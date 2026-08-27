"""SQLAlchemy models for per-user prompt templates."""

import uuid

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, func

from app.db.base import Base


class PromptTemplate(Base):
    """A private reusable system prompt owned by one authenticated user."""

    __tablename__ = "prompt_templates"
    __table_args__ = (
        Index("idx_prompt_templates_user_updated", "user_id", "updated_at"),
        Index("idx_prompt_templates_user_name", "user_id", "name"),
    )

    id = Column(String(64), primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id = Column(String(128), index=True, nullable=False, comment="Java用户ID")
    name = Column(String(100), nullable=False, comment="提示词名称")
    content = Column(Text, nullable=False, comment="提示词正文")
    version = Column(Integer, nullable=False, default=1, comment="乐观锁版本")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
