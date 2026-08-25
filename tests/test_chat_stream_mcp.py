"""Tests for streaming-chat MCP selection."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.routers.chat import _resolve_stream_mcp_tools, chat_stream, chat_with_agent
from app.services.mcp_service import MCPService
from app.utils.models import ChatRequest, ChatStreamRequest


def _credentials(token: str = "access-token") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_stream_request_contains_mcp_fields_without_changing_regular_request():
    request = ChatStreamRequest(
        prompt="assistant",
        query="question",
        use_mcp=True,
        mcp_servers=["pygeomodels"],
    )

    assert request.use_mcp is True
    assert request.mcp_servers == ["pygeomodels"]
    assert not hasattr(ChatRequest(prompt="assistant", query="question"), "use_mcp")


def test_only_stream_route_uses_mcp_aware_request_model():
    assert inspect.signature(chat_stream).parameters["request"].annotation is (
        ChatStreamRequest
    )
    assert inspect.signature(chat_with_agent).parameters["request"].annotation is (
        ChatRequest
    )


@pytest.mark.asyncio
async def test_stream_mcp_can_be_disabled_without_touching_mcp_service():
    service = MagicMock()
    request = ChatStreamRequest(prompt="assistant", query="question", use_mcp=False)

    tools = await _resolve_stream_mcp_tools(request, _credentials(), service)

    assert tools == []
    service.is_mcp_initialized.assert_not_called()
    service.get_mcp_tools_for_token.assert_not_called()


@pytest.mark.asyncio
async def test_stream_mcp_omitted_preserves_automatic_behavior():
    service = MagicMock()
    service.is_mcp_initialized.return_value = True
    service.get_mcp_tools_for_token = AsyncMock(return_value=["tool"])
    request = ChatStreamRequest(prompt="assistant", query="question")

    tools = await _resolve_stream_mcp_tools(request, _credentials(), service)

    assert tools == ["tool"]
    service.get_mcp_tools_for_token.assert_awaited_once_with(
        "access-token", server_names=None, raise_on_error=False
    )


@pytest.mark.asyncio
async def test_stream_mcp_selects_requested_servers():
    service = MagicMock()
    service.is_mcp_initialized.return_value = True
    service.get_mcp_tools_for_token = AsyncMock(return_value=["selected-tool"])
    request = ChatStreamRequest(
        prompt="assistant",
        query="question",
        use_mcp=True,
        mcp_servers=["pygeomodels"],
    )

    tools = await _resolve_stream_mcp_tools(request, _credentials(), service)

    assert tools == ["selected-tool"]
    service.get_mcp_tools_for_token.assert_awaited_once_with(
        "access-token", server_names=["pygeomodels"], raise_on_error=True
    )


@pytest.mark.asyncio
async def test_stream_mcp_explicit_enable_without_servers_uses_all_configured_servers():
    service = MagicMock()
    service.is_mcp_initialized.return_value = True
    service.get_mcp_tools_for_token = AsyncMock(return_value=["tool"])
    request = ChatStreamRequest(prompt="assistant", query="question", use_mcp=True)

    await _resolve_stream_mcp_tools(request, _credentials(), service)

    service.get_mcp_tools_for_token.assert_awaited_once_with(
        "access-token", server_names=None, raise_on_error=True
    )


@pytest.mark.asyncio
async def test_stream_mcp_rejects_server_selection_without_explicit_enable():
    service = MagicMock()
    request = ChatStreamRequest(
        prompt="assistant",
        query="question",
        mcp_servers=["pygeomodels"],
    )

    with pytest.raises(ValueError, match="requires use_mcp=true"):
        await _resolve_stream_mcp_tools(request, _credentials(), service)

    service.is_mcp_initialized.assert_not_called()


@pytest.mark.asyncio
async def test_stream_mcp_requires_initialized_service_when_explicitly_enabled():
    service = MagicMock()
    service.is_mcp_initialized.return_value = False
    request = ChatStreamRequest(prompt="assistant", query="question", use_mcp=True)

    with pytest.raises(RuntimeError, match="not initialized"):
        await _resolve_stream_mcp_tools(request, _credentials(), service)


@pytest.mark.asyncio
async def test_mcp_service_builds_tokenized_config_for_selected_servers():
    service = MCPService()
    client = MagicMock()
    client.get_tools = AsyncMock(return_value=["tool"])
    mcp_config = {
        "pygeomodels": {
            "url": "http://pygeomodels/mcp",
            "transport": "streamable_http",
        },
        "calculator": {
            "url": "http://calculator/mcp",
            "transport": "streamable_http",
        },
    }

    with patch("app.services.mcp_service.MCP_CONFIG", mcp_config):
        with patch(
            "app.services.mcp_service.MultiServerMCPClient", return_value=client
        ) as client_class:
            tools = await service.get_mcp_tools_for_token(
                "access-token",
                server_names=["pygeomodels"],
                raise_on_error=True,
            )

    assert tools == ["tool"]
    selected_config = client_class.call_args.args[0]
    assert list(selected_config) == ["pygeomodels"]
    assert selected_config["pygeomodels"]["headers"] == {
        "Authorization": "Bearer access-token"
    }


def test_mcp_service_rejects_empty_or_unknown_server_selection():
    service = MCPService()
    mcp_config = {"pygeomodels": {"url": "http://pygeomodels/mcp"}}

    with patch("app.services.mcp_service.MCP_CONFIG", mcp_config):
        with pytest.raises(ValueError, match="at least one"):
            service._select_mcp_config([])
        with pytest.raises(ValueError, match="Unknown MCP server"):
            service._select_mcp_config(["missing"])


@pytest.mark.asyncio
async def test_mcp_service_propagates_selected_connection_error_when_requested():
    service = MCPService()
    mcp_config = {"pygeomodels": {"url": "http://pygeomodels/mcp"}}

    with patch("app.services.mcp_service.MCP_CONFIG", mcp_config):
        with patch(
            "app.services.mcp_service.MultiServerMCPClient",
            side_effect=ConnectionError("MCP unavailable"),
        ):
            with pytest.raises(ConnectionError, match="MCP unavailable"):
                await service.get_mcp_tools_for_token(
                    "access-token",
                    server_names=["pygeomodels"],
                    raise_on_error=True,
                )
