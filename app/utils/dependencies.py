"""
依赖注入模块
管理服务实例的创建和依赖注入
"""

from functools import lru_cache

from sqlalchemy.orm import Session

from app.services import (
    ChatService,
    DatabaseService,
    DocumentService,
    MCPService,
    ModelService,
    RAGService,
)
from app.services.db import SessionLocal


# 使用lru_cache确保单例模式
@lru_cache()
def get_model_service() -> ModelService:
    """获取模型服务实例"""
    return ModelService()


@lru_cache()
def get_database_service() -> DatabaseService:
    """获取数据库服务实例"""
    return DatabaseService()


@lru_cache()
def get_document_service() -> DocumentService:
    """获取文档服务实例"""
    return DocumentService()


@lru_cache()
def get_chat_service() -> ChatService:
    """获取聊天服务实例"""
    return ChatService()


@lru_cache()
def get_rag_service() -> RAGService:
    """获取RAG服务实例"""
    return RAGService()


@lru_cache()
def get_mcp_service() -> MCPService:
    """获取MCP服务实例"""
    return MCPService()


# 全局服务实例（用于应用生命周期管理）
_global_mcp_service = None


def get_global_mcp_service() -> MCPService:
    """获取全局MCP服务实例"""
    global _global_mcp_service
    if _global_mcp_service is None:
        _global_mcp_service = MCPService()
    return _global_mcp_service


def set_global_mcp_service(service: MCPService):
    """设置全局MCP服务实例"""
    global _global_mcp_service
    _global_mcp_service = service


# 新增：数据库 Session 依赖
def get_db() -> Session:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
