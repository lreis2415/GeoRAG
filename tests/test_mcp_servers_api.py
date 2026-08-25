"""Tests for the MCP server discovery endpoint."""

from unittest.mock import MagicMock

import pytest

from app.routers.chat import list_mcp_servers, router


@pytest.mark.asyncio
async def test_list_mcp_servers_returns_names_and_initialized_state():
    current_user = MagicMock(user_id="user-1")
    mcp_service = MagicMock()
    mcp_service.is_mcp_initialized.return_value = True
    mcp_service.get_configured_server_names.return_value = [
        "pygeomodels",
        "calculator",
    ]

    result = await list_mcp_servers(
        current_user=current_user,
        mcp_service=mcp_service,
    )

    assert result == {
        "success": True,
        "code": 2000,
        "message": "成功",
        "data": {
            "initialized": True,
            "servers": [
                {"name": "pygeomodels"},
                {"name": "calculator"},
            ],
        },
    }
    mcp_service.is_mcp_initialized.assert_called_once_with()
    mcp_service.get_configured_server_names.assert_called_once_with()


@pytest.mark.asyncio
async def test_list_mcp_servers_still_exposes_configured_names_before_init():
    current_user = MagicMock(user_id="user-1")
    mcp_service = MagicMock()
    mcp_service.is_mcp_initialized.return_value = False
    mcp_service.get_configured_server_names.return_value = ["pygeomodels"]

    result = await list_mcp_servers(
        current_user=current_user,
        mcp_service=mcp_service,
    )

    assert result["data"] == {
        "initialized": False,
        "servers": [{"name": "pygeomodels"}],
    }


def test_mcp_server_discovery_route_is_get_only():
    route = next(route for route in router.routes if route.path == "/mcp/servers")

    assert route.methods == {"GET"}
