# RAG Workspace UI

React/Vite frontend for the RAG Workspace API. The UI talks only to the HTTP API;
keep the Neon `DATABASE_URL` in `rag-backend/.env`, never in Vite environment variables.

## Run locally

1. Start the backend by following [`rag-backend/README.md`](../rag-backend/README.md).
2. Copy `.env.example` to `.env` and set `VITE_API_BASE_URL` if the API is not at
   `http://localhost:8000`.
3. Run `npm install`, then `npm run dev`.

The UI fetches subjects and conversation history from the API and stores account tokens
in browser local storage. User messages are persisted. Assistant/RAG response generation
is not implemented by the current backend.
