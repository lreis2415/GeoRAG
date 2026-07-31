"""Database-only regression tests for chat request auditing."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.dao.chat_dao import ChatDAO
from app.db.base import Base
from app.models.chat_models import ChatRun, ToolRun


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    previous_checked = ChatDAO._observability_tables_checked
    ChatDAO._observability_tables_checked = False
    try:
        yield session
    finally:
        session.close()
        ChatDAO._observability_tables_checked = previous_checked


def test_chat_run_records_terminal_failure(db_session):
    ChatDAO.create_chat_run(db_session, "request-1", "session-1", "message-1")
    ChatDAO.finish_chat_run(
        db_session,
        "request-1",
        "failed",
        started_at=datetime.now(),
        error=RuntimeError("MCP unavailable"),
    )

    run = db_session.get(ChatRun, "request-1")
    assert run.status == "failed"
    assert run.error_type == "RuntimeError"
    assert run.error_message == "MCP unavailable"
    assert run.duration_ms is not None


def test_tool_run_uses_digest_instead_of_raw_payload(db_session):
    secret_input = "very-secret-tool-input"
    ChatDAO.start_tool_run(
        db_session,
        "tool-run-1",
        "request-2",
        "geo_tool",
        secret_input,
    )
    ChatDAO.finish_tool_run(
        db_session,
        "tool-run-1",
        "succeeded",
        output="very-secret-tool-output",
    )

    tool_run = db_session.get(ToolRun, "tool-run-1")
    assert tool_run.status == "succeeded"
    assert secret_input not in tool_run.input_digest
    assert "sha256_prefix=" in tool_run.input_digest
    assert "very-secret-tool-output" not in tool_run.output_digest
