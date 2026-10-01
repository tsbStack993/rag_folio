-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Subjects Table (The top-level workspace tier)
CREATE TABLE IF NOT EXISTS subjects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    vector_collection_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Chat Sessions Table (Scoped to a specific subject and user)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title VARCHAR(255) DEFAULT 'New Chat',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Messages Table (With RAG citation placeholders)
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    sender VARCHAR(20) NOT NULL CHECK (sender IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources JSONB DEFAULT '[]'::jsonb,      -- Holds document chunk citations returned by RAG
    rag_metadata JSONB DEFAULT '{}'::jsonb,  -- Holds operational stats (latency, tokens)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Subject-scoped source chunks used for pgvector similarity search.
CREATE TABLE IF NOT EXISTS subject_document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(768) NOT NULL
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'subject_document_chunks'
          AND column_name = 'metadata'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'subject_document_chunks'
              AND column_name = 'metada'
        ) THEN
            ALTER TABLE subject_document_chunks RENAME COLUMN metada TO metadata;
        ELSIF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'subject_document_chunks'
              AND column_name = 'rag_metadata'
        ) THEN
            ALTER TABLE subject_document_chunks RENAME COLUMN rag_metadata TO metadata;
        ELSE
            ALTER TABLE subject_document_chunks
                ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'subject_document_chunks'
          AND column_name = 'metada'
    ) THEN
        EXECUTE $migration$
            UPDATE subject_document_chunks
            SET metadata = COALESCE(metadata, '{}'::jsonb)
                || COALESCE(metada, '{}'::jsonb)
            WHERE COALESCE(metada, '{}'::jsonb) <> '{}'::jsonb
        $migration$;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'subject_document_chunks'
          AND column_name = 'rag_metadata'
    ) THEN
        EXECUTE $migration$
            UPDATE subject_document_chunks
            SET metadata = COALESCE(metadata, '{}'::jsonb)
                || COALESCE(rag_metadata, '{}'::jsonb)
            WHERE COALESCE(rag_metadata, '{}'::jsonb) <> '{}'::jsonb
        $migration$;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'subject_document_chunks'
          AND column_name = 'document_title'
    ) THEN
        EXECUTE $migration$
            UPDATE subject_document_chunks
            SET metadata = COALESCE(metadata, '{}'::jsonb)
                || jsonb_strip_nulls(jsonb_build_object('document_title', document_title))
            WHERE COALESCE(metadata, '{}'::jsonb)->>'document_title' IS NULL
        $migration$;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'subject_document_chunks'
          AND column_name = 'page_number'
    ) THEN
        EXECUTE $migration$
            UPDATE subject_document_chunks
            SET metadata = COALESCE(metadata, '{}'::jsonb)
                || jsonb_strip_nulls(jsonb_build_object('page_number', page_number))
            WHERE COALESCE(metadata, '{}'::jsonb)->>'page_number' IS NULL
        $migration$;
    END IF;
END
$$;

ALTER TABLE subject_document_chunks
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE subject_document_chunks
SET metadata = '{}'::jsonb
WHERE metadata IS NULL;

ALTER TABLE subject_document_chunks
    ALTER COLUMN metadata SET DEFAULT '{}'::jsonb,
    ALTER COLUMN metadata SET NOT NULL;

-- Indexes for fast query performance
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_subject ON chat_sessions(user_id, subject_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON subject_document_chunks USING hnsw (embedding vector_cosine_ops);
