"""
RAG问答服务
负责RAG智能问答功能
"""

import os
from typing import Dict, Optional

from dao.DataBase import ask_agent

from .base_service import BaseService


class RAGService(BaseService):
    """RAG问答服务类 - 专注于知识库问答"""

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
