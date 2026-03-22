"""
聊天功能路由
提供聊天对话相关的API接口
"""

import logging

from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.dao.chat_dao import ChatDAO
from app.utils.dependencies import (
    get_chat_service,
    get_db,
    get_mcp_service,
    get_model_service,
)
from app.utils.models import (
    ChatHistoryRequest,
    ChatHistoryResponse,
    ChatInitResponse,
    ChatRequest,
    ChatResponse,
    SessionsResponse,
    StandardResponse,
)
from app.utils.response import error_response, success_response

from ..services.chat_service import ChatService
from ..services.mcp_service import MCPService
from ..services.model_service import ModelService

logger = logging.getLogger(__name__)

router = APIRouter()

# Optional Bearer auth parser for incoming chat requests.
# auto_error=False keeps the endpoint backward-compatible for callers without token.
http_bearer = HTTPBearer(auto_error=False)


# 初始化 DAO 实例
chat_dao = ChatDAO()


@router.post("/chat", response_model=StandardResponse[ChatResponse], tags=["聊天对话"])
async def chat_with_agent(
    request: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Security(http_bearer),
    chat_service: ChatService = Depends(get_chat_service),
    model_service: ModelService = Depends(get_model_service),
    mcp_service: MCPService = Depends(
        get_mcp_service
    ),  # 用于FastAPI的依赖注入系统，确保MCP服务在调用时可用
    db: Session = Depends(get_db),
):
    """
    聊天对话（支持记忆、向量数据库 RAG 和 MCP 工具）
    """
    try:
        # 验证聊天模型是否存在
        chat_model_name = (
            request.chat_model_name or model_service.get_default_chat_model()
        )
        if not model_service.validate_chat_model(chat_model_name):
            return error_response(
                message=f"聊天模型 '{chat_model_name}' 不可用", code=4000
            )

        # 处理会话和记忆
        session_id = None
        history = None

        if request.use_memory:
            # 检查是否提供了session_id
            if not request.session_id:
                return error_response(
                    message="使用记忆功能时必须提供session_id", code=4000
                )

            # 验证会话是否存在
            if not chat_service.session_exists(request.session_id):
                return error_response(message="会话不存在，请先创建会话", code=4004)

            # 获取历史对话
            session_id = request.session_id
            chat_service.update_session_activity(session_id)
            history = chat_service.get_conversation_history(session_id)

            # 保存会话到数据库
            if session_id:
                chat_dao.save_session(db, session_id)

        # 获取MCP工具（使用依赖注入的服务，已在应用启动时初始化）
        mcp_tools = []
        if mcp_service.is_mcp_initialized():
            token = credentials.credentials if credentials else None
            if token:
                mcp_tools = await mcp_service.get_mcp_tools_for_token(token)
            else:
                mcp_tools = mcp_service.get_mcp_tools() or []
            logger.info(f"获取到 {len(mcp_tools)} 个 MCP 工具")
            if mcp_tools:
                logger.info(f"MCP 工具列表: {[tool.name for tool in mcp_tools]}")

        # 调用 ChatService 进行对话（新增支持 db_name）
        result = await chat_service.chat_with_agent(
            prompt=request.prompt,
            query=request.query,
            chat_model_name=chat_model_name,
            session_id=session_id,
            use_memory=request.use_memory,
            history=history,
            db_name=request.db_name,  # 新增：传递知识库名称
            mcp_tools=mcp_tools,  # 新增：传递 MCP 工具
        )

        # 如果使用记忆功能，保存对话记录到记忆和数据库
        if request.use_memory and session_id:
            chat_dao.save_message(db, session_id, "user", request.query)
            chat_service.add_to_memory(session_id, request.query, result["response"])
            # 同时将AI回复写入数据库
            chat_dao.save_message(db, session_id, "assistant", result["response"])
            logger.debug(f"准备保存消息到会话 {session_id}: {request.query[:50]}...")
            result["message_count"] = (
                len(chat_service.get_conversation_history(session_id)) // 2
            )

        return success_response(data=result)
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        logger.error(f"聊天处理异常: {e}")
        return error_response(message=str(e), code=5010)


@router.get(
    "/chat/init", response_model=StandardResponse[ChatInitResponse], tags=["聊天对话"]
)
async def init_chat_service(
    chat_service: ChatService = Depends(get_chat_service), db: Session = Depends(get_db)
):
    """
    初始化聊天服务并创建新会话
    """
    try:
        # 创建新会话
        session_id = chat_service.create_session()

        logger.debug(f"在内存中创建会话: {session_id}")

        # 使用 DAO 在数据库中创建会话记录
        chat_dao.save_session(db, session_id)

        logger.debug(f"在数据库中创建会话: {session_id}")

        return success_response(
            data={"session_id": session_id}, message="聊天服务已初始化"
        )
    except Exception as e:
        logger.error(f"创建会话错误: {e}")
        return error_response(message=f"无法初始化聊天服务: {str(e)}", code=5015)


@router.get(
    "/chat/sessions",
    response_model=StandardResponse[SessionsResponse],
    tags=["聊天对话"],
)
async def get_chat_sessions(
    db: Session = Depends(get_db), chat_service: ChatService = Depends(get_chat_service)
):
    """
    获取所有会话信息
    """
    try:
        # 从数据库获取持久化的会话
        db_sessions = chat_dao.get_all_sessions(db)

        # 合并会话信息并转换为字典格式
        sessions_dict = {}
        for session in db_sessions:
            session_id = session["session_id"]
            # 使用session_id作为键，session信息作为值
            sessions_dict[session_id] = session

        return success_response(data={"sessions": sessions_dict})
    except Exception as e:
        logger.error(f"获取会话信息失败: {e}")
        return error_response(message=f"无法获取会话信息: {str(e)}", code=5011)


@router.delete(
    "/chat/sessions/{session_id}",
    response_model=StandardResponse[None],
    tags=["聊天对话"],
)
async def delete_chat_session(
    session_id: str,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    删除指定会话
    """
    try:
        # 从内存中删除会话
        memory_deleted = chat_service.delete_chat_session(session_id)

        # 从数据库中删除会话
        db_deleted = chat_dao.delete_session(db, session_id)

        if not memory_deleted and not db_deleted:
            return error_response(message="会话未找到", code=4004)

        return success_response(message="会话已删除")
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        return error_response(message=f"无法删除会话: {str(e)}", code=5012)


@router.post(
    "/chat/sessions/clear", response_model=StandardResponse[None], tags=["聊天对话"]
)
async def clear_all_sessions(
    db: Session = Depends(get_db), chat_service: ChatService = Depends(get_chat_service)
):
    """
    清空所有会话
    """
    try:
        # 清空内存中的会话
        chat_service.clear_all_sessions()

        # 清空数据库中的会话
        chat_dao.clear_all_sessions(db)

        return success_response(message="所有会话已清空")
    except Exception as e:
        logger.error(f"清空会话失败: {e}")
        return error_response(message=f"无法清空会话: {str(e)}", code=5013)


@router.post(
    "/chat/history",
    response_model=StandardResponse[ChatHistoryResponse],
    tags=["聊天对话"],
)
async def get_chat_history(
    request: ChatHistoryRequest,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    获取会话历史记录
    """
    try:
        session_id = request.session_id
        if not session_id:
            raise ValueError("session_id is required")

        # 获取会话信息
        sessions = chat_dao.get_all_sessions(db)
        session_info = next(
            (s for s in sessions if s["session_id"] == session_id), None
        )

        if not session_info:
            raise ValueError("Session not found")

        created_at = session_info.get("created_at")
        last_active = session_info.get("last_active", created_at)

        # 从数据库获取历史记录
        history = chat_dao.get_session_history(db, session_id)

        # 确保返回所有必需的字段
        response_data = {
            "session_id": session_id,
            "history": history,
            "created_at": (
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else created_at
            ),
            "last_active": (
                last_active.isoformat()
                if hasattr(last_active, "isoformat")
                else last_active
            ),
        }

        return success_response(data=response_data)

    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        return error_response(message=f"无法获取历史记录: {str(e)}", code=5014)
