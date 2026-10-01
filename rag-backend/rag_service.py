import json
import logging
import math
import os
from collections.abc import AsyncIterator, Sequence
from typing import Any
from uuid import UUID

import httpx
import psycopg
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.2")
OLLAMA_REQUEST_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "600"))
EMBEDDING_DIMENSIONS = 768
logger = logging.getLogger(__name__)


def vector_literal(embedding: Sequence[float]) -> str:
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Expected a {EMBEDDING_DIMENSIONS}-dimensional embedding, got {len(embedding)}"
        )
    if not all(math.isfinite(value) for value in embedding):
        raise ValueError("Embedding contains a non-finite value")
    return "[" + ",".join(str(value) for value in embedding) + "]"


async def embed_query(text: str) -> list[float]:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(OLLAMA_REQUEST_TIMEOUT_SECONDS, connect=10)
        ) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/embed",
                json={"model": OLLAMA_EMBED_MODEL, "input": text},
            )
            response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Ollama returned an invalid embedding response")
        embeddings = payload.get("embeddings")
        if (
            not isinstance(embeddings, list)
            or not embeddings
            or not isinstance(embeddings[0], list)
        ):
            raise ValueError("Ollama returned no query embedding")
        embedding = embeddings[0]
        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Ollama returned a {len(embedding)}-dimensional embedding; "
                f"{EMBEDDING_DIMENSIONS} dimensions are required"
            )
        query_embedding = [float(value) for value in embedding]
        if not all(math.isfinite(value) for value in query_embedding):
            raise ValueError("Ollama returned a non-finite embedding value")
        return query_embedding
    except Exception:
        logger.exception("Failed to create query embedding with Ollama")
        raise


def retrieve_top_chunks(
    connection: psycopg.Connection[dict[str, Any]],
    subject_id: UUID,
    query_embedding: Sequence[float],
    top_k: int = 3,
) -> list[dict[str, Any]]:
    try:
        if top_k < 1 or top_k > 20:
            raise ValueError("top_k must be between 1 and 20")
        vector = vector_literal(query_embedding)
        rows = connection.execute(
            """
            SELECT id, content, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM subject_document_chunks
            WHERE subject_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vector, subject_id, vector, top_k),
        ).fetchall()

        chunks = []
        for row in rows:
            metadata = row["metadata"] or {}
            if not isinstance(metadata, dict):
                raise ValueError(f"Chunk {row['id']} has invalid citation metadata")
            title = metadata.get(
                "document_title",
                metadata.get("documentTitle", metadata.get("title", "Source document")),
            )
            page = metadata.get(
                "page_number",
                metadata.get("pageNumber", metadata.get("page", 1)),
            )
            chunks.append(
                {
                    "id": str(row["id"]),
                    "content": row["content"],
                    "title": title if isinstance(title, str) else "Source document",
                    "page": page if isinstance(page, int) else 1,
                    "score": round(float(row["score"]), 4),
                }
            )
        return chunks
    except Exception:
        logger.exception("Failed to retrieve subject document chunks for subject %s", subject_id)
        raise


def build_messages(
    prompt: str,
    chunks: list[dict[str, Any]],
    history: list[dict[str, str]],
) -> list[dict[str, str]]:
    context = "\n\n".join(
        f"--- Source: {chunk['title']} (Page {chunk['page']}) ---\n{chunk['content']}"
        for chunk in chunks
    )
    system_prompt = (
        "You are an academic assistant. Answer using only the supplied source context "
        "and conversation history. Do not add unsupported factual claims. If the sources "
        "do not contain enough information, say so clearly."
        f"\n\nRETRIEVED SOURCE CONTEXT:\n{context or 'No relevant source chunks were found.'}"
    )
    return [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": prompt},
    ]


async def stream_completion(
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(OLLAMA_REQUEST_TIMEOUT_SECONDS, connect=10)
        ) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/chat",
                json={"model": OLLAMA_LLM_MODEL, "messages": messages, "stream": True},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        raise RuntimeError("Ollama returned an invalid generation event")
                    if error := payload.get("error"):
                        raise RuntimeError(f"Ollama generation failed: {error}")
                    if "done" in payload and not isinstance(payload["done"], bool):
                        raise RuntimeError("Ollama returned an invalid completion status")
                    message = payload.get("message", {})
                    if not isinstance(message, dict):
                        raise RuntimeError("Ollama returned an invalid message event")
                    token = message.get("content", "")
                    if not isinstance(token, str):
                        raise RuntimeError("Ollama returned an invalid token value")
                    if token:
                        yield token
                    if payload.get("done") is True:
                        break
                else:
                    raise RuntimeError("Ollama ended the stream without a completion event")
    except Exception:
        logger.exception("Failed to stream completion from Ollama")
        raise
