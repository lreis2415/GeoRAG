-- Add Java JWT subject ownership to existing Agent data.
-- Existing rows remain NULL until an explicit ownership migration is supplied;
-- application queries must never return rows with NULL user_id to normal users.

ALTER TABLE IF EXISTS chat_sessions
    ADD COLUMN IF NOT EXISTS user_id TEXT;

ALTER TABLE IF EXISTS chat_messages
    ADD COLUMN IF NOT EXISTS user_id TEXT;

ALTER TABLE IF EXISTS chat_runs
    ADD COLUMN IF NOT EXISTS user_id TEXT;

ALTER TABLE IF EXISTS tool_runs
    ADD COLUMN IF NOT EXISTS user_id TEXT;

-- Some existing Docker volumes predate the optional vector_collections table.
-- Create it here so this migration remains safe on those databases.
CREATE TABLE IF NOT EXISTS vector_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    name TEXT UNIQUE NOT NULL,
    cmetadata JSONB,
    "uuid" UUID UNIQUE DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE IF EXISTS vector_collections
    ADD COLUMN IF NOT EXISTS user_id TEXT;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_created
    ON chat_sessions (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_messages_user_session_created
    ON chat_messages (user_id, session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_chat_runs_user_created
    ON chat_runs (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tool_runs_user_created
    ON tool_runs (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_vector_collections_user
    ON vector_collections (user_id);
