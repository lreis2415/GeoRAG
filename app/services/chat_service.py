"""
聊天服务
负责聊天会话管理和对话记忆功能
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from langchain.memory import ConversationBufferMemory
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain.schema.messages import BaseMessage
from sqlalchemy.orm import Session

from ..dao.chat_dao import ChatDAO
from .base_service import BaseService


class ChatService(BaseService):
    """聊天服务类"""

    def __init__(self, db_session: Optional[Session] = None):
        """
        初始化聊天服务

        Args:
            db_session: 可选的数据库会话，用于测试或外部事务管理
        """
        super().__init__()
        self.chat_sessions = {}  # 内存中的会话缓存
        self.max_sessions = 100  # 最大内存会话数
        self.max_memory_length = 20  # 每个会话最大记忆轮次
        self.dao = ChatDAO()
        self._db_session = db_session

    def _get_db(self) -> Session:
        """获取数据库会话"""
        if self._db_session:
            return self._db_session
        # 如果没有提供会话，则从依赖注入获取
        from ..services.db import SessionLocal

        return SessionLocal()

    def create_session(
        self, session_id: str = None, db: Optional[Session] = None
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

        if session_id not in self.chat_sessions:
            # 检查会话数量限制
            if len(self.chat_sessions) >= self.max_sessions:
                self._cleanup_old_sessions()

            # 创建新会话
            memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                max_token_limit=4000,
            )

            self.chat_sessions[session_id] = {
                "memory": memory,
                "created_at": datetime.now(),
                "last_active": datetime.now(),
                "message_count": 0,
            }

            # 确保会话在数据库中存在
            try:
                self.dao.save_session(db, session_id)
                db.commit()
            except Exception as e:
                db.rollback()
                self.log_error(f"保存会话到数据库失败: {e}")

            self.log_info(f"创建新会话: {session_id}")

        return session_id

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

    def update_session_activity(self, session_id: str):
        """
        更新会话活跃时间

        Args:
            session_id: 会话ID
        """
        if session_id in self.chat_sessions:
            self.chat_sessions[session_id]["last_active"] = datetime.now()

    def add_to_memory(
        self,
        session_id: str,
        human_message: str,
        ai_message: str,
        db: Optional[Session] = None,
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
        if session_id not in self.chat_sessions:
            self.create_session(session_id, db)

        if session_id in self.chat_sessions:
            session = self.chat_sessions[session_id]
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
        self, session_id: str, db: Optional[Session] = None
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
            db_messages = self.dao.get_session_history(db, session_id)

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
                self._load_session_from_db(session_id, history, db)

            return history

        except Exception as e:
            self.log_error(f"从数据库加载会话历史失败: {e}")
            return []

    def _load_session_from_db(
        self, session_id: str, messages: List[BaseMessage], db: Session
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
        self.chat_sessions[session_id] = {
            "memory": memory,
            "created_at": datetime.now(),  # 使用当前时间，或可以从数据库获取
            "last_active": datetime.now(),
            "message_count": len(messages) // 2,  # 假设每条用户消息都有一条AI回复
        }

    def delete_chat_session(
        self, session_id: str, db: Optional[Session] = None
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
            db_deleted = self.dao.delete_session(db, session_id)
            if db_deleted:
                db.commit()
                deleted = True
                self.log_info(f"从数据库中删除会话: {session_id}")
        except Exception as e:
            db.rollback()
            self.log_error(f"从数据库删除会话失败: {e}")

        if not deleted:
            self.log_warning(f"要删除的会话不存在: {session_id}")

        return deleted

    def clear_all_sessions(self, db: Optional[Session] = None):
        """
        清空所有会话

        Args:
            db: 可选的数据库会话
        """
        db = db or self._get_db()

        # 清空数据库中的会话
        try:
            self.dao.clear_all_sessions(db)
            db.commit()
            self.log_info("清空数据库中所有会话")
        except Exception as e:
            db.rollback()
            self.log_error(f"清空数据库会话失败: {e}")

    def get_chat_history(self, session_id: str, db: Optional[Session] = None) -> Dict:
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
        messages = self.get_conversation_history(session_id, db)
        if not messages and not self.session_exists(session_id, db):
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

        if session_id in self.chat_sessions:
            session = self.chat_sessions[session_id]
            created_at = session["created_at"].isoformat()
            last_active = session["last_active"].isoformat()
        else:
            # 尝试从数据库获取元数据
            try:
                sessions = self.dao.get_all_sessions(db)
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

    def session_exists(self, session_id: str, db: Optional[Session] = None) -> bool:
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
            sessions = self.dao.get_all_sessions(db)
            return any(s["session_id"] == session_id for s in sessions)
        except Exception as e:
            self.log_error(f"检查会话存在性失败: {e}")
            return False
