"""
聊天服务
负责聊天会话管理和对话记忆功能
"""

import asyncio
import os
import re
import uuid
from datetime import datetime
from typing import AsyncIterator, Callable, Dict, List, Optional

from langchain.memory import ConversationBufferMemory
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain.schema.messages import BaseMessage
from langchain_core.runnables import RunnableLambda
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from sqlalchemy.orm import Session

from ..dao.chat_dao import ChatDAO
from ..utils.config import config
from ..utils.handler import MCPToolLoggingHandler
from .base_service import BaseService
from .database_service import DatabaseService


class ChatService(BaseService):
    """聊天服务类"""

    def __init__(
        self,
        db_session: Optional[Session] = None,
        database_service: Optional[DatabaseService] = None,
    ):
        """
        初始化聊天服务

        Args:
            db_session: 可选的数据库会话，用于测试或外部事务管理
            database_service: 可选的数据库服务实例，用于向量数据库访问
        """
        super().__init__()
        self.chat_sessions = {}  # 内存中的会话缓存
        self.max_sessions = 100  # 最大内存会话数
        self.max_memory_length = 20  # 每个会话最大记忆轮次
        self.dao = ChatDAO()
        self._db_session = db_session
        self._database_service = database_service  # 新增：DatabaseService 依赖注入
        self.default_session_title = "New Chat"
        self.max_session_title_length = 30

    @staticmethod
    def _session_key(user_id: Optional[str], session_id: str):
        """Keep in-memory conversation state isolated by authenticated user."""
        return user_id, session_id

    def _get_db(self) -> Session:
        """获取数据库会话"""
        if self._db_session:
            return self._db_session
        # 如果没有提供会话，则从依赖注入获取
        from ..services.db import SessionLocal

        return SessionLocal()

    def create_session(
        self,
        session_id: str = None,
        db: Optional[Session] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        创建或获取会话

        Args:
            session_id: 可选的会话ID，如果为None则创建新会话
            db: 可选的数据库会话

        Returns:
            会话ID
        """
        db = db or self._get_db()

        if session_id is None:
            session_id = str(uuid.uuid4())

        session_key = self._session_key(user_id, session_id)
        if session_key not in self.chat_sessions:
            # 检查会话数量限制
            if len(self.chat_sessions) >= self.max_sessions:
                self._cleanup_old_sessions()

            # 创建新会话
            memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                max_token_limit=4000,
            )

            self.chat_sessions[session_key] = {
                "memory": memory,
                "created_at": datetime.now(),
                "last_active": datetime.now(),
                "message_count": 0,
            }

            # 确保会话在数据库中存在
            try:
                self.dao.save_session(db, session_id, title=None, user_id=user_id)
                db.commit()
            except Exception as e:
                db.rollback()
                self.log_error(f"保存会话到数据库失败: {e}")

            self.log_info(f"创建新会话: {session_id}")

        return session_id

    def generate_session_title(self, query: str) -> str:
        """Generate a short title from the first user query."""
        if not query:
            return self.default_session_title

        normalized = re.sub(r"\s+", " ", query).strip()
        if not normalized:
            return self.default_session_title

        if len(normalized) > self.max_session_title_length:
            return normalized[: self.max_session_title_length].rstrip()

        return normalized

    def ensure_session_title(
        self,
        session_id: str,
        query: str,
        db: Optional[Session] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Set session title once if it is currently missing."""
        db = db or self._get_db()

        session_info = self.dao.get_session(db, session_id, user_id=user_id)
        if not session_info:
            return self.default_session_title

        existing_title = (session_info.get("title") or "").strip()
        if existing_title:
            return existing_title

        generated_title = self.generate_session_title(query)
        self.dao.update_session_title(db, session_id, generated_title, user_id=user_id)
        return generated_title

    def _cleanup_old_sessions(self):
        """清理最老的会话"""
        if not self.chat_sessions:
            return

        # 按最后活跃时间排序，删除最老的会话
        sorted_sessions = sorted(
            self.chat_sessions.items(), key=lambda x: x[1]["last_active"]
        )

        # 删除最老的10个会话或25%，取较大值
        cleanup_count = max(10, len(self.chat_sessions) // 4)
        for session_id, _ in sorted_sessions[:cleanup_count]:
            del self.chat_sessions[session_id]
            self.log_info(f"清理旧会话: {session_id}")

    def update_session_activity(self, session_id: str, user_id: Optional[str] = None):
        """
        更新会话活跃时间

        Args:
            session_id: 会话ID
        """
        session_key = self._session_key(user_id, session_id)
        if session_key in self.chat_sessions:
            self.chat_sessions[session_key]["last_active"] = datetime.now()

    def add_to_memory(
        self,
        session_id: str,
        human_message: str,
        ai_message: str,
        db: Optional[Session] = None,
        user_id: Optional[str] = None,
    ):
        """
        添加对话到记忆中

        Args:
            session_id: 会话ID
            human_message: 用户消息
            ai_message: AI回复消息
            db: 可选的数据库会话
        """
        db = db or self._get_db()

        # 确保会话存在
        session_key = self._session_key(user_id, session_id)
        if session_key not in self.chat_sessions:
            self.create_session(session_id, db, user_id=user_id)

        if session_key in self.chat_sessions:
            session = self.chat_sessions[session_key]
            memory = session["memory"]

            try:
                # 添加到内存
                memory.chat_memory.add_user_message(human_message)
                memory.chat_memory.add_ai_message(ai_message)

                # 更新消息计数
                session["message_count"] += 1
                session["last_active"] = datetime.now()

                # 如果消息数量超过限制，删除最早的消息
                if session["message_count"] > self.max_memory_length:
                    messages = memory.chat_memory.messages
                    if len(messages) > 4:  # 至少保留2轮对话
                        memory.chat_memory.messages = messages[2:]  # 删除最早的一轮对话
                        session["message_count"] -= 1

                self.log_info(f"会话 {session_id} 添加对话记录")

            except Exception as e:
                db.rollback()
                self.log_error(f"保存消息失败: {e}")

    def get_conversation_history(
        self,
        session_id: str,
        db: Optional[Session] = None,
        user_id: Optional[str] = None,
    ) -> List[BaseMessage]:
        """
        获取会话历史

        Args:
            session_id: 会话ID
            db: 可选的数据库会话

        Returns:
            会话历史消息列表
        """
        db = db or self._get_db()

        try:
            history = []
            db_messages = self.dao.get_session_history(db, session_id, user_id=user_id)

            for msg in db_messages:
                role = msg.get("role", "").lower()
                content = msg.get("content", "")

                if role == "user":
                    history.append(HumanMessage(content=content))
                elif role == "assistant":
                    history.append(AIMessage(content=content))
                elif role == "system":
                    history.append(SystemMessage(content=content))

            # 如果从数据库加载到消息，更新内存缓存
            if history:
                self._load_session_from_db(user_id, session_id, history, db)

            return history

        except Exception as e:
            self.log_error(f"从数据库加载会话历史失败: {e}")
            return []

    def _load_session_from_db(
        self,
        user_id: Optional[str],
        session_id: str,
        messages: List[BaseMessage],
        db: Session,
    ):
        """从数据库加载会话到内存"""
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            max_token_limit=4000,
        )

        # 添加历史消息到内存
        for msg in messages:
            if isinstance(msg, HumanMessage):
                memory.chat_memory.add_user_message(msg.content)
            elif isinstance(msg, AIMessage):
                memory.chat_memory.add_ai_message(msg.content)
            elif isinstance(msg, SystemMessage):
                memory.save_context({"system": msg.content}, {"output": ""})

        # 更新内存中的会话
        self.chat_sessions[self._session_key(user_id, session_id)] = {
            "memory": memory,
            "created_at": datetime.now(),  # 使用当前时间，或可以从数据库获取
            "last_active": datetime.now(),
            "message_count": len(messages) // 2,  # 假设每条用户消息都有一条AI回复
        }

    def delete_chat_session(
        self,
        session_id: str,
        db: Optional[Session] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        删除指定会话

        Args:
            session_id: 会话ID
            db: 可选的数据库会话

        Returns:
            是否删除成功
        """
        db = db or self._get_db()
        deleted = False

        # 从数据库中删除
        try:
            db_deleted = self.dao.delete_session(db, session_id, user_id=user_id)
            if db_deleted:
                db.commit()
                deleted = True
                self.chat_sessions.pop(self._session_key(user_id, session_id), None)
                self.log_info(f"从数据库中删除会话: {session_id}")
        except Exception as e:
            db.rollback()
            self.log_error(f"从数据库删除会话失败: {e}")

        if not deleted:
            self.log_warning(f"要删除的会话不存在: {session_id}")

        return deleted

    def clear_all_sessions(
        self, db: Optional[Session] = None, user_id: Optional[str] = None
    ):
        """
        清空所有会话

        Args:
            db: 可选的数据库会话
        """
        db = db or self._get_db()

        # 清空数据库中的会话
        try:
            self.dao.clear_all_sessions(db, user_id=user_id)
            db.commit()
            if user_id is None:
                self.chat_sessions.clear()
            else:
                for session_key in list(self.chat_sessions):
                    if session_key[0] == user_id:
                        self.chat_sessions.pop(session_key, None)
            self.log_info("清空数据库中所有会话")
        except Exception as e:
            db.rollback()
            self.log_error(f"清空数据库会话失败: {e}")

    def get_chat_history(
        self,
        session_id: str,
        db: Optional[Session] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """
        获取会话历史记录

        Args:
            session_id: 会话ID
            db: 可选的数据库会话

        Returns:
            格式化的历史记录

        Raises:
            ValueError: 会话不存在
        """
        db = db or self._get_db()

        if not session_id:
            raise ValueError("session_id is required")

        # 获取历史记录
        messages = self.get_conversation_history(session_id, db, user_id=user_id)
        if not messages and not self.session_exists(session_id, db, user_id=user_id):
            raise ValueError("Session not found")

        # 格式化历史记录
        formatted_history = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                formatted_history.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted_history.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                formatted_history.append({"role": "system", "content": msg.content})

        # 获取会话元数据
        created_at = None
        last_active = None
        message_count = len(formatted_history)

        session_key = self._session_key(user_id, session_id)
        if session_key in self.chat_sessions:
            session = self.chat_sessions[session_key]
            created_at = session["created_at"].isoformat()
            last_active = session["last_active"].isoformat()
        else:
            # 尝试从数据库获取元数据
            try:
                sessions = self.dao.get_all_sessions(db, user_id=user_id)
                for s in sessions:
                    if s["session_id"] == session_id:
                        created_at = s.get("created_at")
                        last_active = created_at  # 如果没有最后活跃时间，使用创建时间
                        break
            except Exception as e:
                self.log_error(f"获取会话元数据失败: {e}")

        self.log_info(f"获取会话 {session_id} 历史记录，共 {message_count} 条")

        return {
            "session_id": session_id,
            "history": formatted_history,
            "message_count": message_count,
            "created_at": created_at or datetime.now().isoformat(),
            "last_active": last_active or datetime.now().isoformat(),
        }

    def session_exists(
        self,
        session_id: str,
        db: Optional[Session] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        检查会话是否存在

        Args:
            session_id: 会话ID
            db: 可选的数据库会话

        Returns:
            会话是否存在
        """
        db = db or self._get_db()

        # 检查数据库中是否存在
        try:
            sessions = self.dao.get_all_sessions(db, user_id=user_id)
            return any(s["session_id"] == session_id for s in sessions)
        except Exception as e:
            self.log_error(f"检查会话存在性失败: {e}")
            return False

    def _create_llm(self, chat_model_name: Optional[str] = None):
        """
        创建 LLM 实例

        Args:
            chat_model_name: 聊天模型名称 (可选)

        Returns:
            LLM 实例
        """
        use_api = True
        api_key = os.environ.get("OPENAI_API_KEY")
        api_base = os.environ.get("OPENAI_API_BASE")

        if not chat_model_name:
            chat_model_name = "qwen-turbo-latest"

        if use_api:
            return ChatOpenAI(
                model=chat_model_name,
                temperature=0.1,
                verbose=True,
                api_key=api_key,
                base_url=api_base,
            )
        else:
            return ChatOllama(model=chat_model_name, temperature=0.1, verbose=True)

    @staticmethod
    async def _await_with_timeout(awaitable, timeout_seconds: Optional[float]):
        """Await an operation with Python 3.9-compatible timeout support."""
        if timeout_seconds is None:
            return await awaitable
        return await asyncio.wait_for(awaitable, timeout=timeout_seconds)

    async def chat_with_agent(
        self,
        prompt: str,
        query: str,
        chat_model_name: Optional[str] = None,
        session_id: Optional[str] = None,
        use_memory: Optional[bool] = True,
        history: Optional[List] = None,
        db_name: Optional[str] = None,
        mcp_tools: Optional[List] = None,
        request_id: Optional[str] = None,
        db: Optional[Session] = None,
        tool_db_factory: Optional[Callable[[], Session]] = None,
        timeout_seconds: Optional[float] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """
        智能对话接口 - 支持记忆、向量数据库 RAG 和 MCP 工具

        Args:
            prompt: 系统提示词
            query: 用户查询
            chat_model_name: 聊天模型名称 (可选)
            session_id: 会话ID (可选)
            use_memory: 是否使用记忆功能 (可选，默认True)
            history: 历史对话记录 (可选)
            db_name: 知识库名称 (可选，提供时启用RAG)
            mcp_tools: MCP工具列表 (可选)
            request_id: 请求追踪ID（用于日志和工具审计）
            db: 当前请求的数据库会话（用于工具审计）
            tool_db_factory: 工具审计独立数据库会话工厂
            timeout_seconds: Agent/LLM 调用超时秒数，None 表示不限制

        Returns:
            智能体的回答和会话ID

        Raises:
            ValueError: 参数验证失败
        """
        if not chat_model_name:
            chat_model_name = "qwen-turbo-latest"

        # 验证必要参数
        if not prompt:
            raise ValueError("prompt is required")
        if not query:
            raise ValueError("query is required")

        self.logger.info(
            "开始聊天对话: request_id=%s model=%s session_id=%s",
            request_id,
            chat_model_name,
            session_id,
        )

        try:
            # 1-4. 构建工具列表与消息列表（与 chat_stream 共享）
            tools, messages = self._build_tools_and_messages(
                prompt=prompt,
                query=query,
                use_memory=use_memory,
                history=history,
                db_name=db_name,
                mcp_tools=mcp_tools,
                user_id=user_id,
            )

            # 5. 创建并运行 Agent
            if tools:
                # 使用 Agent 模式
                self.log_info(
                    f"工具列表数量: {len(tools)}, 工具名称: {[t.name for t in tools]}"
                )
                llm = self._create_llm(chat_model_name)
                agent = create_react_agent(llm, tools)
                handler = MCPToolLoggingHandler(
                    self.logger,
                    request_id=request_id,
                    db=db,
                    db_factory=tool_db_factory,
                    user_id=user_id,
                )
                result = await self._await_with_timeout(
                    agent.ainvoke(
                        {"messages": messages},
                        config={
                            "callbacks": [handler],
                            "recursion_limit": config.MCP_AGENT_RECURSION_LIMIT,
                        },
                    ),
                    timeout_seconds,
                )

                ai_response = result["messages"][-1].content
            else:
                # 直接对话模式（不使用工具）
                llm = self._create_llm(chat_model_name)
                response = await self._await_with_timeout(
                    llm.ainvoke(messages), timeout_seconds
                )
                ai_response = response.content

            self.logger.info(
                "聊天对话完成: request_id=%s response_length=%s",
                request_id,
                len(ai_response),
            )

            return {"response": ai_response, "session_id": session_id}

        except Exception:
            self.logger.exception("聊天对话失败: request_id=%s", request_id)
            raise

    def _build_tools_and_messages(
        self,
        prompt: str,
        query: str,
        use_memory: Optional[bool],
        history: Optional[List],
        db_name: Optional[str],
        mcp_tools: Optional[List],
        user_id: Optional[str],
    ) -> tuple[List, List]:
        """构建工具列表与消息列表（chat_with_agent 与 chat_stream 共享）。"""
        # 1. 构建工具列表
        tools = []

        # 2. 如果提供了 db_name，添加检索工具
        if db_name:
            if not self._database_service:
                raise ValueError(
                    "DatabaseService is not initialized; vector database is "
                    "unavailable"
                )

            vector_db = self._database_service.get_vector_db(db_name, user_id=user_id)
            if not vector_db:
                raise ValueError(f"Knowledge base '{db_name}' not found")

            # 创建检索工具
            vector_store = vector_db.get_vector_store()
            retriever = vector_store.as_retriever(
                search_type="similarity", search_kwargs={"k": 2}
            )

            # 将同步检索器包装为异步
            async def async_retrieve(query: str) -> str:
                """异步检索函数"""
                docs = retriever.invoke(query)
                # 将检索结果格式化为字符串
                if docs:
                    return "\n\n".join(
                        [
                            f"【document {i + 1}】\n{doc.page_content}"
                            for i, doc in enumerate(docs)
                        ]
                    )
                return "未找到相关信息"

            # 创建异步检索工具
            retrieval_tool = RunnableLambda(async_retrieve).as_tool(
                name="info_retriever",
                description="信息检索工具，从知识库中查找相关信息。输入：查询问题，输出：相关文档内容。",
            )
            tools.append(retrieval_tool)

        # 3. 添加 MCP 工具（如果提供）
        if mcp_tools:
            tools.extend(mcp_tools)

        # 4. 构建消息列表
        messages = []
        messages.append(SystemMessage(content=prompt))

        if use_memory and history:
            for msg in history:
                messages.append(msg)

        messages.append(HumanMessage(content=query))

        return tools, messages

    async def chat_stream(
        self,
        prompt: str,
        query: str,
        chat_model_name: Optional[str] = None,
        session_id: Optional[str] = None,
        use_memory: Optional[bool] = True,
        history: Optional[List] = None,
        db_name: Optional[str] = None,
        mcp_tools: Optional[List] = None,
        request_id: Optional[str] = None,
        db: Optional[Session] = None,
        tool_db_factory: Optional[Callable[[], Session]] = None,
        timeout_seconds: Optional[float] = None,
        user_id: Optional[str] = None,
    ) -> AsyncIterator[Dict]:
        """
        流式智能对话 - 逐块产出事件（超时由调用方通过 asyncio.wait_for 控制）。

        事件格式：
            {"type": "text", "content": str}   增量文本（前端追加渲染）
            {"type": "tool", "name": str}      工具调用事件（前端展示状态）
        """
        if not chat_model_name:
            chat_model_name = "qwen-turbo-latest"

        if not prompt:
            raise ValueError("prompt is required")
        if not query:
            raise ValueError("query is required")

        tools, messages = self._build_tools_and_messages(
            prompt=prompt,
            query=query,
            use_memory=use_memory,
            history=history,
            db_name=db_name,
            mcp_tools=mcp_tools,
            user_id=user_id,
        )

        llm = self._create_llm(chat_model_name)

        if tools:
            # Agent 模式：逐 token 流式输出，工具事件单独透出
            self.log_info(
                f"工具列表数量: {len(tools)}, 工具名称: {[t.name for t in tools]}"
            )
            agent = create_react_agent(llm, tools)
            handler = MCPToolLoggingHandler(
                self.logger,
                request_id=request_id,
                db=db,
                db_factory=tool_db_factory,
                user_id=user_id,
            )
            async for msg_chunk, _meta in agent.astream(
                {"messages": messages},
                config={
                    "callbacks": [handler],
                    "recursion_limit": config.MCP_AGENT_RECURSION_LIMIT,
                },
                stream_mode="messages",
            ):
                msg_type = getattr(msg_chunk, "type", "")
                content = getattr(msg_chunk, "content", "") or ""
                if msg_type == "tool":
                    yield {
                        "type": "tool",
                        "name": getattr(msg_chunk, "name", None) or "tool",
                    }
                elif content:
                    yield {"type": "text", "content": content}
        else:
            # 直接对话模式（不使用工具）：逐 token 流式
            async for chunk in llm.astream(messages):
                content = getattr(chunk, "content", "") or ""
                if content:
                    yield {"type": "text", "content": content}
