"""
数据模型模块
定义 API 通用请求/响应的 Pydantic 模型。

业务域模型请放对应的 app/models/<domain>_models.py：
  - 知识库相关：app/models/knowledge_models.py
  - ORM 表模型：app/models/chat_models.py
"""

from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel, Field

# 定义通用响应数据类型
T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    """标准API响应格式"""

    success: bool  # 操作是否成功
    code: int  # 状态码，如2000表示成功
    message: str  # 描述信息
    data: Optional[T] = None  # 返回数据，可以是任何类型

    def dict(self):
        """转换为字典格式"""
        return {
            "success": self.success,
            "code": self.code,
            "message": self.message,
            "data": self.data,
        }


class AskRequest(BaseModel):
    """RAG问答请求模型（保留向后兼容，推荐改用 app.models.KnowledgeAskRequest）"""

    prompt: str = Field(
        ..., description="系统提示词", example="你是一个地理信息专家助手"
    )
    query: str = Field(..., description="用户查询问题", example="什么是数字地形模型？")
    db_name: str = Field(..., description="知识库名称", example="geo_knowledge")
    chat_model_name: Optional[str] = Field(
        None, description="聊天模型名称", example="qwen-turbo-latest"
    )


class ChatRequest(BaseModel):
    """聊天对话请求模型"""

    prompt: str = Field(
        ..., description="系统提示词", example="你是一个地理信息专家助手"
    )
    query: str = Field(..., description="用户查询问题", example="什么是数字地形模型？")
    chat_model_name: Optional[str] = Field(
        None, description="聊天模型名称", example="qwen-turbo-latest"
    )
    session_id: Optional[str] = Field(
        None, description="会话ID", example="550e8400-e29b-41d4-a716-446655440000"
    )
    use_memory: Optional[bool] = Field(
        None, description="是否使用记忆功能", example=True
    )
    db_name: Optional[str] = Field(
        None,
        description="知识库名称（可选，提供时启用RAG）",
        example="geo_knowledge_base",
    )


class ChatHistoryRequest(BaseModel):
    """聊天历史请求模型"""

    session_id: str = Field(
        ..., description="会话ID", example="550e8400-e29b-41d4-a716-446655440000"
    )


class HealthResponse(BaseModel):
    """健康检查响应模型"""

    status: str
    version: str


class ModelsResponse(BaseModel):
    """模型列表响应模型"""

    embedding_models: List[str]
    chat_models: List[str]


class SessionsResponse(BaseModel):
    """会话列表响应模型"""

    sessions: Dict[str, Dict[str, Union[str, int]]] = Field(
        ..., description="会话列表，键为会话ID，值为会话信息"
    )


class ChatResponse(BaseModel):
    """聊天对话响应模型"""

    response: str = Field(..., description="AI回复内容")
    session_id: Optional[str] = Field(None, description="会话ID")
    message_count: Optional[int] = Field(None, description="消息数量")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="工具调用信息")


class ChatInitResponse(BaseModel):
    """初始化聊天响应模型"""

    session_id: str = Field(..., description="新创建的会话ID")


class ChatHistoryResponse(BaseModel):
    """聊天历史响应模型"""

    session_id: str = Field(..., description="会话ID")
    history: List[Dict[str, str]] = Field(..., description="对话历史记录")
    created_at: str = Field(..., description="会话创建时间")
    last_active: str = Field(..., description="最后活跃时间")


# ==================== 向后兼容 re-export ====================
# 知识库相关模型已移至 app/models/knowledge_models.py
# 此处保留别名，避免其他模块的 import 失效

from app.models.knowledge_models import (  # noqa: E402, F401
    KnowledgeAskRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseCreateResponse,
    KnowledgeBaseFileInfo,
    KnowledgeBaseFilesResponse,
    KnowledgeBaseInfo,
    KnowledgeBaseListResponse,
    KnowledgeBaseUpdateRequest,
)
