"""Tests for safe streamed MCP tool-call lifecycle events and replay data."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain.schema import AIMessage
from langchain_core.messages import ToolMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.dao.chat_dao import ChatDAO
from app.db.base import Base
from app.services.chat_service import ChatService
from app.utils.tool_calls import ToolCallTracker, normalize_tool_calls


def test_tracker_emits_ordered_safe_success_events():
    tracker = ToolCallTracker()

    started = tracker.start(
        [
            {
                "id": "call_01",
                "name": "pygeomodels_search",
                "args": {"query": "secret input"},
            }
        ]
    )
    completed = tracker.finish("call_01", "pygeomodels_search")

    assert started == [
        {
            "type": "tool",
            "call_id": "call_01",
            "sequence": 1,
            "status": "started",
            "tool_key": "geo.model_search",
            "tool_name": "pygeomodels_search",
            "tool_source": "mcp",
        }
    ]
    assert completed[0]["status"] == "succeeded"
    assert completed[0]["sequence"] == 2
    assert "args" not in completed[0]
    assert tracker.completed_calls() == [
        {
            "id": "call_01",
            "sequence": 2,
            "tool_key": "geo.model_search",
            "tool_name": "pygeomodels_search",
            "tool_source": "mcp",
            "status": "succeeded",
            "duration_ms": completed[0]["duration_ms"],
        }
    ]


@pytest.mark.asyncio
async def test_chat_stream_emits_safe_failed_tool_event_without_raw_output():
    service = ChatService()
    agent = MagicMock()

    async def stream(*_args, **_kwargs):
        yield (
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_02",
                        "name": "pygeomodels_search",
                        "args": {"query": "secret input"},
                    }
                ],
            ),
            {},
        )
        yield (
            ToolMessage(
                content="https://internal.example token=secret",
                tool_call_id="call_02",
                name="pygeomodels_search",
                status="error",
            ),
            {},
        )

    agent.astream = MagicMock(return_value=stream())

    with patch.object(
        service,
        "_build_tools_and_messages",
        new=AsyncMock(return_value=([MagicMock()], [], [])),
    ):
        with patch.object(service, "_create_llm"):
            with patch(
                "app.services.chat_service.create_react_agent",
                return_value=agent,
            ):
                events = [
                    event
                    async for event in service.chat_stream(
                        prompt="assistant",
                        query="question",
                        use_memory=False,
                    )
                ]

    tool_statuses = [event["status"] for event in events if event["type"] == "tool"]
    assert tool_statuses == [
        "started",
        "failed",
    ]
    failed = events[-1]
    assert failed["code"] == "mcp.tool_failed"
    assert failed["tool_key"] == "geo.model_search"
    assert "name" not in failed
    assert "token" not in str(events)
    assert "internal.example" not in str(events)


def test_tracker_keeps_safe_concrete_tool_identifier_for_display():
    tracker = ToolCallTracker()

    event = tracker.start([{"id": "call_04", "name": "list_models_by_category"}])[0]

    assert event["tool_key"] == "mcp.tool"
    assert event["tool_name"] == "list_models_by_category"
    assert event["tool_source"] == "mcp"
    assert normalize_tool_calls(
        [
            {
                "id": "call_04",
                "sequence": 1,
                "tool_key": "mcp.tool",
                "tool_name": "list_models_by_category",
                "status": "succeeded",
            },
            {
                "id": "call_05",
                "sequence": 2,
                "tool_key": "mcp.tool",
                "tool_name": "unsafe tool name with spaces",
                "status": "succeeded",
            },
        ]
    ) == [
        {
            "id": "call_04",
            "sequence": 1,
            "tool_key": "mcp.tool",
            "tool_name": "list_models_by_category",
            "status": "succeeded",
            "tool_source": "mcp",
        },
        {
            "id": "call_05",
            "sequence": 2,
            "tool_key": "mcp.tool",
            "status": "succeeded",
            "tool_source": "mcp",
        },
    ]


def test_tracker_marks_registered_retriever_as_rag_tool():
    tracker = ToolCallTracker()

    event = tracker.start([{"id": "call_06", "name": "info_retriever"}])[0]

    assert event["tool_name"] == "info_retriever"
    assert event["tool_source"] == "rag"


def test_chat_message_persists_only_safe_terminal_tool_call_records():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    previous_checked = ChatDAO._chat_tables_checked
    ChatDAO._chat_tables_checked = False
    try:
        ChatDAO.save_session(db, "session-1", user_id="user-1")
        ChatDAO.save_message(
            db,
            "session-1",
            "assistant",
            "partial response",
            user_id="user-1",
            generation_status="failed",
            tool_calls=[
                {
                    "id": "call_03",
                    "sequence": 2,
                    "tool_key": "geo.model_search",
                    "status": "failed",
                    "duration_ms": 12,
                    "code": "mcp.tool_failed",
                    "arguments": "must-not-persist",
                    "result": "must-not-persist",
                }
            ],
        )

        history = ChatDAO.get_session_history(db, "session-1", user_id="user-1")
        assert history[0]["generation_status"] == "failed"
        assert history[0]["tool_calls"] == [
            {
                "id": "call_03",
                "sequence": 2,
                "tool_key": "geo.model_search",
                "status": "failed",
                "duration_ms": 12,
                "code": "mcp.tool_failed",
                "tool_source": "mcp",
            }
        ]
        assert "must-not-persist" not in str(history)
    finally:
        db.close()
        ChatDAO._chat_tables_checked = previous_checked
