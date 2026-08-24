-- Persist the most recently used chat model for each conversation.
-- Existing sessions remain NULL and clients should fall back to their default model.

ALTER TABLE IF EXISTS chat_sessions
    ADD COLUMN IF NOT EXISTS chat_model_name VARCHAR(200);
