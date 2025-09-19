import asyncio
import logging
import os

from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

OPEN_API_KEY = os.getenv("OPENAI_API_KEY")
OPEN_API_BASE = os.getenv("OPENAI_API_BASE")

# MCP服务配置
MCP_CONFIG = {
    "calculator-mcp": {
        "command": "/opt/homebrew/bin/uv",
        "args": [
            "--directory",
            "/Users/wuchenglong/Documents/LLM/MCP-Geo",
            "run",
            "geo_cal.py",
        ],
    },
    "pygeomodels": {
        "command": "/opt/homebrew/Caskroom/miniconda/base/envs/gptac_new/bin/python",
        "args": [
            "/Users/wuchenglong/Desktop/GraduationDesigh/pygeomodels/pygeomodels_service.py"
        ],
    },
}
config = MCP_CONFIG["pygeomodels"]
server_params = StdioServerParameters(
    command=config["command"],
    args=config["args"],
)


# 主流程封装为异步函数
async def main():
    # 初始化 LLM
    llm = ChatOpenAI(
        model="qwen-turbo-latest",
        api_key=OPEN_API_KEY,
        base_url=OPEN_API_BASE,
    )

    # 启动 MCP 服务器会话并加载工具
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # 加载 MCP 工具
            tools = await load_mcp_tools(session)
            logging.info("MCP tools initialized successfully.")

            # 创建智能体
            agent = create_react_agent(llm, tools=tools)

            # 发送消息并获取响应
            response = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "what are the GIS models?"}]}
            )
            print(response)


# 入口
if __name__ == "__main__":
    # 运行主异步流程
    asyncio.run(main())
