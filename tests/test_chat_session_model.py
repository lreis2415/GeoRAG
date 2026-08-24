"""Regression tests for persisting the latest model on a chat session."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.dao.chat_dao import ChatDAO
from app.db.base import Base


def test_session_persists_and_updates_latest_chat_model():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    previous_title_checked = ChatDAO._title_column_checked
    previous_model_checked = ChatDAO._chat_model_column_checked
    ChatDAO._title_column_checked = True
    ChatDAO._chat_model_column_checked = True

    try:
        ChatDAO.save_session(
            db,
            "session-1",
            user_id="user-1",
            chat_model_name="qwen-turbo-latest",
        )
        assert (
            ChatDAO.get_session(db, "session-1", user_id="user-1")["chat_model_name"]
            == "qwen-turbo-latest"
        )

        ChatDAO.save_session(
            db,
            "session-1",
            user_id="user-1",
            chat_model_name="deepseek-v3",
        )

        session = ChatDAO.get_session(db, "session-1", user_id="user-1")
        sessions = ChatDAO.get_all_sessions(db, user_id="user-1")
        assert session["chat_model_name"] == "deepseek-v3"
        assert sessions[0]["chat_model_name"] == "deepseek-v3"

        ChatDAO.save_session(db, "legacy-session", user_id="user-1")
        assert (
            ChatDAO.get_session(db, "legacy-session", user_id="user-1")[
                "chat_model_name"
            ]
            is None
        )
    finally:
        ChatDAO._title_column_checked = previous_title_checked
        ChatDAO._chat_model_column_checked = previous_model_checked
        db.close()
