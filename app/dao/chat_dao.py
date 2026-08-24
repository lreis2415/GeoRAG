import hashlib
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.chat_models import ChatMessage, ChatRun, ChatSession, ToolRun

logger = logging.getLogger(__name__)


class ChatDAO:
    """聊天数据访问对象"""

    _title_column_checked = False
    _chat_model_column_checked = False
    _observability_tables_checked = False
    _chat_tables_checked = False

    @classmethod
    def _ensure_observability_tables(cls, db: Session) -> None:
        """Create audit tables for deployments that predate observability."""
        if cls._observability_tables_checked:
            return

        try:
            engine = db.get_bind()
            if engine is None:
                return
            ChatRun.__table__.create(bind=engine, checkfirst=True)
            ToolRun.__table__.create(bind=engine, checkfirst=True)
            cls._observability_tables_checked = True
        except Exception:
            db.rollback()
            logger.exception("创建聊天审计表失败")
            raise

    @classmethod
    def _ensure_chat_tables(cls, db: Session) -> None:
        """Create chat session/message tables for deployments that predate them."""
        if cls._chat_tables_checked:
            return

        try:
            engine = db.get_bind()
            if engine is None:
                return
            ChatSession.__table__.create(bind=engine, checkfirst=True)
            ChatMessage.__table__.create(bind=engine, checkfirst=True)
            cls._chat_tables_checked = True
        except Exception:
            db.rollback()
            logger.exception("创建聊天会话表失败")
            raise

    @staticmethod
    def _payload_digest(value: object) -> str:
        """Return a bounded, non-reversible diagnostic summary for a payload."""
        if isinstance(value, bytes):
            prefix = value[:4096]
            return (
                f"bytes={len(value)} sha256_prefix="
                f"{hashlib.sha256(prefix).hexdigest()[:16]}"
            )
        if isinstance(value, str):
            prefix = value[:4096].encode("utf-8", errors="replace")
            return (
                f"chars={len(value)} sha256_prefix="
                f"{hashlib.sha256(prefix).hexdigest()[:16]}"
            )
        return f"type={type(value).__name__}"

    @staticmethod
    def _error_summary(error: object, max_length: int = 2000) -> str:
        message = str(error).replace("\x00", " ").strip()
        return message[:max_length]

    @classmethod
    def _ensure_title_column(cls, db: Session) -> None:
        """Best-effort schema compatibility for `chat_sessions.title`."""
        if cls._title_column_checked:
            return

        try:
            engine = db.get_bind()
            if engine is None:
                return

            columns = {
                col["name"] for col in inspect(engine).get_columns("chat_sessions")
            }
            if "title" not in columns:
                db.execute(
                    text("ALTER TABLE chat_sessions ADD COLUMN title VARCHAR(200)")
                )
                db.commit()
            cls._title_column_checked = True
        except Exception:
            # 对于测试 mock 或非标准数据库，忽略并继续
            db.rollback()

    @classmethod
    def _ensure_chat_model_column(cls, db: Session) -> None:
        """Best-effort schema compatibility for session model metadata."""
        if cls._chat_model_column_checked:
            return

        try:
            engine = db.get_bind()
            if engine is None:
                return

            columns = {
                col["name"] for col in inspect(engine).get_columns("chat_sessions")
            }
            if "chat_model_name" not in columns:
                db.execute(
                    text(
                        "ALTER TABLE chat_sessions "
                        "ADD COLUMN chat_model_name VARCHAR(200)"
                    )
                )
                db.commit()
            cls._chat_model_column_checked = True
        except Exception:
            # 对于测试 mock 或非标准数据库，忽略并继续
            db.rollback()

    @staticmethod
    def save_session(
        db: Session,
        session_id: str,
        title: Optional[str] = None,
        user_id: Optional[str] = None,
        chat_model_name: Optional[str] = None,
    ) -> None:
        """
        保存会话到数据库

        Args:
            db: 数据库会话
            session_id: 会话ID
            title: 会话标题（可选）
            chat_model_name: 会话最近一次使用的聊天模型（可选）

        Raises:
            SQLAlchemyError: 数据库操作异常
        """
        try:
            ChatDAO._ensure_chat_tables(db)
            ChatDAO._ensure_title_column(db)
            ChatDAO._ensure_chat_model_column(db)
            existing_session = db.get(ChatSession, session_id)
            if existing_session:
                if user_id is not None and existing_session.user_id != user_id:
                    raise ValueError("Session belongs to another user")
                if title is not None:
                    existing_session.title = title
                if chat_model_name is not None:
                    existing_session.chat_model_name = chat_model_name
            else:
                db.add(
                    ChatSession(
                        session_id=session_id,
                        title=title,
                        user_id=user_id,
                        chat_model_name=chat_model_name,
                    )
                )
            db.commit()
            logger.debug(f"Session saved: {session_id}")
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"保存会话到数据库失败: {e}")
            raise

    @staticmethod
    def get_session(
        db: Session, session_id: str, user_id: Optional[str] = None
    ) -> Optional[dict]:
        """获取单个会话信息"""
        try:
            ChatDAO._ensure_chat_tables(db)
            ChatDAO._ensure_title_column(db)
            ChatDAO._ensure_chat_model_column(db)
            query = db.query(ChatSession).filter(ChatSession.session_id == session_id)
            if user_id is not None:
                query = query.filter(ChatSession.user_id == user_id)
            session = query.first()
            if not session:
                return None

            return {
                "session_id": session.session_id,
                "title": session.title,
                "chat_model_name": session.chat_model_name,
                "created_at": (
                    session.created_at.isoformat() if session.created_at else None
                ),
            }
        except SQLAlchemyError as e:
            logger.error(f"获取会话失败: {e}")
            return None

    @staticmethod
    def update_session_title(
        db: Session, session_id: str, title: str, user_id: Optional[str] = None
    ) -> bool:
        """
        更新会话标题

        Args:
            db: 数据库会话
            session_id: 会话ID
            title: 会话标题

        Returns:
            bool: 是否更新成功
        """
        try:
            ChatDAO._ensure_chat_tables(db)
            ChatDAO._ensure_title_column(db)
            query = db.query(ChatSession).filter(ChatSession.session_id == session_id)
            if user_id is not None:
                query = query.filter(ChatSession.user_id == user_id)
            result = query.update({"title": title})
            db.commit()
            return result > 0
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"更新会话标题失败: {e}")
            return False

    @staticmethod
    def save_message(
        db: Session,
        session_id: str,
        role: str,
        content: str,
        message_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        保存消息到数据库

        Args:
            db: 数据库会话
            session_id: 会话ID
            role: 消息角色 (user/assistant)
            content: 消息内容
            message_id: 可选的消息ID，如未提供则自动生成

        Returns:
            str: 消息ID

        Raises:
            SQLAlchemyError: 数据库操作异常
            ValueError: 内容过长或无效
        """
        try:
            ChatDAO._ensure_chat_tables(db)
            # 验证和清理内容
            if not isinstance(content, str):
                content = str(content)

            # 限制内容长度
            max_length = 10000
            if len(content) > max_length:
                content = content[:max_length] + "...[截断]"
                logger.warning(f"消息内容超过{max_length}字符，已截断")

            if user_id is not None:
                session_exists = (
                    db.query(ChatSession)
                    .filter(
                        ChatSession.session_id == session_id,
                        ChatSession.user_id == user_id,
                    )
                    .first()
                )
                if session_exists is None:
                    raise ValueError("Session not found")

            # 创建消息对象
            message = ChatMessage(
                message_id=message_id or ChatMessage.create_id(),
                session_id=session_id,
                user_id=user_id,
                role=role,
                content=content,
            )

            db.add(message)
            db.commit()
            logger.debug(f"Message saved to session {session_id}")
            return message.message_id

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"保存消息到数据库失败: {e}")
            raise

    @classmethod
    def create_chat_run(
        cls,
        db: Session,
        request_id: str,
        session_id: Optional[str] = None,
        user_message_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Persist a running request before LLM or MCP work begins."""
        try:
            cls._ensure_observability_tables(db)
            db.add(
                ChatRun(
                    request_id=request_id,
                    session_id=session_id,
                    user_message_id=user_message_id,
                    user_id=user_id,
                    status="running",
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("创建聊天运行记录失败: request_id=%s", request_id)
            raise

    @classmethod
    def finish_chat_run(
        cls,
        db: Session,
        request_id: str,
        status: str,
        started_at: datetime,
        error: Optional[object] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Record the terminal state of a chat request."""
        try:
            cls._ensure_observability_tables(db)
            query = db.query(ChatRun).filter(ChatRun.request_id == request_id)
            if user_id is not None:
                query = query.filter(ChatRun.user_id == user_id)
            run = query.first()
            if not run:
                logger.warning("聊天运行记录不存在: request_id=%s", request_id)
                return
            finished_at = datetime.now()
            run.status = status
            run.finished_at = finished_at
            run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            if error is not None:
                run.error_type = type(error).__name__
                run.error_message = cls._error_summary(error)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("更新聊天运行记录失败: request_id=%s", request_id)

    @classmethod
    def start_tool_run(
        cls,
        db: Session,
        tool_run_id: str,
        request_id: str,
        tool_name: Optional[str],
        tool_input: object,
        user_id: Optional[str] = None,
    ) -> None:
        """Persist a tool's start using only a bounded input digest."""
        try:
            cls._ensure_observability_tables(db)
            if db.get(ToolRun, tool_run_id):
                return
            db.add(
                ToolRun(
                    tool_run_id=tool_run_id,
                    request_id=request_id,
                    user_id=user_id,
                    tool_name=tool_name,
                    status="running",
                    input_digest=cls._payload_digest(tool_input),
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "创建工具运行记录失败: request_id=%s tool_run_id=%s",
                request_id,
                tool_run_id,
            )

    @classmethod
    def finish_tool_run(
        cls,
        db: Session,
        tool_run_id: str,
        status: str,
        output: Optional[object] = None,
        error: Optional[object] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Persist a tool's terminal state and a bounded diagnostic."""
        try:
            cls._ensure_observability_tables(db)
            query = db.query(ToolRun).filter(ToolRun.tool_run_id == tool_run_id)
            if user_id is not None:
                query = query.filter(ToolRun.user_id == user_id)
            run = query.first()
            if not run:
                logger.warning("工具运行记录不存在: tool_run_id=%s", tool_run_id)
                return
            run.status = status
            run.finished_at = datetime.now()
            if output is not None:
                run.output_digest = cls._payload_digest(output)
            if error is not None:
                run.error_message = cls._error_summary(error)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("更新工具运行记录失败: tool_run_id=%s", tool_run_id)

    @staticmethod
    def get_session_messages(
        db: Session,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        user_id: Optional[str] = None,
    ) -> List[dict]:
        """
        获取指定会话的消息历史

        Args:
            db: 数据库会话
            session_id: 会话ID
            limit: 返回的最大消息数
            offset: 偏移量

        Returns:
            List[dict]: 消息列表，每个消息是包含角色和内容的字典
        """
        try:
            ChatDAO._ensure_chat_tables(db)
            query = db.query(ChatMessage).filter(ChatMessage.session_id == session_id)
            if user_id is not None:
                query = query.filter(ChatMessage.user_id == user_id)
            messages = (
                query.order_by(ChatMessage.created_at.asc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            return [{"role": msg.role, "content": msg.content} for msg in messages]

        except SQLAlchemyError as e:
            logger.error(f"获取会话消息失败: {e}")
            return []

    @staticmethod
    def delete_session(
        db: Session, session_id: str, user_id: Optional[str] = None
    ) -> bool:
        """
        删除指定会话及其所有消息

        Args:
            db: 数据库会话
            session_id: 会话ID

        Returns:
            bool: 是否删除成功
        """
        try:
            ChatDAO._ensure_chat_tables(db)
            # 先删除消息
            message_query = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            )
            if user_id is not None:
                message_query = message_query.filter(ChatMessage.user_id == user_id)
            message_query.delete()

            # 再删除会话
            session_query = db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            )
            if user_id is not None:
                session_query = session_query.filter(ChatSession.user_id == user_id)
            result = session_query.delete()

            db.commit()
            return result > 0

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"删除会话失败: {e}")
            return False

    @staticmethod
    def get_all_sessions(db: Session, user_id: Optional[str] = None) -> List[dict]:
        """
        获取所有会话信息

        Args:
            db: 数据库会话

        Returns:
            List[dict]: 会话信息列表，每个会话包含session_id, created_at, message_count
        """
        try:
            ChatDAO._ensure_chat_tables(db)
            ChatDAO._ensure_title_column(db)
            ChatDAO._ensure_chat_model_column(db)
            # 获取所有会话及其消息数量
            query = db.query(
                ChatSession.session_id,
                ChatSession.title,
                ChatSession.chat_model_name,
                ChatSession.created_at,
                func.count(ChatMessage.message_id).label("message_count"),
            ).outerjoin(ChatMessage, ChatSession.session_id == ChatMessage.session_id)
            if user_id is not None:
                query = query.filter(ChatSession.user_id == user_id)
            sessions = (
                query.group_by(
                    ChatSession.session_id,
                    ChatSession.title,
                    ChatSession.chat_model_name,
                    ChatSession.created_at,
                )
                .order_by(ChatSession.created_at.desc())
                .all()
            )

            return [
                {
                    "session_id": s.session_id,
                    "title": s.title,
                    "chat_model_name": s.chat_model_name,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "message_count": s.message_count or 0,
                }
                for s in sessions
            ]

        except SQLAlchemyError as e:
            logger.error(f"获取会话列表失败: {e}")
            return []

    @staticmethod
    def clear_all_sessions(db: Session, user_id: Optional[str] = None) -> bool:
        """
        清空所有会话和消息

        Args:
            db: 数据库会话

        Returns:
            bool: 是否清空成功
        """
        try:
            ChatDAO._ensure_chat_tables(db)
            # 删除所有消息
            message_query = db.query(ChatMessage)
            session_query = db.query(ChatSession)
            if user_id is not None:
                message_query = message_query.filter(ChatMessage.user_id == user_id)
                session_query = session_query.filter(ChatSession.user_id == user_id)
            message_query.delete()
            # 删除所有会话
            session_query.delete()
            db.commit()
            return True

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"清空所有会话失败: {e}")
            return False

    @staticmethod
    def get_session_history(
        db: Session, session_id: str, user_id: Optional[str] = None
    ) -> List[dict]:
        """
        获取指定会话的历史消息

        Args:
            db: 数据库会话
            session_id: 会话ID

        Returns:
            List[dict]: 消息列表，包含 message_id/role/content/created_at
        """
        try:
            ChatDAO._ensure_chat_tables(db)
            query = db.query(
                ChatMessage.message_id,
                ChatMessage.role,
                ChatMessage.content,
                ChatMessage.created_at,
            ).filter(ChatMessage.session_id == session_id)
            if user_id is not None:
                query = query.filter(ChatMessage.user_id == user_id)
            messages = query.order_by(ChatMessage.created_at.asc()).all()

            return [
                {
                    "message_id": msg.message_id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": (
                        msg.created_at.isoformat() if msg.created_at else None
                    ),
                }
                for msg in messages
            ]

        except SQLAlchemyError as e:
            logger.error(f"获取会话历史失败: {e}")
            return []
