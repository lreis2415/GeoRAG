"""
聊天功能路由
提供聊天对话相关的API接口
"""

from fastapi import APIRouter, Depends
from app.utils.response import success_response, error_response
from app.utils.models import ChatRequest, ChatHistoryRequest
from app.utils.dependencies import (
    get_chat_service,
    get_model_service,
    get_rag_service,
    get_global_mcp_service,
    get_mcp_service
)
from ..services.chat_service import ChatService
from ..services.model_service import ModelService
from ..services.rag_service import RAGService
from ..services.mcp_service import MCPService

from pydantic import BaseModel, Field
from typing import Optional, Dict, List

class ChatResponse(BaseModel):
    """聊天接口返回体"""
    response: str = Field(..., description="聊天响应内容", example="数字地形模型是...")
    session_id: Optional[str] = Field(None, description="会话ID", example="550e8400-e29b-41d4-a716-446655440000")
    message_count: Optional[int] = Field(None, description="消息数量", example=5)
    

router = APIRouter()

@router.post("/chat")
async def chat_with_agent(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
    model_service: ModelService = Depends(get_model_service),
    rag_service: RAGService = Depends(get_rag_service),
    mcp_service: MCPService = Depends(get_mcp_service)
):
    """
    聊天对话（支持记忆功能）
    """
    try:
        # 验证聊天模型是否存在
        chat_model_name = request.chat_model_name or model_service.get_default_chat_model()
        if not model_service.validate_chat_model(chat_model_name):
            return error_response(message=f"聊天模型 '{chat_model_name}' 不可用", code=4000)
        
        # 处理会话和记忆
        session_id = None
        history = None
        
        if request.use_memory:
            # 检查是否提供了session_id
            if not request.session_id:
                return error_response(message="使用记忆功能时必须提供session_id", code=4000)
            
            # 验证会话是否存在
            if not chat_service.session_exists(request.session_id):
                return error_response(message="会话不存在，请先创建会话", code=4004)
            
            # 获取历史对话
            session_id = request.session_id
            chat_service.update_session_activity(session_id)
            history = chat_service.get_conversation_history(session_id)
        
        # 获取MCP工具
        mcp_service_instance = get_global_mcp_service()
        mcp_tools = mcp_service_instance.get_mcp_tools() or []
        print("sessionId",session_id, history)
        # 调用RAG服务进行对话
        result = await rag_service.chat_with_agent(
            prompt=request.prompt,
            query=request.query,
            mcp_tools=mcp_tools,
            chat_model_name=chat_model_name,
            session_id=session_id,
            use_memory=request.use_memory,
            history=history
        )
        # 如果使用记忆功能，保存对话记录
        if request.use_memory and session_id:
            chat_service.add_to_memory(session_id, request.query, result["response"])
            result["message_count"] = len(chat_service.get_conversation_history(session_id)) // 2
        
        return success_response(data=result)
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5010)

@router.get("/chat/init")
async def init_chat_service(chat_service: ChatService = Depends(get_chat_service)):
    """
    初始化聊天服务并创建新会话
    """
    try:
        # 创建新会话
        session_id = chat_service.create_session()
        return success_response(data={"session_id": session_id}, message="聊天服务已初始化")
    except Exception as e:
        return error_response(message="无法初始化聊天服务", code=5015)


    
@router.get("/chat/sessions")
async def get_chat_sessions(chat_service: ChatService = Depends(get_chat_service)):
    """
    获取所有会话信息
    """
    try:
        sessions = chat_service.get_chat_sessions()
        return success_response(data={"sessions": sessions})
    except Exception as e:
        return error_response(message="无法获取会话信息", code=5011)

@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    删除指定会话
    """
    try:
        success = chat_service.delete_chat_session(session_id)
        if not success:
            return error_response(message="会话未找到", code=4004)
        return success_response(message="会话已删除")
    except Exception as e:
        return error_response(message="无法删除会话", code=5012)

@router.post("/chat/sessions/clear")
async def clear_all_sessions(chat_service: ChatService = Depends(get_chat_service)):
    """
    清空所有会话
    """
    try:
        chat_service.clear_all_sessions()
        return success_response(message="所有会话已清空")
    except Exception as e:
        return error_response(message="无法清空会话", code=5013)

@router.post("/chat/history")
async def get_chat_history(
    request: ChatHistoryRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    获取会话历史记录
    """
    try:
        result = chat_service.get_chat_history(request.session_id)
        return success_response(data=result)
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5014)