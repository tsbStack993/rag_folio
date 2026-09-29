# RAG Workspace API

FastAPI service for accounts, seeded subjects, chat sessions, and persisted user messages.
The Neon connection string is used only by this backend; do not put it in `rag-ui`.

## Run locally

1. Create/activate a Python virtual environment and install `requirements.txt`.
2. Copy `.env.example` to `.env` and set `DATABASE_URL` to the Neon connection string.
   Set `AUTH_SECRET` to a long, random value (for example, generate one with
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
3. Apply `db/schema.sql` to the database, then run `python seed.py` to add the subjects.
4. Start the API with `uvicorn main:app --reload`.

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

Authenticated endpoints use `Authorization: Bearer <accessToken>`. API responses map
database `snake_case` columns to frontend `camelCase`. Passwords are stored as scrypt
hashes. The message endpoint currently persists user messages; an assistant/RAG
generation service is not part of this backend yet.
