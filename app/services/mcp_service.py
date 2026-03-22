"""
MCP工具服务
负责MCP工具的初始化和管理

使用 streamable_http 传输，MCP 服务器作为独立的 HTTP 服务运行。
MultiServerMCPClient only stores connection config — no persistent connections
are held. Each get_tools() call opens and closes its own ephemeral session.
"""

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

from langchain_mcp_adapters.client import MultiServerMCPClient

from ..utils.config import AppConfig
from .base_service import BaseService

logger = logging.getLogger(__name__)

# MCP server configuration is loaded from the MCP_CONFIG env variable (JSON string).
# See .env.example for the expected format.
MCP_CONFIG: dict = AppConfig.MCP_CONFIG


class MCPService(BaseService):
    """MCP工具服务类"""

    def __init__(self):
        super().__init__()
        self.mcp_tools: Optional[List] = None
        self.mcp_client: Optional[MultiServerMCPClient] = None

    async def init_mcp_tools(self):
        """
        初始化 MCP 工具

        MultiServerMCPClient stores connection config only; it holds no persistent
        connections. Each get_tools() call opens an ephemeral session that closes
        automatically after the call completes.
        """
        logger.info("开始初始化 MCP 工具...")
        try:
            # 创建客户端并保持引用
            self.mcp_client = MultiServerMCPClient(MCP_CONFIG)
            logger.info(f"MultiServerMCPClient 创建成功: {self.mcp_client}")
            # 加载工具
            self.mcp_tools = await self.mcp_client.get_tools()

            self.log_info(
                f"MCP工具初始化成功，共 {len(self.mcp_tools)} 个工具，"
                f"已连接 {len(MCP_CONFIG)} 个服务器"
            )
        except Exception as e:
            # anyio TaskGroup wraps sub-exceptions in an ExceptionGroup.
            # Unwrap one level to surface the actual root cause in the log line.
            inner: BaseException = e
            if hasattr(e, "exceptions") and e.exceptions:  # type: ignore[union-attr]
                inner = e.exceptions[0]  # type: ignore[union-attr]
            logger.error("MCP init failed: %s", inner)
            logger.debug("MCP init full traceback:", exc_info=True)
            self.mcp_tools = []
            self.mcp_client = None

    async def reload_mcp_tools(self) -> List:
        """
        重新加载 MCP 工具

        当工具列表可能变化时调用。

        Returns:
            重新加载后的工具列表
        """
        if self.mcp_client:
            try:
                self.mcp_tools = await self.mcp_client.get_tools()
                self.log_info(f"MCP工具重新加载完成，共 {len(self.mcp_tools)} 个工具")
            except Exception as e:
                self.log_error(f"MCP工具重新加载失败: {e}")
                self.mcp_tools = []
        return self.mcp_tools or []

    def get_mcp_tools(self) -> Optional[List]:
        """
        获取MCP工具列表

        Returns:
            MCP工具列表
        """
        return self.mcp_tools

    def get_mcp_client(self) -> Optional[MultiServerMCPClient]:
        """
        获取MCP客户端实例

        Returns:
            MCP客户端实例
        """
        return self.mcp_client

    def _build_mcp_config_with_bearer(self, token: str) -> Dict[str, Any]:
        """
        基于全局 MCP_CONFIG 构建带 Authorization 请求头的配置。

        注意：为了避免全局污染，这里会深拷贝配置并仅在副本上写入 headers。
        """
        config_copy: Dict[str, Any] = deepcopy(MCP_CONFIG)
        for _, server_cfg in config_copy.items():
            if isinstance(server_cfg, dict):
                headers = server_cfg.get("headers")
                if not isinstance(headers, dict):
                    headers = {}
                headers["Authorization"] = f"Bearer {token}"
                server_cfg["headers"] = headers
        return config_copy

    async def get_mcp_tools_for_token(self, token: str) -> List:
        """
        按请求动态构建 MCP 工具（携带 Bearer Token）。

        该方法用于需要将用户 token 透传到 MCP Server 的场景。
        不会更新全局缓存的 mcp_client/mcp_tools，避免跨用户 token 污染。

        Args:
            token: Bearer token（不含 "Bearer " 前缀）

        Returns:
            按 token 构建得到的工具列表。失败时返回空列表。
        """
        if not token:
            return self.get_mcp_tools() or []

        try:
            config_with_headers = self._build_mcp_config_with_bearer(token)
            ephemeral_client = MultiServerMCPClient(config_with_headers)
            tools = await ephemeral_client.get_tools()
            self.log_info(f"按请求构建 MCP 工具成功，共 {len(tools)} 个工具")
            return tools
        except Exception as e:
            inner: BaseException = e
            if hasattr(e, "exceptions") and e.exceptions:  # type: ignore[union-attr]
                inner = e.exceptions[0]  # type: ignore[union-attr]
            logger.error("MCP tokenized tools failed: %s", inner)
            logger.debug("MCP tokenized tools full traceback:", exc_info=True)
            return []

    def is_mcp_initialized(self) -> bool:
        """
        检查MCP是否已初始化

        Returns:
            是否已初始化
        """
        result = self.mcp_client is not None and self.mcp_tools is not None
        if not result:
            logger.debug(
                "MCP not initialized: client=%s, tools_loaded=%s",
                self.mcp_client is not None,
                self.mcp_tools is not None,
            )
        return result

    async def cleanup(self):
        """
        清理 MCP 资源

        在应用关闭时调用。
        MultiServerMCPClient holds no persistent connections (each get_tools() call
        uses an ephemeral session that is closed automatically). The class has no
        aclose() method and its __aexit__ raises NotImplementedError. Dropping the
        reference is therefore the correct and complete cleanup.
        """
        self.mcp_client = None
        self.mcp_tools = None
        self.log_info("MCP 资源引用已清理")
