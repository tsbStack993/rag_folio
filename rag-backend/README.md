# RAG Workspace API

FastAPI service for accounts, seeded subjects, chat sessions, and persisted RAG chat messages.
The Neon connection string is used only by this backend; do not put it in `rag-ui`.

## Run locally

1. Create/activate a Python virtual environment and install `requirements.txt`.
2. Copy `.env.example` to `.env` and set `DATABASE_URL` to the Neon connection string.
   Set `AUTH_SECRET` to a long, random value (for example, generate one with
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
3. Install the local Ollama models with `ollama pull nomic-embed-text` and
   `ollama pull llama3.2`, then ensure Ollama is running at `OLLAMA_BASE_URL`.
   Ollama requests allow up to `OLLAMA_REQUEST_TIMEOUT_SECONDS` (600 seconds by default)
   for slow local model startup and generation.
4. Apply `db/schema.sql` to the database, then run `python seed.py` to add the subjects.
   This enables pgvector and creates the `subject_document_chunks` table and cosine HNSW index.
   The table stores one 768-dimensional embedding per chunk and document citation values
   in `metadata`.
5. Start Ollama, then run `python ingest_documents.py` from `rag-backend` to upsert sample
   subject notes with citations and embeddings. The script is safe to rerun. You can edit
   or extend `STARTER_DOCUMENTS` in that file to add material; subjects must be seeded first.
6. Start the API with `uvicorn main:app --reload`.

The API is available at `http://localhost:8000`; interactive OpenAPI docs are at
`http://localhost:8000/docs`. `FRONTEND_ORIGINS` is a comma-separated list of allowed
browser origins and defaults to `http://localhost:5173`.
If `AUTH_SECRET` is omitted, local development derives a signing key from `DATABASE_URL`
and emits a warning; configure a dedicated secret before deployment.

## API

- `GET /api/v1/subjects`
- `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`
- `GET /api/v1/chat-sessions?subject_id=<uuid>`, `POST /api/v1/chat-sessions`
- `GET /api/v1/chat-sessions/{session_id}/messages`
- `POST /api/v1/chat-sessions/{session_id}/messages`
- `POST /api/v1/chats/{session_id}/stream` (authenticated SSE stream)

Authenticated endpoints use `Authorization: Bearer <accessToken>`. API responses map
database `snake_case` columns to frontend `camelCase`. Passwords are stored as scrypt
hashes. The streaming endpoint persists the user's message before retrieval, sends a
`sources` event followed by `token` events, then saves and emits the completed assistant
message in a `done` event. Errors after streaming begins are sent as an `error` event.
