"""
MCP工具服务
负责MCP工具的初始化和管理

使用 streamable_http 传输，MCP 服务器作为独立的 HTTP 服务运行。
MultiServerMCPClient 内部管理连接复用，保持 client 实例存活即可。
"""

import logging
from datetime import datetime
from typing import List, Optional

from langchain.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient

from .base_service import BaseService

logger = logging.getLogger(__name__)

# MCP服务配置
MCP_CONFIG = {
    # calculator-mcp 也改为 HTTP 传输（可选）
    # "calculator-mcp": {
    #     "url": "http://localhost:8001/mcp",
    #     "transport": "streamable_http",
    # },
    # "calculator-mcp": {
    #     "command": "/opt/homebrew/bin/uv",
    #     "args": [
    #         "--directory",
    #         "/Users/wuchenglong/Documents/LLM/MCP-Geo",
    #         "run",
    #         "geo_cal.py",
    #     ],
    #     "transport": "stdio",
    # },
    "pygeomodels": {
        "url": "http://localhost:8050/mcp",
        "transport": "streamable_http",
    },
}


# Function Call tool 封装示例（实际上本项目没用到，仅供学习参考）
@tool("get_current_time", return_direct=True)
def get_current_time():
    """
    获取当前时间
    """
    # 获取当前日期和时间
    current_datetime = datetime.now()
    # 格式化当前日期和时间
    formatted_time = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
    # 返回格式化后的当前时间
    return f"当前时间：{formatted_time}。"


# 示例工具列表
tools = [get_current_time]


class MCPService(BaseService):
    """MCP工具服务类"""

    def __init__(self):
        super().__init__()
        self.mcp_tools: Optional[List] = None
        self.mcp_client: Optional[MultiServerMCPClient] = None
        # 移除 StdioServerParameters，不再需要

    async def init_mcp_tools(self):
        """
        初始化 MCP 工具

        MultiServerMCPClient 内部会管理连接的创建和复用。
        保持 client 实例存活，后续工具调用会自动复用已建立的连接。
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
            logger.error(f"MCP工具初始化失败: {e}", exc_info=True)
            self.log_error(f"MCP工具初始化失败: {e}")
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

    def get_mcp_session(self):
        """
        获取MCP客户端实例（兼容旧接口）

        Returns:
            MCP客户端实例
        """
        return self.mcp_client

    def is_mcp_initialized(self) -> bool:
        """
        检查MCP是否已初始化

        Returns:
            是否已初始化
        """
        result = self.mcp_client is not None and self.mcp_tools is not None
        if not result:
            logger.warning(
                f"MCP 未初始化: mcp_client={self.mcp_client}, mcp_tools={self.mcp_tools}"
            )
        return result

    async def cleanup(self):
        """
        清理 MCP 资源

        在应用关闭时调用。
        注意：MultiServerMCPClient 没有显式的 close 方法，
        当 client 对象被销毁时，底层的 stdio 进程会自动终止。
        """
        self.mcp_client = None
        self.mcp_tools = None
        self.log_info("MCP 资源引用已清理")

    def get_example_tools(self) -> List:
        """
        获取示例工具列表（用于测试）

        Returns:
            示例工具列表
        """
        return tools
