import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sys
import time
import warnings
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Iterator
from uuid import UUID

import httpx
import psycopg
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import rag_service

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set in rag-backend/.env")

AUTH_SECRET = os.getenv("AUTH_SECRET")
if not AUTH_SECRET:
    warnings.warn(
        "AUTH_SECRET is not configured; deriving a development signing key from DATABASE_URL. "
        "Set AUTH_SECRET before deploying.",
        RuntimeWarning,
        stacklevel=1,
    )
    AUTH_SECRET = hashlib.sha256(
        b"rag-backend-access-token:" + DATABASE_URL.encode("utf-8")
    ).hexdigest()
if len(AUTH_SECRET) < 32:
    raise RuntimeError("AUTH_SECRET must contain at least 32 characters")

TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LOCAL_ORIGIN_REGEX = (
    r"^https?://(?:localhost|127\.0\.0\.1|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"10(?:\.\d{1,3}){3}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})"
    r"(?::\d{1,5})?$"
)


def snake_to_camel(value: Any) -> Any:
    if isinstance(value, list):
        return [snake_to_camel(item) for item in value]
    if isinstance(value, dict):
        return {
            re.sub(r"_([a-z])", lambda match: match.group(1).upper(), key): snake_to_camel(item)
            for key, item in value.items()
        }
    return value


def encode_token(user_id: UUID) -> str:
    payload = json.dumps(
        {"sub": str(user_id), "exp": int(time.time()) + TOKEN_TTL_SECONDS},
        separators=(",", ":"),
    ).encode("utf-8")
    body = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(AUTH_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    return f"{body.decode('ascii')}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}"


def decode_token(token: str) -> UUID:
    try:
        body_text, signature_text = token.split(".", 1)
        body = body_text.encode("ascii")
        signature = base64.urlsafe_b64decode(
            signature_text + "=" * (-len(signature_text) % 4)
        )
        expected = hmac.new(AUTH_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        payload = json.loads(
            base64.urlsafe_b64decode(body_text + "=" * (-len(body_text) % 4))
        )
        if payload["exp"] <= time.time():
            raise ValueError("Expired token")
        return UUID(payload["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${base64.b64encode(salt).decode('ascii')}${base64.b64encode(digest).decode('ascii')}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_text, digest_text = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = base64.b64decode(salt_text, validate=True)
        expected = base64.b64decode(digest_text, validate=True)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


@contextmanager
def database() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=5,
        sslmode="require",
    ) as connection:
        yield connection


def check_database_connection() -> None:
    with database() as connection:
        connection.execute("SELECT 1")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        await asyncio.to_thread(check_database_connection)
    except Exception:
        print("[ERROR] Failed to connect to Neon DB", flush=True)
        logger.exception("Database connectivity check failed during startup")
    else:
        print("[SUCCESS] Connected to Neon DB", flush=True)
        logger.info("Database connectivity check succeeded during startup")
    yield


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=1024)


class CreateSession(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: re.sub(
            r"_([a-z])", lambda match: match.group(1).upper(), value
        ),
        populate_by_name=True,
    )

    subject_id: UUID
    title: str = Field(default="New Chat", min_length=1, max_length=255)


class CreateMessage(BaseModel):
    content: str = Field(min_length=1, max_length=50000)


bearer_scheme = HTTPBearer(auto_error=False)


def current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UUID:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(credentials.credentials)


app = FastAPI(title="RAG Workspace API", lifespan=lifespan)
logger = logging.getLogger(__name__)
origins = list(
    {
        "http://localhost:5173",
        *(
            origin.strip()
            for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
            if origin.strip()
        ),
    }
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=LOCAL_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    logger.info("Incoming request %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Request failed before returning a response")
        raise
    logger.info(
        "Completed request %s %s with status %s",
        request.method,
        request.url.path,
        response.status_code,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, error: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.detail},
        headers=error.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, error: Exception) -> JSONResponse:
    logger.exception("Unhandled API exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "error": str(error)},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/subjects")
def list_subjects() -> list[dict[str, Any]]:
    with database() as connection:
        rows = connection.execute(
            """
            SELECT id, name, slug, vector_collection_name, description, created_at
            FROM subjects
            ORDER BY name
            """
        ).fetchall()
    return snake_to_camel(rows)


@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
def register(credentials: Credentials) -> dict[str, Any]:
    email = credentials.email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    try:
        with database() as connection:
            user = connection.execute(
                """
                INSERT INTO users (email, password_hash)
                VALUES (%s, %s)
                RETURNING id, email, created_at
                """,
                (email, hash_password(credentials.password)),
            ).fetchone()
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(status_code=409, detail="An account with this email already exists") from error
    return snake_to_camel({"access_token": encode_token(user["id"]), "user": user})


@app.post("/api/v1/auth/login")
def login(credentials: Credentials) -> dict[str, Any]:
    email = credentials.email.strip().lower()
    with database() as connection:
        user = connection.execute(
            "SELECT id, email, password_hash, created_at FROM users WHERE email = %s",
            (email,),
        ).fetchone()
    if user is None or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    public_user = {key: value for key, value in user.items() if key != "password_hash"}
    return snake_to_camel(
        {"access_token": encode_token(user["id"]), "user": public_user}
    )


@app.get("/api/v1/auth/me")
def get_current_user(user_id: UUID = Depends(current_user_id)) -> dict[str, Any]:
    with database() as connection:
        user = connection.execute(
            "SELECT id, email, created_at FROM users WHERE id = %s", (user_id,)
        ).fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="User account no longer exists")
    return snake_to_camel(user)


@app.get("/api/v1/chat-sessions")
def list_chat_sessions(
    subject_id: UUID | None = Query(default=None),
    user_id: UUID = Depends(current_user_id),
) -> list[dict[str, Any]]:
    with database() as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, subject_id, title, created_at, updated_at
            FROM chat_sessions
            WHERE user_id = %s AND (%s::uuid IS NULL OR subject_id = %s)
            ORDER BY updated_at DESC
            """,
            (user_id, subject_id, subject_id),
        ).fetchall()
    return snake_to_camel(rows)


@app.post("/api/v1/chat-sessions", status_code=status.HTTP_201_CREATED)
def create_chat_session(
    request: CreateSession, user_id: UUID = Depends(current_user_id)
) -> dict[str, Any]:
    with database() as connection:
        subject = connection.execute(
            "SELECT id FROM subjects WHERE id = %s", (request.subject_id,)
        ).fetchone()
        if subject is None:
            raise HTTPException(status_code=404, detail="Subject not found")
        session = connection.execute(
            """
            INSERT INTO chat_sessions (user_id, subject_id, title)
            VALUES (%s, %s, %s)
            RETURNING id, user_id, subject_id, title, created_at, updated_at
            """,
            (user_id, request.subject_id, request.title),
        ).fetchone()
    return snake_to_camel(session)


def require_owned_session(
    connection: psycopg.Connection[dict[str, Any]], session_id: UUID, user_id: UUID
) -> dict[str, Any]:
    session = connection.execute(
        "SELECT id, subject_id FROM chat_sessions WHERE id = %s AND user_id = %s",
        (session_id, user_id),
    ).fetchone()
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@app.get("/api/v1/chat-sessions/{session_id}/messages")
def list_messages(
    session_id: UUID, user_id: UUID = Depends(current_user_id)
) -> list[dict[str, Any]]:
    with database() as connection:
        require_owned_session(connection, session_id, user_id)
        rows = connection.execute(
            """
            SELECT id, session_id, sender, content, sources, rag_metadata, created_at
            FROM messages
            WHERE session_id = %s
            ORDER BY created_at, id
            """,
            (session_id,),
        ).fetchall()
    return snake_to_camel(rows)


@app.post(
    "/api/v1/chat-sessions/{session_id}/messages",
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    session_id: UUID,
    request: CreateMessage,
    user_id: UUID = Depends(current_user_id),
) -> dict[str, Any]:
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content cannot be blank")
    with database() as connection:
        require_owned_session(connection, session_id, user_id)
        message = connection.execute(
            """
            INSERT INTO messages (session_id, sender, content)
            VALUES (%s, 'user', %s)
            RETURNING id, session_id, sender, content, sources, rag_metadata, created_at
            """,
            (session_id, content),
        ).fetchone()
        connection.execute(
            """
            UPDATE chat_sessions
            SET title = CASE
                    WHEN title = 'New Chat' THEN LEFT(%s, 42)
                    ELSE title
                END,
                updated_at = %s
            WHERE id = %s
            """,
            (content, datetime.now(timezone.utc), session_id),
        )
    return snake_to_camel(message)


def sse_event(payload: dict[str, Any]) -> str:
    encoded_payload = jsonable_encoder(payload)
    return (
        "data: "
        + json.dumps(encoded_payload, ensure_ascii=False, separators=(",", ":"))
        + "\n\n"
    )


@app.post(
    "/api/v1/chats/{session_id}/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {
                "text/event-stream": {"schema": {"type": "string"}},
            },
        },
    },
)
async def stream_chat(
    session_id: UUID,
    request: CreateMessage,
    user_id: UUID = Depends(current_user_id),
) -> StreamingResponse:
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content cannot be blank")

    with database() as connection:
        session = require_owned_session(connection, session_id, user_id)
        history_rows = connection.execute(
            """
            SELECT sender, content
            FROM messages
            WHERE session_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 12
            """,
            (session_id,),
        ).fetchall()
        user_message = connection.execute(
            """
            INSERT INTO messages (session_id, sender, content)
            VALUES (%s, 'user', %s)
            RETURNING id, session_id, sender, content, sources, rag_metadata, created_at
            """,
            (session_id, content),
        ).fetchone()
        connection.execute(
            """
            UPDATE chat_sessions
            SET title = CASE
                    WHEN title = 'New Chat' THEN LEFT(%s, 42)
                    ELSE title
                END,
                updated_at = %s
            WHERE id = %s
            """,
            (content, datetime.now(timezone.utc), session_id),
        )

    try:
        query_embedding = await rag_service.embed_query(content)
    except Exception as error:
        logger.exception("Query embedding failed for chat session %s", session_id)
        raise HTTPException(
            status_code=502,
            detail=f"Could not create a query embedding with Ollama: {error}",
        ) from error

    try:
        with database() as connection:
            chunks = rag_service.retrieve_top_chunks(
                connection, session["subject_id"], query_embedding, top_k=3
            )
    except Exception as error:
        logger.exception("Vector retrieval failed for chat session %s", session_id)
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve subject document chunks: {error}",
        ) from error

    history = [
        {"role": row["sender"], "content": row["content"]}
        for row in reversed(history_rows)
    ]
    citations = [
        {key: chunk[key] for key in ("id", "title", "page", "score")}
        for chunk in chunks
    ]
    ollama_messages = rag_service.build_messages(content, chunks, history)
    sources_payload = {
        "type": "sources",
        "sources": citations,
        "userMessage": snake_to_camel(user_message),
    }

    async def generate():
        yield sse_event(sources_payload)
        response_parts: list[str] = []
        try:
            async for token in rag_service.stream_completion(ollama_messages):
                response_parts.append(token)
                yield sse_event({"type": "token", "content": token})

            if not response_parts:
                raise RuntimeError("Ollama returned an empty response")

            with database() as connection:
                assistant_message = connection.execute(
                    """
                    INSERT INTO messages (
                        session_id, sender, content, sources, rag_metadata
                    )
                    VALUES (%s, 'assistant', %s, %s, %s)
                    RETURNING id, session_id, sender, content, sources, rag_metadata, created_at
                    """,
                    (
                        session_id,
                        "".join(response_parts),
                        Jsonb(citations),
                        Jsonb(
                            {
                                "model": rag_service.OLLAMA_LLM_MODEL,
                                "retrieved_chunks": len(chunks),
                                "history_messages": len(history),
                            }
                        ),
                    ),
                ).fetchone()
                connection.execute(
                    "UPDATE chat_sessions SET updated_at = %s WHERE id = %s",
                    (datetime.now(timezone.utc), session_id),
                )
            yield sse_event(
                {
                    "type": "done",
                    "assistantMessage": snake_to_camel(assistant_message),
                }
            )
        except Exception as error:
            logger.exception("Stream generation failed for chat session %s", session_id)
            yield sse_event({"type": "error", "message": f"RAG response failed: {error}"})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Keep CORS outside Starlette's error middleware so even unhandled-error responses
# carry the configured browser CORS headers.
fastapi_app = app
app = CORSMiddleware(
    app=fastapi_app,
    allow_origins=origins,
    allow_origin_regex=LOCAL_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
