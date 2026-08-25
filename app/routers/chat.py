"""
聊天功能路由
提供聊天对话相关的API接口
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Security
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user, http_bearer
from app.dao.chat_dao import ChatDAO
from app.services.db import SessionLocal
from app.utils.config import config
from app.utils.dependencies import (
    get_chat_service,
    get_db,
    get_mcp_service,
    get_model_service,
)
from app.utils.errors import safe_error_message
from app.utils.models import (
    ChatHistoryResponse,
    ChatInitResponse,
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    RenameSessionRequest,
    SessionsResponse,
    StandardResponse,
)
from app.utils.response import error_response, success_response

from ..services.chat_service import ChatService
from ..services.mcp_service import MCPService
from ..services.model_service import ModelService

logger = logging.getLogger(__name__)

router = APIRouter()

# 初始化 DAO 实例
chat_dao = ChatDAO()


@router.post("/chat", response_model=StandardResponse[ChatResponse], tags=["聊天对话"])
async def chat_with_agent(
    request: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Security(http_bearer),
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    model_service: ModelService = Depends(get_model_service),
    mcp_service: MCPService = Depends(
        get_mcp_service
    ),  # 用于FastAPI的依赖注入系统，确保MCP服务在调用时可用
    db: Session = Depends(get_db),
):
    """
    聊天对话（支持记忆、向量数据库 RAG 和 MCP 工具）

    use_memory=true 时 session_id 可省略：未提供或不存在时自动创建新会话，
    并在响应中返回新 session_id（无需先调用 /chat/init）。
    """
    request_id = uuid.uuid4().hex
    started_at = datetime.now()
    run_created = False

    try:
        # 验证聊天模型是否存在
        chat_model_name = (
            request.chat_model_name or model_service.get_default_chat_model()
        )
        if not model_service.validate_chat_model(chat_model_name):
            return error_response(
                message=f"Chat model '{chat_model_name}' is not available", code=4000
            )

        # 处理会话和记忆
        session_id = None
        history = None

        if request.use_memory:
            if request.session_id and chat_service.session_exists(
                request.session_id, db=db, user_id=current_user.user_id
            ):
                # 已有会话：加载历史对话，保持原行为
                session_id = request.session_id
                chat_service.update_session_activity(session_id, current_user.user_id)
                history = chat_service.get_conversation_history(
                    session_id, db=db, user_id=current_user.user_id
                )

                # 保存会话到数据库
                chat_dao.save_session(
                    db,
                    session_id,
                    user_id=current_user.user_id,
                    chat_model_name=chat_model_name,
                )
            else:
                # 未提供或会话不存在：自动创建（调试友好，无需先调 /chat/init）
                session_id = request.session_id or str(uuid.uuid4())
                chat_service.create_session(
                    session_id=session_id, db=db, user_id=current_user.user_id
                )
                chat_dao.save_session(
                    db,
                    session_id,
                    user_id=current_user.user_id,
                    chat_model_name=chat_model_name,
                )
                logger.info("自动创建新会话: session_id=%s", session_id)

        # 先落库用户消息和运行状态。后续 MCP 超时、异常或取消时，用户输入仍可恢复。
        user_message_id = None
        if request.use_memory and session_id:
            user_message_id = chat_dao.save_message(
                db,
                session_id,
                "user",
                request.query,
                user_id=current_user.user_id,
            )
        chat_dao.create_chat_run(
            db,
            request_id,
            session_id,
            user_message_id,
            user_id=current_user.user_id,
        )
        run_created = True
        logger.info(
            "聊天请求已开始: request_id=%s session_id=%s use_memory=%s",
            request_id,
            session_id,
            request.use_memory,
        )

        # 获取MCP工具（使用依赖注入的服务，已在应用启动时初始化）
        mcp_tools = []
        if mcp_service.is_mcp_initialized():
            token = credentials.credentials if credentials else None
            if token:
                mcp_tools = await mcp_service.get_mcp_tools_for_token(token)
            else:
                mcp_tools = []
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
            request_id=request_id,
            db=db,
            tool_db_factory=SessionLocal,
            timeout_seconds=config.MCP_AGENT_TIMEOUT_SECONDS,
            user_id=current_user.user_id,
        )

        # 如果使用记忆功能，保存对话记录到记忆和数据库
        if request.use_memory and session_id:
            chat_service.ensure_session_title(
                session_id,
                request.query,
                db,
                user_id=current_user.user_id,
            )
            chat_service.add_to_memory(
                session_id,
                request.query,
                result["response"],
                db=db,
                user_id=current_user.user_id,
            )
            # 同时将AI回复写入数据库
            chat_dao.save_message(
                db,
                session_id,
                "assistant",
                result["response"],
                user_id=current_user.user_id,
            )
            result["message_count"] = (
                len(
                    chat_service.get_conversation_history(
                        session_id, db=db, user_id=current_user.user_id
                    )
                )
                // 2
            )

        chat_dao.finish_chat_run(
            db, request_id, "succeeded", started_at, user_id=current_user.user_id
        )
        return success_response(data=result)
    except asyncio.TimeoutError as e:
        if run_created:
            chat_dao.finish_chat_run(
                db,
                request_id,
                "timed_out",
                started_at,
                e,
                user_id=current_user.user_id,
            )
        logger.error(
            "聊天请求超时: request_id=%s timeout_seconds=%s",
            request_id,
            config.MCP_AGENT_TIMEOUT_SECONDS,
        )
        return error_response(message="Chat request timed out", code=5010)
    except asyncio.CancelledError as e:
        if run_created:
            chat_dao.finish_chat_run(
                db,
                request_id,
                "cancelled",
                started_at,
                e,
                user_id=current_user.user_id,
            )
        logger.warning("聊天请求已取消: request_id=%s", request_id)
        raise
    except ValueError as e:
        if run_created:
            chat_dao.finish_chat_run(
                db,
                request_id,
                "failed",
                started_at,
                e,
                user_id=current_user.user_id,
            )
        return error_response(message=str(e), code=4000)
    except Exception as e:
        if run_created:
            chat_dao.finish_chat_run(
                db,
                request_id,
                "failed",
                started_at,
                e,
                user_id=current_user.user_id,
            )
        logger.exception("聊天处理异常: request_id=%s", request_id)
        return error_response(
            message=safe_error_message(e, fallback="Chat request failed"), code=5010
        )


def _sse_payload(event: Dict) -> str:
    """将事件序列化为 SSE data 帧。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _resolve_stream_mcp_tools(
    request: ChatStreamRequest,
    credentials: Optional[HTTPAuthorizationCredentials],
    mcp_service: MCPService,
) -> List:
    """Resolve MCP tools for the streaming endpoint without changing /chat."""
    if request.use_mcp is False:
        if request.mcp_servers is not None:
            raise ValueError("mcp_servers requires use_mcp=true")
        return []

    if request.mcp_servers is not None and request.use_mcp is not True:
        raise ValueError("mcp_servers requires use_mcp=true")

    explicit_mcp = request.use_mcp is True
    if not mcp_service.is_mcp_initialized():
        if explicit_mcp:
            raise RuntimeError("MCP service is not initialized")
        return []

    token = credentials.credentials if credentials else None
    if not explicit_mcp and not token:
        return []

    return await mcp_service.get_mcp_tools_for_token(
        token,
        server_names=request.mcp_servers,
        raise_on_error=explicit_mcp,
    )


@router.post("/chat/stream", tags=["聊天对话"])
async def chat_stream(
    request: ChatStreamRequest,
    credentials: HTTPAuthorizationCredentials = Security(http_bearer),
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    model_service: ModelService = Depends(get_model_service),
    mcp_service: MCPService = Depends(get_mcp_service),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    聊天对话（SSE 流式）— 支持记忆、向量数据库 RAG 和 MCP 工具

    use_memory=true 时 session_id 可省略：未提供或不存在时自动创建新会话，
    并在 done 事件中返回新 session_id（无需先调用 /chat/init）。

    事件格式：
        data: {"type": "text", "content": "..."}    增量文本
        data: {"type": "tool", "name": "..."}      工具调用
        data: {"type": "done", "response": "...",
               "session_id": "...", "message_count": n}  结束
        data: {"type": "error", "code": ..., "message": "..."}  错误
    """
    request_id = uuid.uuid4().hex
    started_at = datetime.now()
    run_created = False
    session_id = None
    history = None

    # 验证聊天模型是否存在
    chat_model_name = request.chat_model_name or model_service.get_default_chat_model()
    if not model_service.validate_chat_model(chat_model_name):
        return error_response(message=f"聊天模型 '{chat_model_name}' 不可用", code=4000)

    try:
        # 处理会话和记忆
        if request.use_memory:
            if request.session_id and chat_service.session_exists(
                request.session_id, db=db, user_id=current_user.user_id
            ):
                # 已有会话：加载历史对话，保持原行为
                session_id = request.session_id
                chat_service.update_session_activity(session_id, current_user.user_id)
                history = chat_service.get_conversation_history(
                    session_id, db=db, user_id=current_user.user_id
                )

                # 保存会话到数据库
                chat_dao.save_session(
                    db,
                    session_id,
                    user_id=current_user.user_id,
                    chat_model_name=chat_model_name,
                )
            else:
                # 未提供或会话不存在：自动创建（调试友好，无需先调 /chat/init）
                session_id = request.session_id or str(uuid.uuid4())
                chat_service.create_session(
                    session_id=session_id, db=db, user_id=current_user.user_id
                )
                chat_dao.save_session(
                    db,
                    session_id,
                    user_id=current_user.user_id,
                    chat_model_name=chat_model_name,
                )
                logger.info("自动创建新会话: session_id=%s", session_id)

        # 先落库用户消息和运行状态
        user_message_id = None
        if request.use_memory and session_id:
            user_message_id = chat_dao.save_message(
                db,
                session_id,
                "user",
                request.query,
                user_id=current_user.user_id,
            )
        chat_dao.create_chat_run(
            db,
            request_id,
            session_id,
            user_message_id,
            user_id=current_user.user_id,
        )
        run_created = True
        logger.info(
            "流式聊天请求已开始: request_id=%s session_id=%s use_memory=%s",
            request_id,
            session_id,
            request.use_memory,
        )

        # 仅流式接口支持按请求控制 MCP；普通 /chat 保持旧逻辑不变。
        mcp_tools = await _resolve_stream_mcp_tools(request, credentials, mcp_service)
        logger.info(
            "流式 MCP 选择: request_id=%s use_mcp=%s servers=%s tool_count=%s",
            request_id,
            request.use_mcp,
            request.mcp_servers or "<all>",
            len(mcp_tools),
        )
        if mcp_tools:
            logger.info(f"MCP 工具列表: {[tool.name for tool in mcp_tools]}")

        timeout_seconds = config.MCP_AGENT_TIMEOUT_SECONDS

        async def event_generator():
            """SSE 事件生成器：流转 + 结束落库（与 /chat 行为一致）。"""
            final_response = ""
            message_count = None
            terminal_recorded = False

            def record_run(status: str, error: Optional[object] = None):
                nonlocal terminal_recorded
                if terminal_recorded:
                    return
                terminal_recorded = True
                chat_dao.finish_chat_run(
                    db,
                    request_id,
                    status,
                    started_at,
                    error,
                    user_id=current_user.user_id,
                )

            try:
                iterator = chat_service.chat_stream(
                    prompt=request.prompt,
                    query=request.query,
                    chat_model_name=chat_model_name,
                    session_id=session_id,
                    use_memory=request.use_memory,
                    history=history,
                    db_name=request.db_name,
                    mcp_tools=mcp_tools,
                    request_id=request_id,
                    db=db,
                    tool_db_factory=SessionLocal,
                    timeout_seconds=timeout_seconds,
                    user_id=current_user.user_id,
                ).__aiter__()

                while True:
                    try:
                        if timeout_seconds is not None:
                            event = await asyncio.wait_for(
                                iterator.__anext__(), timeout=timeout_seconds
                            )
                        else:
                            event = await iterator.__anext__()
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        record_run("timed_out")
                        logger.error(
                            "流式聊天请求超时: request_id=%s timeout_seconds=%s",
                            request_id,
                            timeout_seconds,
                        )
                        yield _sse_payload(
                            {"type": "error", "code": 5010, "message": "聊天调用超时"}
                        )
                        return

                    if event["type"] == "text":
                        final_response += event["content"]
                        yield _sse_payload(event)
                    elif event["type"] == "tool":
                        yield _sse_payload(event)

                # 流结束：落库 AI 回复（与 /chat 行为一致）
                if request.use_memory and session_id:
                    chat_service.ensure_session_title(
                        session_id,
                        request.query,
                        db,
                        user_id=current_user.user_id,
                    )
                    chat_service.add_to_memory(
                        session_id,
                        request.query,
                        final_response,
                        db=db,
                        user_id=current_user.user_id,
                    )
                    chat_dao.save_message(
                        db,
                        session_id,
                        "assistant",
                        final_response,
                        user_id=current_user.user_id,
                    )
                    message_count = (
                        len(
                            chat_service.get_conversation_history(
                                session_id, db=db, user_id=current_user.user_id
                            )
                        )
                        // 2
                    )

                record_run("succeeded")
                yield _sse_payload(
                    {
                        "type": "done",
                        "response": final_response,
                        "session_id": session_id,
                        "message_count": message_count,
                    }
                )
            except asyncio.CancelledError:
                record_run("cancelled")
                logger.warning("流式聊天请求已取消: request_id=%s", request_id)
                raise
            except ValueError as e:
                record_run("failed", e)
                yield _sse_payload({"type": "error", "code": 4000, "message": str(e)})
            except Exception as e:
                record_run("failed", e)
                logger.exception("流式聊天处理异常: request_id=%s", request_id)
                yield _sse_payload(
                    {
                        "type": "error",
                        "code": 5010,
                        "message": safe_error_message(e, fallback="聊天调用失败"),
                    }
                )
            finally:
                if not terminal_recorded:
                    record_run("cancelled")

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                # no-transform: 让 Express/compression 中间件跳过 gzip，
                # 否则 gzip 会攒块缓冲，浏览器只能一次性收到整段流
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    except Exception as e:
        if run_created:
            chat_dao.finish_chat_run(
                db,
                request_id,
                "failed",
                started_at,
                e,
                user_id=current_user.user_id,
            )
        logger.exception("流式聊天初始化失败: request_id=%s", request_id)
        return error_response(
            message=safe_error_message(e, fallback="聊天调用失败"), code=5010
        )


@router.get(
    "/chat/init",
    response_model=StandardResponse[ChatInitResponse],
    tags=["聊天对话"],
    deprecated=True,
)
async def init_chat_service(
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db),
):
    """
    初始化聊天服务并创建新会话

    .. deprecated::
        /chat 与 /chat/stream 已支持 use_memory=true 时自动创建会话
        （省略 session_id 即可，响应中返回新 session_id）。
        本接口仅用于显式创建空会话（如“新建对话”），不再是对话的前置条件。
    """
    try:
        # 创建新会话
        session_id = chat_service.create_session(user_id=current_user.user_id, db=db)

        logger.debug(f"在内存中创建会话: {session_id}")

        # 使用 DAO 在数据库中创建会话记录
        chat_dao.save_session(db, session_id, user_id=current_user.user_id)

        logger.debug(f"在数据库中创建会话: {session_id}")

        return success_response(
            data={"session_id": session_id}, message="聊天服务已初始化"
        )
    except Exception as e:
        logger.error(f"创建会话错误: {e}")
        return error_response(
            message=f"Failed to initialize chat service: {safe_error_message(e)}",
            code=5015,
        )


@router.get(
    "/chat/sessions",
    response_model=StandardResponse[SessionsResponse],
    tags=["聊天对话"],
)
async def get_chat_sessions(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    获取所有会话信息
    """
    try:
        # 从数据库获取持久化的会话
        db_sessions = chat_dao.get_all_sessions(db, user_id=current_user.user_id)

        sessions_list = []
        for session in db_sessions:
            if not session.get("title"):
                session["title"] = chat_service.default_session_title
            sessions_list.append(session)

        return success_response(data={"sessions": sessions_list})
    except Exception as e:
        logger.error(f"获取会话信息失败: {e}")
        return error_response(
            message=f"Failed to fetch chat sessions: {safe_error_message(e)}", code=5011
        )


@router.delete(
    "/chat/sessions/{session_id}",
    response_model=StandardResponse[None],
    tags=["聊天对话"],
)
async def delete_chat_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    删除指定会话
    """
    try:
        # 从内存中删除会话
        memory_deleted = chat_service.delete_chat_session(
            session_id, db=db, user_id=current_user.user_id
        )

        # 从数据库中删除会话
        db_deleted = chat_dao.delete_session(
            db, session_id, user_id=current_user.user_id
        )

        if not memory_deleted and not db_deleted:
            return error_response(message="Session not found", code=4004)

        return success_response(message="会话已删除")
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        return error_response(
            message=f"Failed to delete chat session: {safe_error_message(e)}", code=5012
        )


@router.post(
    "/chat/sessions/clear", response_model=StandardResponse[None], tags=["聊天对话"]
)
async def clear_all_sessions(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    清空所有会话
    """
    try:
        # 清空内存中的会话
        chat_service.clear_all_sessions(db=db, user_id=current_user.user_id)

        # 清空数据库中的会话
        chat_dao.clear_all_sessions(db, user_id=current_user.user_id)

        return success_response(message="所有会话已清空")
    except Exception as e:
        logger.error(f"清空会话失败: {e}")
        return error_response(
            message=f"Failed to clear chat sessions: {safe_error_message(e)}", code=5013
        )


@router.post(
    "/chat/sessions/{session_id}/rename",
    response_model=StandardResponse[None],
    tags=["聊天对话"],
)
async def rename_chat_session(
    session_id: str,
    request: RenameSessionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    重命名指定会话
    """
    try:
        title = request.title.strip()
        if not title:
            return error_response(message="会话标题不能为空", code=4002)

        renamed = chat_dao.update_session_title(
            db, session_id, title, user_id=current_user.user_id
        )

        if not renamed:
            return error_response(message="Session not found", code=4004)

        return success_response(message="会话已重命名")
    except Exception as e:
        logger.error(f"重命名会话失败: {e}")
        return error_response(
            message=f"Failed to rename chat session: {safe_error_message(e)}", code=5014
        )


@router.get(
    "/chat/sessions/{session_id}/history",
    response_model=StandardResponse[ChatHistoryResponse],
    tags=["聊天对话"],
)
async def get_chat_history_by_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    获取会话历史记录（推荐 GET 接口）
    """
    return await _get_chat_history_internal(
        session_id,
        db,
        user_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )


async def _get_chat_history_internal(
    session_id: str,
    db: Session,
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """Build chat history response payload."""
    try:
        if not session_id:
            raise ValueError("session_id is required")

        session_info = chat_dao.get_session(db, session_id, user_id=user_id)

        if not session_info:
            raise ValueError("Session not found")

        created_at = session_info.get("created_at")
        title = session_info.get("title") or "New Chat"
        full_history = chat_dao.get_session_history(db, session_id, user_id=user_id)
        paged_messages = full_history[offset : offset + limit]

        messages = []
        for msg in paged_messages:
            message_item = {
                "message_id": msg.get("message_id"),
                "role": msg.get("role"),
                "content": msg.get("content"),
                "created_at": msg.get("created_at"),
            }

            if msg.get("role") == "assistant":
                message_item["sources"] = []
                message_item["tool_calls"] = None

            messages.append(message_item)

        response_data = {
            "session": {
                "session_id": session_id,
                "title": title,
                "chat_model_name": session_info.get("chat_model_name"),
                "created_at": (
                    created_at.isoformat()
                    if hasattr(created_at, "isoformat")
                    else created_at
                ),
                "message_count": len(full_history),
            },
            "messages": messages,
        }

        return success_response(data=response_data)

    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        return error_response(
            message=f"Failed to fetch chat history: {safe_error_message(e)}", code=5014
        )
