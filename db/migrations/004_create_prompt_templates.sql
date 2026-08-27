CREATE TABLE IF NOT EXISTS prompt_templates (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    name VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prompt_templates_user_updated
    ON prompt_templates (user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_prompt_templates_user_name
    ON prompt_templates (user_id, name);
