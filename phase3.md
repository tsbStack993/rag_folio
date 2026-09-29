Here is the blueprint for **Phase 3: Python FastAPI + Ollama + pgvector Implementation**.

This phase connects your **React UI (Phase 2)** to your **Neon PostgreSQL DB (Phase 1)** while integrating **Ollama** for running local LLMs and embeddings.

---
k
### Phase 3 Architecture & Flow

```
[React UI] --(SSE / Streaming)--> [FastAPI App] 
                                    ├── Auth JWT Verification
                                    ├── Embed Query (Ollama)
                                    ├── Similarity Search (Neon / pgvector)
                                    └── Token Streaming (Ollama LLM)

```

---

### Step 1: Backend Dependencies & Setup

Inside your `rag-backend` folder, install the required asynchronous Python dependencies:

```bash
pip install fastapi uvicorn[standard] asyncpg psycopg[binary] pgvector ollama python-jose[cryptography] passlib[bcrypt] python-dotenv pydantic

```

Update your `.env` file to include JWT secrets and local Ollama details:

```env
DATABASE_URL=postgresql://alex:password@ep-xyz-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
SECRET_KEY=your_super_secret_jwt_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.2
OLLAMA_EMBED_MODEL=nomic-embed-text

```

---

### Step 2: Vector Store Setup (`vector_store.sql`)

Enable the `vector` extension on Neon PostgreSQL and create a table to hold domain chunks mapped to your **5 Subjects**:

```sql
-- Enable vector extension in Neon
CREATE EXTENSION IF NOT EXISTS vector;

-- Table to hold knowledge base documents/chunks
CREATE TABLE IF NOT EXISTS subject_document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    document_title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    page_number INT,
    embedding VECTOR(768), -- Matches nomic-embed-text dimension size
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- HNSW index for sub-millisecond vector similarity search
CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
ON subject_document_chunks 
USING hnsw (embedding vector_cosine_ops);

```

---

### Step 3: Minimal RAG & Streaming Engine (`rag_service.py`)

Create a dedicated module for interacting with Ollama and querying pgvector:

```python
import os
import json
import psycopg
from pgvector.psycopg import register_vector
import ollama

DATABASE_URL = os.getenv("DATABASE_URL")
LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.2")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

async def get_query_embedding(text: str) -> list[float]:
    """Generates embeddings using local Ollama instance."""
    client = ollama.AsyncClient()
    response = await client.embed(model=EMBED_MODEL, input=text)
    return response['embeddings'][0]

def retrieve_top_chunks(subject_id: str, query_embedding: list[float], top_k: int = 3):
    """Performs Cosine Similarity vector search in Neon PostgreSQL."""
    with psycopg.connect(DATABASE_URL) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT document_title, page_number, content, 
                       1 - (embedding <=> %s::vector) AS similarity
                FROM subject_document_chunks
                WHERE subject_id = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
            """, (query_embedding, subject_id, query_embedding, top_k))
            
            rows = cur.fetchall()
            return [
                {
                    "title": row[0],
                    "page": row[1],
                    "content": row[2],
                    "score": round(float(row[3]), 3)
                }
                for row in rows
            ]

async def stream_rag_response(prompt: str, context_chunks: list[dict]):
    """Formats prompt with context and streams LLM response tokens."""
    client = ollama.AsyncClient()
    
    # 1. Format Knowledge Context
    context_text = "\n\n".join([f"--- Source: {c['title']} (Page {c['page']}) ---\n{c['content']}" for c in context_chunks])
    
    system_instruction = (
        "You are an academic expert assistant. Answer the question using ONLY the provided context below. "
        "If the context does not contain enough info, state clearly that you don't know.\n\n"
        f"CONTEXT:\n{context_text}"
    )

    # 2. Yield Retrieved Citations First via Server-Sent Event (SSE)
    sources_payload = json.dumps({"type": "sources", "data": context_chunks})
    yield f"data: {sources_payload}\n\n"

    # 3. Stream Response Tokens
    stream = await client.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        stream=True
    )

    async for chunk in stream:
        token = chunk['message']['content']
        token_payload = json.dumps({"type": "token", "content": token})
        yield f"data: {token_payload}\n\n"
        
    yield "data: [DONE]\n\n"

```

---

### Step 4: Main FastAPI Server (`main.py`)

Create the FastAPI application serving metadata and the SSE streaming endpoint:

```python
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import psycopg
import os

from rag_service import get_query_embedding, retrieve_top_chunks, stream_rag_response

app = FastAPI(title="Two-Tier RAG API", version="1.0")

# Enable CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")

@app.get("/api/v1/subjects")
def get_subjects():
    """Returns available subjects to populate View 2 (Subject Hub)."""
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, slug, vector_collection_name, description FROM subjects;")
            rows = cur.fetchall()
            return [
                {"id": str(r[0]), "name": r[1], "slug": r[2], "vector_collection_name": r[3], "description": r[4]}
                for r in rows
            ]

@app.get("/api/v1/chat/stream")
async def chat_stream(
    subject_id: str = Query(...),
    session_id: str = Query(...),
    message: str = Query(...)
):
    """
    RAG Streaming Endpoint returning SSE (Server-Sent Events).
    Sends retrieved sources followed by streamed LLM tokens.
    """
    try:
        # Step A: Generate Embedding
        query_vec = await get_query_embedding(message)
        
        # Step B: Perform pgvector Cosine Search
        chunks = retrieve_top_chunks(subject_id=subject_id, query_embedding=query_vec, top_k=3)
        
        # Step C: Return Streaming Response (SSE)
        return StreamingResponse(
            stream_rag_response(prompt=message, context_chunks=chunks),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"}  # Disable buffering for real-time streaming
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

```

---

### Step 5: Connecting Frontend to Backend

In your **Phase 2 React UI**, replace the mock streaming logic in `sendMessage` with a real `EventSource` or `fetch` stream:

```typescript
const response = await fetch(
  `http://localhost:8000/api/v1/chat/stream?subject_id=${activeSubject.id}&session_id=${activeSessionId}&message=${encodeURIComponent(userMessage)}`
);

const reader = response.body?.getReader();
const decoder = new TextDecoder("utf-8");

while (reader) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value, { stream: true });
  const lines = chunk.split("\n\n");

  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const payload = line.replace("data: ", "").trim();
      if (payload === "[DONE]") break;

      const parsed = JSON.parse(payload);
      if (parsed.type === "sources") {
        setSources(parsed.data); // Update RAG citations state
      } else if (parsed.type === "token") {
        appendTokenToMessage(parsed.content); // Stream token to UI
      }
    }
  }
}

```

---

### Verification Run Command

1. Make sure **Ollama** is running locally with models pulled:
```bash
ollama pull llama3.2
ollama pull nomic-embed-text

```


2. Start the FastAPI server:
```bash
uvicorn main:app --reload --port 8000

```


3. Test your endpoints at `
`http://localhost:8000/docs` to inspect the automatic Swagger UI and test your endpoints.

---

### Phase 3 Summary Checklist

With Phase 3 complete, your full-stack system components are wired together as follows:

1. **Phase 1 (PostgreSQL Database):** Holds your `users`, `subjects`, `chat_sessions`, and vector embeddings in `subject_document_chunks`.
2. **Phase 2 (React UI Shell):** Manages the **Two-Tier Hub** state, workspace navigation, chat windows, and streams back responses token-by-token.
3. **Phase 3 (FastAPI + Ollama RAG):**
* Fetches subjects dynamically from Neon.
* Generates query embeddings using Ollama's `nomic-embed-text`.
* Performs high-speed Cosine similarity search using `pgvector` in Neon.
* Streams responses token-by-token using `llama3.2` and Server-Sent Events (`text/event-stream`).