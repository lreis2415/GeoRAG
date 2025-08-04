"""
MCP工具服务
负责MCP工具的初始化和管理
"""

import logging
from datetime import datetime
from typing import List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.tools import tool
from .base_service import BaseService

# MCP服务配置
MCP_CONFIG = {
    "calculator-mcp": {
        "command": "/opt/homebrew/bin/uv",
        "args": [
            "--directory",
            "/Users/wuchenglong/Documents/LLM/MCP-Geo",
            "run",
            "geo_cal.py"
        ],
        "transport": "stdio"
    },
    "pygeomodels": {
        "command": "/opt/homebrew/Caskroom/miniconda/base/envs/gptac_new/bin/python",
        "args": [
            "/Users/wuchenglong/Desktop/GraduationDesigh/pygeomodels/pygeomodels_service.py"
        ],
        "transport": "stdio"
    }
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
        self.mcp_tools = None
        self.mcp_session = None
        self.mcp_config = MCP_CONFIG["calculator-mcp"]
        self.mcp_server_params = StdioServerParameters(
            command=self.mcp_config["command"],
            args=self.mcp_config["args"],
        )
    
    async def init_mcp_tools(self):
        """
        初始化 MCP 工具
        
        思路1：创建 MCP 客户端，client.get_tools()，成功！
        """
        try:
            client = MultiServerMCPClient(MCP_CONFIG)   
            # 加载 MCP 工具
            self.mcp_tools = await client.get_tools()
            self.mcp_session = client
            self.log_info("MCP工具初始化成功")
        except Exception as e:
            self.log_error(f"MCP工具初始化失败: {e}")
            self.mcp_tools = []
            self.mcp_session = None
    
    def get_mcp_tools(self) -> Optional[List]:
        """
        获取MCP工具列表
        
        Returns:
            MCP工具列表
        """
        return self.mcp_tools
    
    def get_mcp_session(self):
        """
        获取MCP会话
        
        Returns:
            MCP会话实例
        """
        return self.mcp_session
    
    def is_mcp_initialized(self) -> bool:
        """
        检查MCP是否已初始化
        
        Returns:
            是否已初始化
        """
        return self.mcp_tools is not None and self.mcp_session is not None
    
    def get_example_tools(self) -> List:
        """
        获取示例工具列表（用于测试）
        
        Returns:
            示例工具列表
        """
        return tools