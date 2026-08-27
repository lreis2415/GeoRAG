"""
app/models 包
- chat_models.py   : SQLAlchemy ORM 表模型（ChatSession, ChatMessage）
- knowledge_models.py : 知识库相关 Pydantic Schema（Request / Response）
"""

from .chat_models import ChatMessage, ChatSession
from .prompt_template_models import PromptTemplate
from .knowledge_models import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseCreateResponse,
    KnowledgeBaseFileInfo,
    KnowledgeBaseFilesResponse,
    KnowledgeBaseInfo,
    KnowledgeBaseListResponse,
    KnowledgeBaseUpdateRequest,
)

__all__ = [
    # ORM
    "ChatSession",
    "ChatMessage",
    "PromptTemplate",
    # Knowledge Pydantic schemas
    "KnowledgeBaseInfo",
    "KnowledgeBaseFileInfo",
    "KnowledgeBaseCreateRequest",
    "KnowledgeBaseUpdateRequest",
    "KnowledgeBaseListResponse",
    "KnowledgeBaseCreateResponse",
    "KnowledgeBaseFilesResponse",
]
