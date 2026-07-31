"""Regression tests for MCP/chat request observability."""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.dao.chat_dao import ChatDAO
from app.db.base import Base
from app.models.chat_models import ChatRun, ToolRun
from app.services.chat_service import ChatService
from app.utils.handler import MCPToolLoggingHandler


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


def test_chat_run_records_terminal_failure_without_message_payload(db_session):
    request_id = "request-1"
    ChatDAO.create_chat_run(db_session, request_id, "session-1", "message-1")
    ChatDAO.finish_chat_run(
        db_session,
        request_id,
        "failed",
        started_at=datetime.now(),
        error=RuntimeError("MCP unavailable"),
    )

    run = db_session.get(ChatRun, request_id)
    assert run.status == "failed"
    assert run.error_type == "RuntimeError"
    assert run.error_message == "MCP unavailable"
    assert run.duration_ms is not None


def test_tool_handler_persists_digests_not_raw_payload(db_session):
    handler = MCPToolLoggingHandler(
        MagicMock(), request_id="request-2", db=db_session
    )
    secret_input = "very-secret-tool-input"
    run_id = "tool-run-1"

    handler.on_tool_start({"name": "geo_tool"}, secret_input, run_id=run_id)
    handler.on_tool_end("very-secret-tool-output", run_id=run_id)

    tool_run = db_session.get(ToolRun, run_id)
    assert tool_run.status == "succeeded"
    assert secret_input not in tool_run.input_digest
    assert "sha256_prefix=" in tool_run.input_digest
    assert "very-secret-tool-output" not in tool_run.output_digest


@pytest.mark.asyncio
async def test_chat_service_marks_long_agent_call_as_timeout():
    service = ChatService()
    agent = MagicMock()

    async def slow_agent(*args, **kwargs):
        await asyncio.sleep(0.05)

    agent.ainvoke.side_effect = slow_agent

    with patch("app.services.chat_service.create_react_agent", return_value=agent):
        with patch.object(service, "_create_llm"):
            with pytest.raises(asyncio.TimeoutError):
                await service.chat_with_agent(
                    prompt="你是助手",
                    query="调用一个很慢的工具",
                    mcp_tools=[MagicMock(name="slow_tool")],
                    timeout_seconds=0.001,
                )
