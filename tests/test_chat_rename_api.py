"""
会话重命名接口测试模块

测试内容：
1. POST /chat/sessions/{session_id}/rename - 重命名会话
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.routers.chat import rename_chat_session
from app.utils.models import RenameSessionRequest


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.user_id = "user-1"
    return user


def run(coro):
    return asyncio.run(coro)


def call_rename(session_id, title, mock_db, mock_user):
    with patch("app.routers.chat.chat_dao") as dao:
        result = run(
            rename_chat_session(
                session_id=session_id,
                request=RenameSessionRequest(title=title),
                current_user=mock_user,
                db=mock_db,
            )
        )
        return result, dao


def test_rename_session_success(mock_db, mock_user):
    result, dao = call_rename("sess-1", "新标题", mock_db, mock_user)

    dao.update_session_title.assert_called_once_with(
        mock_db, "sess-1", "新标题", user_id="user-1"
    )
    assert result["success"] is True
    assert result["message"] == "会话已重命名"


def test_rename_session_strips_whitespace(mock_db, mock_user):
    result, dao = call_rename("sess-1", "  新标题  ", mock_db, mock_user)

    dao.update_session_title.assert_called_once_with(
        mock_db, "sess-1", "新标题", user_id="user-1"
    )
    assert result["success"] is True


def test_rename_session_not_found(mock_db, mock_user):
    with patch("app.routers.chat.chat_dao") as dao:
        dao.update_session_title.return_value = False
        result = run(
            rename_chat_session(
                session_id="missing",
                request=RenameSessionRequest(title="标题"),
                current_user=mock_user,
                db=mock_db,
            )
        )

    assert result["success"] is False
    assert result["code"] == 4004


def test_rename_session_blank_title_rejected(mock_db, mock_user):
    result, dao = call_rename("sess-1", "   ", mock_db, mock_user)

    dao.update_session_title.assert_not_called()
    assert result["success"] is False
    assert result["code"] == 4002


def test_rename_session_title_length_validation():
    with pytest.raises(Exception):
        RenameSessionRequest(title="")
    with pytest.raises(Exception):
        RenameSessionRequest(title="x" * 101)


def test_rename_session_db_error(mock_db, mock_user):
    with patch("app.routers.chat.chat_dao") as dao:
        dao.update_session_title.side_effect = RuntimeError("db down")
        result = run(
            rename_chat_session(
                session_id="sess-1",
                request=RenameSessionRequest(title="标题"),
                current_user=mock_user,
                db=mock_db,
            )
        )

    assert result["success"] is False
    assert result["code"] == 5014
