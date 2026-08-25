-- Persist only the UI-safe terminal MCP tool-call summary for chat replay.
-- Raw tool arguments, outputs, headers and internal execution IDs remain in
-- protected audit storage and must never be copied into this table.

ALTER TABLE IF EXISTS chat_messages
    ADD COLUMN IF NOT EXISTS tool_calls_json JSONB;

ALTER TABLE IF EXISTS chat_messages
    ADD COLUMN IF NOT EXISTS generation_status VARCHAR(20);
