from sqlalchemy import Column, DateTime, String, Text, func

from app.db.base import Base


class ChatSession(Base):
    """聊天会话模型"""

    __tablename__ = "chat_sessions"

    session_id = Column(String(64), primary_key=True, index=True, comment="会话ID")
    title = Column(String(200), nullable=True, comment="会话标题")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class ChatMessage(Base):
    """聊天消息模型"""

    __tablename__ = "chat_messages"

    message_id = Column(String(64), primary_key=True, comment="消息ID")
    session_id = Column(String(64), index=True, nullable=False, comment="会话ID")
    role = Column(String(20), nullable=False, comment="角色：user/assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    @classmethod
    def create_id(cls):
        """生成消息ID"""
        import uuid

        return uuid.uuid4().hex
