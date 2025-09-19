"""
RAG问答服务
负责RAG智能问答和纯对话功能
"""

import os
from typing import Dict, List, Optional

from dao.DataBase import ask_agent
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from .base_service import BaseService


class RAGService(BaseService):
    """RAG问答服务类"""

    def __init__(self):
        super().__init__()
        self.default_chat_model = "qwen-turbo-latest"

    def ask_question(
        self, query: str, db_name: str, vector_db, chat_model_name: Optional[str] = None
    ) -> Dict:
        """
        运行RAG智能体的接口

        Args:
            query: 用户查询
            db_name: 知识库名称
            vector_db: 向量数据库实例
            chat_model_name: 聊天模型名称 (可选)

        Returns:
            智能体的回答

        Raises:
            ValueError: 参数验证失败
        """
        use_api = True  # 默认使用 API
        api_key = os.environ.get("OPENAI_API_KEY")  # 使用环境变量中的 API 密钥
        api_base = os.environ.get("OPENAI_API_BASE")  # 使用环境变量中的 API 基础 URL

        # 获取用户指定的模型名称
        if not chat_model_name:
            chat_model_name = self.default_chat_model

        # 验证必要参数
        if not query:
            raise ValueError("query is required")
        if not db_name:
            raise ValueError("db_name is required")

        self.log_info(f"开始RAG问答，模型: {chat_model_name}, 数据库: {db_name}")

        response = []

        def stream_response(chunk):
            """流式响应回调函数"""
            if "agent" in chunk:
                agent_message = chunk["agent"]["messages"][0]
                if agent_message.content:
                    response.append(agent_message.content)
            elif "tools" in chunk:
                tool_message = chunk["tools"]["messages"][0]
                response.append(tool_message.content)  # 捕获工具消息内容

        try:
            ask_agent(
                chat_model_name=chat_model_name,
                query=query,
                use_api=use_api,
                api_key=api_key,
                api_base=api_base,
                vector_db=vector_db,
                callback=stream_response,  # 添加回调函数参数
            )

            result = {"response": "\n".join(response)}
            self.log_info(f"RAG问答完成，响应长度: {len(result['response'])}")
            return result

        except Exception as e:
            self.log_error(f"RAG问答失败: {e}")
            raise

    async def chat_with_agent(
        self,
        prompt: str,
        query: str,
        mcp_tools: List,
        chat_model_name: Optional[str] = None,
        session_id: Optional[str] = None,
        use_memory: Optional[bool] = True,
        history: Optional[List] = None,
    ) -> Dict:
        """
        纯对话智能体的接口 - 支持记忆功能

        Args:
            prompt: 系统提示词
            query: 用户查询
            mcp_tools: MCP工具列表
            chat_model_name: 聊天模型名称 (可选)
            session_id: 会话ID (可选)
            use_memory: 是否使用记忆功能 (可选，默认True)
            history: 历史对话记录 (可选)

        Returns:
            智能体的回答和会话ID

        Raises:
            ValueError: 参数验证失败
        """
        use_api = True  # 默认使用 API
        api_key = os.environ.get("OPENAI_API_KEY")
        api_base = os.environ.get("OPENAI_API_BASE")

        if not chat_model_name:
            chat_model_name = self.default_chat_model

        # 验证必要参数
        if not prompt:
            raise ValueError("prompt is required")
        if not query:
            raise ValueError("query is required")

        self.log_info(f"开始聊天对话，模型: {chat_model_name}, 会话: {session_id}")

        try:
            # 创建LLM
            llm = (
                ChatOpenAI(
                    model=chat_model_name,
                    temperature=0.1,
                    verbose=True,
                    api_key=api_key,
                    base_url=api_base,
                )
                if use_api
                else ChatOllama(model=chat_model_name, temperature=0.1, verbose=True)
            )

            # 处理记忆
            if use_memory:
                # 构建消息列表
                messages = []

                # 添加系统提示词
                messages.append(SystemMessage(content=prompt))

                # 添加历史对话
                for msg in history:
                    messages.append(msg)

                # 添加当前用户查询
                messages.append(HumanMessage(content=query))

                # 加载 MCP 工具并创建 Agent
                agent = create_react_agent(llm, tools=mcp_tools)

                # 运行 Agent
                result = await agent.ainvoke({"messages": messages})
                ai_response = result["messages"][-1].content

                self.log_info(f"聊天对话完成，响应长度: {len(ai_response)}")

                return {"response": ai_response, "session_id": session_id}

            else:
                # 不使用记忆，简单的一次性对话
                messages = [SystemMessage(content=prompt), HumanMessage(content=query)]

                response = llm.invoke(messages)

                self.log_info(f"简单对话完成，响应长度: {len(response.content)}")

                return {"response": response.content}

        except Exception as e:
            self.log_error(f"聊天对话失败: {e}")
            raise
