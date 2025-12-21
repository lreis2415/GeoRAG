import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import yaml
from fastapi import HTTPException
from fastapi.responses import FileResponse, JSONResponse
from langchain.memory import ConversationBufferMemory
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain.schema.messages import BaseMessage
from langchain.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from werkzeug.utils import secure_filename

from GeoRAGService.RAGAgent import (
    ask_agent,
    create_db,
    delete_database,
    get_all_databases,
    save_uploaded_file,
)

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
        "transport": "stdio",
    },
    "pygeomodels": {
        "command": "/opt/homebrew/Caskroom/miniconda/base/envs/pygeomodels/bin/python",
        "args": ["/Users/wuchenglong/Desktop/EGC/pygeomodels/pygeomodels_service.py"],
        "transport": "stdio",
    },
}


# Function Call tool 封装示例（实际上本项目没用到，仅供学习参考）
# 使用时，仅需将 self.mcp_tools = None 改为 self.mcp_tools = tools 即可
# 查询当前时间的工具。返回结果示例：“当前时间：2024-04-15 17:15:18。“
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


tools = [get_current_time]


class GeoRAGService:
    def __init__(self):
        self.vector_dbs = {}  # 存储已加载的向量数据库
        self.default_embed_model = "text-embedding-v3"
        self.default_chat_model = "qwen-turbo-latest"
        self.allowed_extensions = {"csv", "json", "txt"}
        # 初始化MCP适配器
        self.mcp_tools = None
        self.mcp_session = None
        self.mcp_config = MCP_CONFIG["calculator-mcp"]
        self.mcp_server_params = StdioServerParameters(
            command=self.mcp_config["command"],
            args=self.mcp_config["args"],
        )

        # 设置上传目录
        self.upload_folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "documents"
        )
        os.makedirs(self.upload_folder, exist_ok=True)

        # 添加会话管理
        self.chat_sessions = (
            {}
        )  # 存储会话记录 {session_id: {"memory": ConversationBufferMemory, "created_at": datetime, "last_active": datetime}}
        self.max_sessions = 100  # 最大会话数
        self.max_memory_length = 20  # 每个会话最大记忆轮次

    async def _init_mcp_tools(self):
        """初始化 MCP 工具"""
        # 思路1：创建 MCP 客户端，client.get_tools()，成功！
        client = MultiServerMCPClient(MCP_CONFIG)
        # 加载 MCP 工具
        self.mcp_tools = await client.get_tools()
        self.mcp_session = client
        logging.info("MCP tools initialized successfully.")

        # 思路2：创建 MCP 客户端，load_mcp_tools(session)，没有成功
        # client = MultiServerMCPClient(MCP_CONFIG)
        # async with client.session("calculator-mcp") as session:
        #     tools = await load_mcp_tools(session)
        #     self.mcp_tools = tools
        #     self.mcp_session = session
        #     logging.info("MCP tools initialized successfully.")

        # 思路3：启动 MCP 服务器会话并加载工具，load_mcp_tools(session)，没有成功

        # try:
        #     async with stdio_client(self.mcp_server_params) as (read, write):
        #         async with ClientSession(read, write) as session:
        #             await session.initialize()
        #             # 加载 MCP 工具
        #             tools = await load_mcp_tools(session)
        #             self.mcp_tools = tools
        #             self.mcp_session = session
        #             logging.info("MCP tools initialized successfully.")
        # except Exception as e:
        #     logging.error(f"Failed to initialize MCP tools: {e}")
        #     self.mcp_tools = []
        #     self.mcp_session = None

    def allowed_file(self, filename):
        """检查文件是否允许上传"""
        return (
            "." in filename
            and filename.rsplit(".", 1)[1].lower() in self.allowed_extensions
        )

    def _create_session(self, session_id: str = None) -> str:
        """创建或获取会话"""
        if session_id is None:
            session_id = str(uuid.uuid4())

        if session_id not in self.chat_sessions:
            # 检查会话数量限制
            if len(self.chat_sessions) >= self.max_sessions:
                self._cleanup_old_sessions()

            # 创建新会话
            memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                max_token_limit=4000,  # 控制token数量
            )

            self.chat_sessions[session_id] = {
                "memory": memory,
                "created_at": datetime.now(),
                "last_active": datetime.now(),
                "message_count": 0,
            }

        return session_id

    def _cleanup_old_sessions(self):
        """清理最老的会话"""
        # 按最后活跃时间排序，删除最老的会话
        sorted_sessions = sorted(
            self.chat_sessions.items(), key=lambda x: x[1]["last_active"]
        )

        # 删除最老的10个会话
        for session_id, _ in sorted_sessions[:10]:
            del self.chat_sessions[session_id]

    def _update_session_activity(self, session_id: str):
        """更新会话活跃时间"""
        if session_id in self.chat_sessions:
            self.chat_sessions[session_id]["last_active"] = datetime.now()

    def _add_to_memory(self, session_id: str, human_message: str, ai_message: str):
        """添加对话到记忆中"""
        if session_id in self.chat_sessions:
            session = self.chat_sessions[session_id]
            memory = session["memory"]

            # 添加到记忆中
            memory.chat_memory.add_user_message(human_message)
            memory.chat_memory.add_ai_message(ai_message)

            # 更新消息计数
            session["message_count"] += 1

            # 如果消息数量超过限制，删除最早的消息
            if session["message_count"] > self.max_memory_length:
                messages = memory.chat_memory.messages
                if len(messages) > 4:  # 至少保留2轮对话
                    memory.chat_memory.messages = messages[2:]  # 删除最早的一轮对话
                    session["message_count"] -= 1

    def _get_conversation_history(self, session_id: str) -> List[BaseMessage]:
        """获取会话历史"""
        if session_id in self.chat_sessions:
            return self.chat_sessions[session_id]["memory"].chat_memory.messages
        return []

    def get_chat_sessions(self):
        """获取所有会话信息"""
        sessions_info = {}
        for session_id, session in self.chat_sessions.items():
            sessions_info[session_id] = {
                "created_at": session["created_at"].isoformat(),
                "last_active": session["last_active"].isoformat(),
                "message_count": session["message_count"],
            }
        return sessions_info

    def delete_chat_session(self, session_id: str):
        """删除指定会话"""
        if session_id in self.chat_sessions:
            del self.chat_sessions[session_id]
            return True
        return False

    def clear_all_sessions(self):
        """清空所有会话"""
        self.chat_sessions.clear()

    def get_available_embedding_models(self):
        """
        获取当前系统中可用的嵌入模型列表。
        返回包含模型信息的列表
        """
        try:
            with open("models.yaml", "r") as f:
                config = yaml.safe_load(f)
            return [model["name"] for model in config.get("embedding_models", [])]
        except Exception as e:
            logging.error(f"加载嵌入模型失败: {e}")
            return []

    def get_available_chat_models(self):
        """
        获取当前系统中可用的聊天模型列表。
        返回包含模型信息的列表
        """
        try:
            with open("models.yaml", "r") as f:
                config = yaml.safe_load(f)
            return [model["name"] for model in config.get("chat_models", [])]
        except Exception as e:
            # 记录错误日志
            logging.error(f"加载聊天模型失败: {e}")
            return []

    def get_databases(self):
        """
        获取所有知识库列表
        返回知识库列表
        """
        databases = get_all_databases()
        return {"databases": databases}

    def create_database(self, model_name, db_name, files=None):
        """
        创建向量数据库的接口
        参数:
            model_name: 嵌入模型名称
            db_name: 数据库名称
            files: 要上传的文件列表 (可选)
        返回成功消息和相关信息
        """

        # 验证必要参数
        if not model_name:
            raise ValueError("model_name is required")
        if not db_name:
            raise ValueError("db_name is required")

        # 验证模型是否存在
        if model_name not in self.get_available_embedding_models():
            raise ValueError(f"Embedding model '{model_name}' is not available")

        # 处理上传的文件
        file_paths = []
        if files:
            for file in files:
                if file and self.allowed_file(file.filename):
                    # 安全地获取文件名并保存
                    filename = secure_filename(file.filename)
                    # 添加随机字符串避免文件名冲突
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    file_path = save_uploaded_file(file, unique_filename)
                    file_paths.append(file_path)

        # 创建数据库
        self.vector_dbs[db_name] = create_db(model_name, db_name, file_paths)
        return {
            "message": f"Database '{db_name}' created successfully",
            "db_name": db_name,
            "model_name": model_name,
            "files_processed": len(file_paths),
        }

    def add_files_to_database(self, db_name, files):
        """
        向已有知识库添加新文件
        参数:
            db_name: 知识库名称
            files: 要添加的文件列表
        返回值:
            成功消息和相关信息
        """

        # 验证必要参数
        if not db_name:
            raise ValueError("db_name is required")

        # 验证知识库是否存在
        if db_name not in self.vector_dbs:
            raise ValueError(f"Database '{db_name}' not found")

        # 处理上传的文件
        file_paths = []
        if files:
            for file in files:
                if file and self.allowed_file(file.filename):
                    # 安全地获取文件名并保存
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    file_path = save_uploaded_file(file, unique_filename)
                    file_paths.append(file_path)

        # 更新知识库
        self.vector_dbs[db_name].add_files(
            file_paths
        )  # 假设 VectorDB 支持 add_files 方法
        return {
            "message": f"Files added to database '{db_name}' successfully",
            "db_name": db_name,
            "files_processed": len(file_paths),
        }

    def delete_db(self, db_name):
        """
        删除指定知识库
        参数:
            db_name: 知识库名称
        返回值:
            成功消息
        """
        # 从内存中移除
        if db_name in self.vector_dbs:
            del self.vector_dbs[db_name]

        # 从磁盘中删除
        success = delete_database(db_name)
        if not success:
            raise ValueError(f"Database '{db_name}' not found")

        return {"message": f"Database '{db_name}' deleted successfully"}

    def get_documents(self):
        """
        获取documents目录下的所有文件的列表，仅名称
        返回值:
            文件列表
        """
        if not os.path.exists(self.upload_folder):
            return {"documents": []}
        documents = [
            f
            for f in os.listdir(self.upload_folder)
            if os.path.isfile(os.path.join(self.upload_folder, f))
        ]
        return {"documents": documents}

    def download_document(self, filename):
        """
        下载指定文件
        路径参数:
            filename: 文件名
        返回值:
            文件内容
        """
        try:
            return FileResponse(path=os.path.join(self.upload_folder, filename))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def delete_document(self, filename):
        """
        删除指定文件
        参数:
            filename: 文件名
        返回值:
            成功消息
        """
        file_path = os.path.join(self.upload_folder, filename)
        if not os.path.exists(file_path):
            raise ValueError(f"Document '{filename}' not found")

        os.remove(file_path)
        return {"message": f"Document '{filename}' deleted successfully"}

    def ask_question(self, query, db_name, chat_model_name=None):
        """
        运行RAG智能体的接口
        参数:
            query: 用户查询
            db_name: 知识库名称
            chat_model_name: 聊天模型名称 (可选)
        返回值:
            智能体的回答
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

        # 验证模型是否存在
        if chat_model_name not in self.get_available_chat_models():
            raise ValueError(f"Chat model '{chat_model_name}' is not available")

        # 获取向量数据库
        vector_db = self.vector_dbs.get(db_name)
        print("db", vector_db)
        response = []

        def stream_response(chunk):
            if "agent" in chunk:
                agent_message = chunk["agent"]["messages"][0]
                if agent_message.content:
                    response.append(agent_message.content)
            elif "tools" in chunk:
                tool_message = chunk["tools"]["messages"][0]
                response.append(tool_message.content)  # 捕获工具消息内容

        ask_agent(
            chat_model_name=chat_model_name,
            query=query,
            use_api=use_api,
            api_key=api_key,
            api_base=api_base,
            vector_db=vector_db,
            callback=stream_response,  # 添加回调函数参数
        )
        return {"response": "\n".join(response)}

    async def chat_with_agent(
        self, prompt, query, chat_model_name=None, session_id=None, use_memory=True
    ):
        """
        纯对话智能体的接口 - 支持记忆功能
        参数:
            prompt: 系统提示词
            query: 用户查询
            chat_model_name: 聊天模型名称 (可选)
            session_id: 会话ID (可选，如果不提供则创建新会话)
            use_memory: 是否使用记忆功能 (可选，默认True)
        返回值:
            智能体的回答和会话ID
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

        # 验证模型是否存在
        if chat_model_name not in self.get_available_chat_models():
            raise ValueError(f"Chat model '{chat_model_name}' is not available")

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

        # 1.处理记忆
        if use_memory:
            # 创建或获取会话
            session_id = self._create_session(session_id)
            self._update_session_activity(session_id)

            # 获取历史对话
            history = self._get_conversation_history(session_id)

            # 构建消息列表
            messages = []

            # 添加系统提示词
            messages.append(SystemMessage(content=prompt))

            # 添加历史对话
            for msg in history:
                messages.append(msg)

            # 添加当前用户查询
            messages.append(HumanMessage(content=query))

            # 2. 加载 MCP 工具并创建 Agent
            agent = create_react_agent(llm, tools=self.mcp_tools)

            # 3. 运行 Agent
            result = await agent.ainvoke({"messages": messages})
            ai_response = result["messages"][-1].content

            # 4. 记忆入库
            self._add_to_memory(session_id, query, ai_response)

            return {
                "response": ai_response,
                "session_id": session_id,
                "message_count": self.chat_sessions[session_id]["message_count"],
            }

        else:
            # 不使用记忆，简单的一次性对话
            messages = [SystemMessage(content=prompt), HumanMessage(content=query)]

            response = llm.invoke(messages)
            return {"response": response.content}

    def get_chat_history(self, session_id):
        """
        获取会话历史记录
        参数:
            session_id: 会话ID
        返回值:
            历史对话记录
        """
        if not session_id:
            raise ValueError("session_id is required")

        if session_id not in self.chat_sessions:
            raise ValueError("Session not found")

        history = self._get_conversation_history(session_id)

        # 格式化历史记录
        formatted_history = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                formatted_history.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted_history.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                formatted_history.append({"role": "system", "content": msg.content})

        return {
            "session_id": session_id,
            "history": formatted_history,
            "message_count": self.chat_sessions[session_id]["message_count"],
        }
