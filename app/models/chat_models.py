from sqlalchemy import Column, DateTime, String, Text, func

from app.db.base import Base


class ChatSession(Base):
    """聊天会话模型"""

    __tablename__ = "chat_sessions"

    session_id = Column(String(64), primary_key=True, index=True, comment="会话ID")
    user_id = Column(String(128), index=True, nullable=True, comment="Java用户ID")
    title = Column(String(200), nullable=True, comment="会话标题")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class ChatMessage(Base):
    """聊天消息模型"""

    __tablename__ = "chat_messages"

    message_id = Column(String(64), primary_key=True, comment="消息ID")
    session_id = Column(String(64), index=True, nullable=False, comment="会话ID")
    user_id = Column(String(128), index=True, nullable=True, comment="Java用户ID")
    role = Column(String(20), nullable=False, comment="角色：user/assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    @classmethod
    def create_id(cls):
        """生成消息ID"""
        import uuid

        return uuid.uuid4().hex


class ChatRun(Base):
    """One observable execution of the chat endpoint."""

    __tablename__ = "chat_runs"

    request_id = Column(String(64), primary_key=True, comment="请求追踪ID")
    session_id = Column(String(64), index=True, nullable=True, comment="会话ID")
    user_id = Column(String(128), index=True, nullable=True, comment="Java用户ID")
    user_message_id = Column(String(64), nullable=True, comment="用户消息ID")
    status = Column(String(20), index=True, nullable=False, comment="运行状态")
    error_type = Column(String(120), nullable=True, comment="错误类型")
    error_message = Column(Text, nullable=True, comment="错误摘要")
    duration_ms = Column(Integer, nullable=True, comment="总耗时（毫秒）")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    finished_at = Column(DateTime, nullable=True)


class ToolRun(Base):
    """Durable audit record for a tool execution within a chat run."""

    __tablename__ = "tool_runs"

    tool_run_id = Column(String(64), primary_key=True, comment="工具调用追踪ID")
    request_id = Column(String(64), index=True, nullable=False, comment="请求追踪ID")
    user_id = Column(String(128), index=True, nullable=True, comment="Java用户ID")
    tool_name = Column(String(255), nullable=True, comment="工具名称")
    status = Column(String(20), index=True, nullable=False, comment="运行状态")
    input_digest = Column(String(255), nullable=True, comment="输入长度与摘要哈希")
    output_digest = Column(String(255), nullable=True, comment="输出长度与摘要哈希")
    error_message = Column(Text, nullable=True, comment="错误摘要")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    finished_at = Column(DateTime, nullable=True)
