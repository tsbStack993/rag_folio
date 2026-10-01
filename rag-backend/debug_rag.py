"""Inspect the stored RAG chunks and exercise the embedded-systems retrieval query."""

import asyncio
import json
import os
import traceback
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from rag_service import embed_query, vector_literal

load_dotenv(Path(__file__).with_name(".env"))

DEBUG_QUERY = (
    "What is the main drawback of using a simple main loop design for small "
    "embedded systems?"
)
CHUNK_PREVIEW_PATH = Path(__file__).with_name("debug_chunks.txt")


def inspect_chunks(connection: psycopg.Connection[dict[str, Any]]) -> None:
    total = connection.execute(
        "SELECT count(*) AS total FROM subject_document_chunks"
    ).fetchone()["total"]
    by_subject = connection.execute(
        """
        SELECT subject_id, count(*) AS chunk_count
        FROM subject_document_chunks
        GROUP BY subject_id
        ORDER BY subject_id
        """
    ).fetchall()
    print(f"Total subject_document_chunks rows: {total}")
    print("Chunk count by subject_id:")
    if not by_subject:
        print("  (no chunks found)")
    for row in by_subject:
        print(f"  {row['subject_id']}: {row['chunk_count']}")

    chunks = connection.execute(
        """
        SELECT id, subject_id, content
        FROM subject_document_chunks
        ORDER BY subject_id, id
        """
    )
    with CHUNK_PREVIEW_PATH.open("w", encoding="utf-8", newline="\n") as preview_file:
        for row in chunks:
            excerpt = " ".join(row["content"].split())[:100]
            preview_file.write(
                f"id: {row['id']}\n"
                f"subject_id: {row['subject_id']}\n"
                f"excerpt: {excerpt}\n\n"
            )
    print(f"Wrote chunk excerpts to {CHUNK_PREVIEW_PATH}")


async def run_similarity_search() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set in rag-backend/.env")

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        subject = connection.execute(
            "SELECT id FROM subjects WHERE slug = %s",
            ("embedded-system",),
        ).fetchone()
        if subject is None:
            raise RuntimeError("No subject with slug 'embedded-system' exists in Neon")
        subject_id = UUID(str(subject["id"]))
        print(f"embedded-system subject_id: {subject_id}")

        query_embedding = await embed_query(DEBUG_QUERY)
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
            (vector, subject_id, vector, 3),
        ).fetchall()

    print(f"Similarity search results for: {DEBUG_QUERY}")
    print(f"Retrieved {len(rows)} chunk(s):")
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, indent=2, default=str))


async def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set in rag-backend/.env")

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        inspect_chunks(connection)
    await run_similarity_search()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        traceback.print_exc()
        raise
