import logging
from typing import List, Optional

from sqlalchemy import func, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.chat_models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


class ChatDAO:
    """聊天数据访问对象"""

    _title_column_checked = False

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

    @staticmethod
    def save_session(db: Session, session_id: str, title: Optional[str] = None) -> None:
        """
        保存会话到数据库

        Args:
            db: 数据库会话
            session_id: 会话ID
            title: 会话标题（可选）

        Raises:
            SQLAlchemyError: 数据库操作异常
        """
        try:
            ChatDAO._ensure_title_column(db)
            existing_session = db.get(ChatSession, session_id)
            if existing_session:
                if title is not None:
                    existing_session.title = title
            else:
                db.add(ChatSession(session_id=session_id, title=title))
            db.commit()
            logger.debug(f"Session saved: {session_id}")
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"保存会话到数据库失败: {e}")
            raise

    @staticmethod
    def get_session(db: Session, session_id: str) -> Optional[dict]:
        """获取单个会话信息"""
        try:
            ChatDAO._ensure_title_column(db)
            session = (
                db.query(ChatSession)
                .filter(ChatSession.session_id == session_id)
                .first()
            )
            if not session:
                return None

            return {
                "session_id": session.session_id,
                "title": session.title,
                "created_at": (
                    session.created_at.isoformat() if session.created_at else None
                ),
            }
        except SQLAlchemyError as e:
            logger.error(f"获取会话失败: {e}")
            return None

    @staticmethod
    def update_session_title(db: Session, session_id: str, title: str) -> bool:
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
            ChatDAO._ensure_title_column(db)
            result = (
                db.query(ChatSession)
                .filter(ChatSession.session_id == session_id)
                .update({"title": title})
            )
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
            # 验证和清理内容
            if not isinstance(content, str):
                content = str(content)

            # 限制内容长度
            max_length = 10000
            if len(content) > max_length:
                content = content[:max_length] + "...[截断]"
                logger.warning(f"消息内容超过{max_length}字符，已截断")

            # 创建消息对象
            message = ChatMessage(
                message_id=message_id or ChatMessage.create_id(),
                session_id=session_id,
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

    @staticmethod
    def get_session_messages(
        db: Session, session_id: str, limit: int = 100, offset: int = 0
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
            messages = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            return [{"role": msg.role, "content": msg.content} for msg in messages]

        except SQLAlchemyError as e:
            logger.error(f"获取会话消息失败: {e}")
            return []

    @staticmethod
    def delete_session(db: Session, session_id: str) -> bool:
        """
        删除指定会话及其所有消息

        Args:
            db: 数据库会话
            session_id: 会话ID

        Returns:
            bool: 是否删除成功
        """
        try:
            # 先删除消息
            db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()

            # 再删除会话
            result = (
                db.query(ChatSession)
                .filter(ChatSession.session_id == session_id)
                .delete()
            )

            db.commit()
            return result > 0

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"删除会话失败: {e}")
            return False

    @staticmethod
    def get_all_sessions(db: Session) -> List[dict]:
        """
        获取所有会话信息

        Args:
            db: 数据库会话

        Returns:
            List[dict]: 会话信息列表，每个会话包含session_id, created_at, message_count
        """
        try:
            ChatDAO._ensure_title_column(db)
            # 获取所有会话及其消息数量
            sessions = (
                db.query(
                    ChatSession.session_id,
                    ChatSession.title,
                    ChatSession.created_at,
                    func.count(ChatMessage.message_id).label("message_count"),
                )
                .outerjoin(
                    ChatMessage, ChatSession.session_id == ChatMessage.session_id
                )
                .group_by(
                    ChatSession.session_id, ChatSession.title, ChatSession.created_at
                )
                .order_by(ChatSession.created_at.desc())
                .all()
            )

            return [
                {
                    "session_id": s.session_id,
                    "title": s.title,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "message_count": s.message_count or 0,
                }
                for s in sessions
            ]

        except SQLAlchemyError as e:
            logger.error(f"获取会话列表失败: {e}")
            return []

    @staticmethod
    def clear_all_sessions(db: Session) -> bool:
        """
        清空所有会话和消息

        Args:
            db: 数据库会话

        Returns:
            bool: 是否清空成功
        """
        try:
            # 删除所有消息
            db.query(ChatMessage).delete()
            # 删除所有会话
            db.query(ChatSession).delete()
            db.commit()
            return True

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"清空所有会话失败: {e}")
            return False

    @staticmethod
    def get_session_history(db: Session, session_id: str) -> List[dict]:
        """
        获取指定会话的历史消息

        Args:
            db: 数据库会话
            session_id: 会话ID

        Returns:
            List[dict]: 消息列表，包含 message_id/role/content/created_at
        """
        try:
            messages = (
                db.query(
                    ChatMessage.message_id,
                    ChatMessage.role,
                    ChatMessage.content,
                    ChatMessage.created_at,
                )
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
                .all()
            )

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
