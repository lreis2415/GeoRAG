-- 创建会话表
CREATE TABLE IF NOT EXISTS chat_sessions(
    session_id text NOT NULL,
    user_id text NOT NULL,
    title varchar(200),
    chat_model_name varchar(200),
    created_at timestamp with time zone DEFAULT now(),
    PRIMARY KEY(session_id)
);

-- 创建消息表
CREATE TABLE IF NOT EXISTS chat_messages(
    message_id text NOT NULL,
    session_id text,
    user_id text NOT NULL,
    role text NOT NULL,
    content text NOT NULL,
    tool_calls_json JSONB,
    generation_status varchar(20),
    created_at timestamp with time zone DEFAULT now(),
    PRIMARY KEY(message_id),
    CONSTRAINT chat_messages_session_id_fkey FOREIGN key(session_id) REFERENCES chat_sessions(session_id)
);

-- 插入初始会话（示例）
INSERT INTO chat_sessions (session_id, user_id)
VALUES ('demo-session-1', '__demo__')
ON CONFLICT (session_id) DO NOTHING;

-- 插入初始消息（示例）
INSERT INTO chat_messages (message_id, session_id, user_id, role, content)
VALUES
('demo-message-1', 'demo-session-1', '__demo__', 'user', '你好，这是一个示例会话'),
('demo-message-2', 'demo-session-1', '__demo__', 'assistant', '你好，我是 GeoRAG 助手，很高兴为你服务');
