import os
import logging
import uuid
from flask import jsonify
import yaml

from GeoRAG.RAGAgent import ask_agent, create_db, get_all_databases


class GeoRAGService:
    def __init__(self):
        self.vector_dbs = {}  # 存储已加载的向量数据库
        self.default_embed_model = "llama3.1"
        self.default_chat_model = "qwen-turbo"
        self.allowed_extensions = {'csv', 'json', 'txt'}
        
        # 设置上传目录
        self.upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'documents')
        os.makedirs(self.upload_folder, exist_ok=True)
        
    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def get_available_embedding_models(self):
        try:
            with open('models.yaml', 'r') as f:
                config = yaml.safe_load(f)
            return [model["name"] for model in config.get("embedding_models", [])]
        except Exception as e:
            logging.error(f"加载嵌入模型失败: {e}")
            return []
            
    def get_available_chat_models(self):
        """
        获取当前系统中可用的聊天模型列表。
        :return: 包含模型信息的列表
        """
        try:
            with open('models.yaml', 'r') as f:
                config = yaml.safe_load(f)
            return [model["name"] for model in config.get("chat_models", [])]
        except Exception as e:
            # 记录错误日志
            logging.error(f"加载聊天模型失败: {e}")
            return []  

    def get_databases(self, request):
        """
        获取所有知识库列表
        返回值:
            知识库列表
        """
        try:
            databases = get_all_databases()
            return jsonify({"databases": databases}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def create_database(self, request):
        """
        创建向量数据库的接口
        请求参数:
            model_name: 嵌入模型名称
            db_name: 数据库名称
            files: 要上传的文件列表 (可选)
        返回值:
            成功或失败的消息
        """
        global VECTOR_DBS
        
        # 获取请求参数
        model_name = request.form.get("model_name")
        db_name = request.form.get("db_name")
        
        # 验证必要参数
        if not model_name:
            return jsonify({"error": "model_name is required"}), 400
        if not db_name:
            return jsonify({"error": "db_name is required"}), 400
        
        # 验证模型是否存在
        if model_name not in self.get_available_embedding_models():
            return jsonify({"error": f"Embedding model '{model_name}' is not available"}), 400
        
        try:
            # 处理上传的文件
            file_paths = []
            if 'files' in request.files:
                files = request.files.getlist('files')
                for file in files:
                    if file and self.allowed_file(file.filename):
                        # 安全地获取文件名并保存
                        filename = self.secure_filename(file.filename)
                        # 添加随机字符串避免文件名冲突
                        unique_filename = f"{uuid.uuid4().hex}_{filename}"
                        file_path = self.save_uploaded_file(file, unique_filename)
                        file_paths.append(file_path)
            
            # 创建数据库
            self.vector_dbs[db_name] = create_db(model_name, db_name, file_paths)
            return jsonify({
                "message": f"Database '{db_name}' created successfully",
                "db_name": db_name,
                "model_name": model_name,
                "files_processed": len(file_paths)
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    def ask_question(self, request):
        """
        运行RAG智能体的接口
        请求参数:
            query: 用户查询
            db_name: 知识库名称
            embed_model_name: 嵌入模型名称 (可选)
            chat_model_name: 聊天模型名称 (可选)
            use_api: 是否使用API (可选，默认True)
        返回值:
            智能体的回答
        """
        
        # 获取请求参数
        query = request.json.get("query")
        db_name = request.json.get("db_name")
        use_api = True  # 默认使用 API
        api_key = os.environ.get("QWEN_API_KEY")  # 使用环境变量中的 API 密钥
        api_base = os.environ.get("QWEN_API_BASE")  # 使用环境变量中的 API 基础 URL
        
        # 获取用户指定的模型名称
        embed_model_name = request.json.get("embed_model_name", self.default_embed_model)
        chat_model_name = request.json.get("chat_model_name", self.default_chat_model)
        
        # 验证必要参数
        if not query:
            return jsonify({"error": "query is required"}), 400
        if not db_name:
            return jsonify({"error": "db_name is required"}), 400
        
        # 验证模型是否存在
        if embed_model_name not in self.get_available_embedding_models():
            return jsonify({"error": f"Embedding model '{embed_model_name}' is not available"}), 400
        if chat_model_name not in self.get_available_chat_models():
            return jsonify({"error": f"Chat model '{chat_model_name}' is not available"}), 400
        
        try:
            # 获取向量数据库
            vector_db = self.vector_dbs.get(db_name)
            
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
                embed_model_name=embed_model_name,
                chat_model_name=chat_model_name,
                query=query,
                db_name=db_name,
                use_api=use_api,
                api_key=api_key,
                api_base=api_base,
                vector_db=vector_db,
                callback=stream_response  # 添加回调函数参数
            )
            return jsonify({"response": "\n".join(response)}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

