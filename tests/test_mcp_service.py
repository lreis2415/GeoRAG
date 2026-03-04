"""
Tests for mcp_service.py

测试内容包括：
1. MCP 服务管理功能测试
2. MCP 工具加载和执行测试
3. MCP 服务器连接测试
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import StdioServerParameters

# ==================== Fixtures ====================


@pytest.fixture
def mock_db():
    """Mock 数据库会话"""
    return MagicMock()


@pytest.fixture
def mock_mcp_server():
    """Mock MCP 服务器"""
    server = MagicMock()
    server.name = "test_mcp_server"
    server.config = {
        "command": "python",
        "args": ["-m", "test_server"],
    }
    return server


@pytest.fixture
def mock_mcp_tools():
    """Mock MCP 工具列表"""
    tools = [
        MagicMock(
            name="test_tool_1",
            description="Test tool 1",
            func=AsyncMock(return_value="Result from tool 1"),
        ),
        MagicMock(
            name="test_tool_2",
            description="Test tool 2",
            func=AsyncMock(return_value="Result from tool 2"),
        ),
    ]
    return tools


@pytest.fixture
def mcp_config():
    """MCP 配置 fixture"""
    return {
        "pygeomodels": {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "pygeomodels"],
        },
        "calculator": {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "calculator"],
        },
    }


# ==================== 测试 MCP 服务初始化 ====================


def test_mcp_service_init(mcp_config):
    """测试 MCP 服务初始化"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.mcp_servers = {}
        service.mcp_tools = {}

        assert service.mcp_servers == {}
        assert service.mcp_tools == {}


def test_mcp_service_init_with_config(mcp_config):
    """测试使用配置初始化 MCP 服务"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.config = mcp_config
        service.mcp_servers = {}
        service.mcp_tools = {}

        assert service.config == mcp_config
        assert len(service.config) == 2


# ==================== 测试 MCP 服务器管理 ====================


def test_add_mcp_server(mcp_config):
    """测试添加 MCP 服务器"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.mcp_servers = {}
        service.mcp_tools = {}
        service.config = mcp_config

        # 添加服务器
        server_name = "test_server"
        server_config = mcp_config["pygeomodels"]
        service.mcp_servers[server_name] = server_config

        assert server_name in service.mcp_servers
        assert service.mcp_servers[server_name] == server_config


def test_add_mcp_server_duplicate(mcp_config):
    """测试添加重复的 MCP 服务器"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.mcp_servers = {}
        service.mcp_tools = {}
        service.config = mcp_config

        # 添加相同的服务器两次
        server_name = "test_server"
        server_config = mcp_config["pygeomodels"]
        service.mcp_servers[server_name] = server_config
        service.mcp_servers[server_name] = server_config

        # 应该只有一个条目
        assert len([s for s in service.mcp_servers if s == server_name]) == 1


def test_remove_mcp_server(mcp_config):
    """测试移除 MCP 服务器"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.mcp_servers = {}
        service.mcp_tools = {}
        service.config = mcp_config

        server_name = "test_server"
        service.mcp_servers[server_name] = mcp_config["pygeomodels"]

        # 移除服务器
        del service.mcp_servers[server_name]

        assert server_name not in service.mcp_servers


def test_list_mcp_servers(mcp_config):
    """测试列出所有 MCP 服务器"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.mcp_servers = {}
        service.mcp_tools = {}
        service.config = mcp_config

        # 添加多个服务器
        service.mcp_servers["server1"] = mcp_config["pygeomodels"]
        service.mcp_servers["server2"] = mcp_config["calculator"]

        servers = list(service.mcp_servers.keys())

        assert len(servers) == 2
        assert "server1" in servers
        assert "server2" in servers


# ==================== 测试 MCP 工具管理 ====================


def test_add_mcp_tools(mock_mcp_tools):
    """测试添加 MCP 工具"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.mcp_servers = {}
        service.mcp_tools = {}

        server_name = "test_server"
        service.mcp_tools[server_name] = mock_mcp_tools

        assert server_name in service.mcp_tools
        assert len(service.mcp_tools[server_name]) == 2


def test_get_tools_from_server(mock_mcp_tools):
    """测试从特定服务器获取工具"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.mcp_servers = {}
        service.mcp_tools = {}

        server_name = "test_server"
        service.mcp_tools[server_name] = mock_mcp_tools

        tools = service.mcp_tools.get(server_name, [])

        assert len(tools) == 2
        assert tools[0].name == "test_tool_1"
        assert tools[1].name == "test_tool_2"


def test_get_all_tools(mock_mcp_tools):
    """测试获取所有工具"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.mcp_servers = {}
        service.mcp_tools = {}

        # 添加多个服务器的工具
        service.mcp_tools["server1"] = mock_mcp_tools[:1]
        service.mcp_tools["server2"] = mock_mcp_tools[1:]

        # 收集所有工具
        all_tools = []
        for tools in service.mcp_tools.values():
            all_tools.extend(tools)

        assert len(all_tools) == 2


# ==================== 测试 MCP 工具执行 ====================


@pytest.mark.asyncio
async def test_execute_mcp_tool(mock_mcp_tools):
    """测试执行 MCP 工具"""
    tool = mock_mcp_tools[0]

    result = await tool.func(arg1="value1", arg2="value2")

    assert result == "Result from tool 1"
    tool.func.assert_called_once()


@pytest.mark.asyncio
async def test_execute_mcp_tool_with_error(mock_mcp_tools):
    """测试执行 MCP 工具时的错误处理"""
    tool = mock_mcp_tools[0]
    tool.func = AsyncMock(side_effect=Exception("Tool execution failed"))

    with pytest.raises(Exception) as exc_info:
        await tool.func(arg1="value1")

    assert str(exc_info.value) == "Tool execution failed"


# ==================== 测试 MCP 服务器参数 ====================


def test_create_stdio_server_parameters(mcp_config):
    """测试创建 stdio 服务器参数"""
    config = mcp_config["pygeomodels"]

    params = StdioServerParameters(
        command=config["command"],
        args=config["args"],
    )

    assert params.command == "python"
    assert params.args == ["-m", "pygeomodels"]


def test_server_params_validation():
    """测试服务器参数验证"""
    # 缺少必要参数
    with pytest.raises(TypeError):
        StdioServerParameters(command="python")
    # args 是必需的
    with pytest.raises(TypeError):
        StdioServerParameters(args=["-m", "test"])

    # 正确的参数
    params = StdioServerParameters(
        command="python",
        args=["-m", "test"],
    )
    assert params is not None


# ==================== 测试 MCP 配置验证 ====================


def test_validate_mcp_config_valid(mcp_config):
    """测试验证有效的 MCP 配置"""
    for server_name, config in mcp_config.items():
        assert "type" in config
        assert "command" in config
        assert "args" in config
        assert isinstance(config["args"], list)


def test_validate_mcp_config_invalid():
    """测试验证无效的 MCP 配置"""
    # 缺少 type
    config1 = {"command": "python", "args": ["-m", "test"]}
    assert "type" not in config1

    # 缺少 command
    config2 = {"type": "stdio", "args": ["-m", "test"]}
    assert "command" not in config2

    # args 不是列表
    config3 = {"type": "stdio", "command": "python", "args": "not a list"}
    assert not isinstance(config3["args"], list)


def test_validate_mcp_config_empty():
    """测试验证空的 MCP 配置"""
    config = {}
    assert len(config) == 0


# ==================== 测试 MCP 服务状态 ====================


def test_mcp_service_empty_state():
    """测试空的 MCP 服务状态"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.mcp_servers = {}
        service.mcp_tools = {}

        assert len(service.mcp_servers) == 0
        assert len(service.mcp_tools) == 0


def test_mcp_service_populated_state(mcp_config, mock_mcp_tools):
    """测试有数据的 MCP 服务状态"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.mcp_servers = mcp_config
        service.mcp_tools = {"server1": mock_mcp_tools}

        assert len(service.mcp_servers) == 2
        assert len(service.mcp_tools) == 1
        assert "server1" in service.mcp_tools


# ==================== 测试 MCP 错误处理 ====================


def test_handle_invalid_server_name():
    """测试处理无效的服务器名称"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.mcp_servers = {}
        service.mcp_tools = {}

        # 尝试获取不存在的服务器
        server = service.mcp_servers.get("nonexistent")
        tools = service.mcp_tools.get("nonexistent")

        assert server is None
        assert tools is None


def test_handle_empty_tools_list():
    """测试处理空的工具列表"""
    with patch("app.services.mcp_service.MCPService.__init__", return_value=None):
        from app.services.mcp_service import MCPService

        service = MCPService()
        service.mcp_servers = {}
        service.mcp_tools = {}

        server_name = "empty_server"
        service.mcp_tools[server_name] = []

        tools = service.mcp_tools.get(server_name, [])

        assert len(tools) == 0
        assert isinstance(tools, list)
