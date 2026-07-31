"""Regression tests for per-user chat ownership filters."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.dao.chat_dao import ChatDAO
from app.db.base import Base


def test_chat_records_are_isolated_by_user():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    ChatDAO._title_column_checked = True

    try:
        ChatDAO.save_session(db, "session-a", user_id="user-a")
        ChatDAO.save_message(db, "session-a", "user", "A secret", user_id="user-a")
        ChatDAO.save_session(db, "session-b", user_id="user-b")
        ChatDAO.save_message(db, "session-b", "user", "B secret", user_id="user-b")

        assert [
            item["session_id"]
            for item in ChatDAO.get_all_sessions(db, user_id="user-a")
        ] == ["session-a"]
        assert ChatDAO.get_session(db, "session-b", user_id="user-a") is None
        assert ChatDAO.get_session_history(
            db, "session-b", user_id="user-a"
        ) == []

        assert ChatDAO.delete_session(db, "session-a", user_id="user-b") is False
        assert ChatDAO.delete_session(db, "session-a", user_id="user-a") is True
        assert ChatDAO.get_session(db, "session-b", user_id="user-b") is not None

        ChatDAO.clear_all_sessions(db, user_id="user-b")
        assert ChatDAO.get_all_sessions(db, user_id="user-b") == []
    finally:
        db.close()
