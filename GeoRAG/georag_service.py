import os
import logging
import uuid
from flask import jsonify, send_from_directory
import yaml
from werkzeug.utils import secure_filename
from GeoRAG.RAGAgent import ask_agent, create_db, delete_database, get_all_databases, save_uploaded_file


class GeoRAGService:
    def __init__(self):
        self.vector_dbs = {}  # 存储已加载的向量数据库
        self.default_embed_model = "text-embedding-v3"
        self.default_chat_model = "qwen-turbo"
        self.allowed_extensions = {'csv', 'json', 'txt'}
        
        # 设置上传目录
        self.upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'documents')
        os.makedirs(self.upload_folder, exist_ok=True)
        
    def allowed_file(self, filename):
        """检查文件是否允许上传"""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def get_available_embedding_models(self):
        """
        获取当前系统中可用的嵌入模型列表。
        返回包含模型信息的列表
        """
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
        返回包含模型信息的列表
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
        返回知识库列表
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
        返回成功或失败的消息
        """
        
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
                        filename = secure_filename(file.filename)
                        # 添加随机字符串避免文件名冲突
                        unique_filename = f"{uuid.uuid4().hex}_{filename}"
                        file_path = save_uploaded_file(file, unique_filename)
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
    
    def add_files_to_database(self, request):
        """
        向已有知识库添加新文件
        请求参数:
            db_name: 知识库名称
            files: 要添加的文件列表
        返回值:
            成功或失败的消息
        """
        # 获取请求参数
        db_name = request.form.get("db_name")
        
        # 验证必要参数
        if not db_name:
            return jsonify({"error": "db_name is required"}), 400
        
        # 验证知识库是否存在
        if db_name not in self.vector_dbs:
            return jsonify({"error": f"Database '{db_name}' not found"}), 404
        
        # 处理上传的文件
        file_paths = []
        if 'files' in request.files:
            files = request.files.getlist('files')
            for file in files:
                if file and self.allowed_file(file.filename):
                    # 安全地获取文件名并保存
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    file_path = save_uploaded_file(file, unique_filename)
                    file_paths.append(file_path)
        
        # 更新知识库
        try:
            self.vector_dbs[db_name].add_files(file_paths)  # 假设 VectorDB 支持 add_files 方法
            return jsonify({
                "message": f"Files added to database '{db_name}' successfully",
                "db_name": db_name,
                "files_processed": len(file_paths)
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def delete_db(self,db_name):
        """
        删除指定知识库
        路径参数:
            db_name: 知识库名称
        返回值:
            成功或失败的消息
        """
        try:
            # 从内存中移除
            if db_name in self.vector_dbs:
                del self.vector_dbs[db_name]
            
            # 从磁盘中删除
            success = delete_database(db_name)
            if success:
                return jsonify({"message": f"Database '{db_name}' deleted successfully"}), 200
            else:
                return jsonify({"error": f"Database '{db_name}' not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def get_documents(self):
        """
        获取documents目录下的所有文件的列表，仅名称
        返回值:
            文件列表
        """
        try:
            print(self.upload_folder)
            if not os.path.exists(self.upload_folder):
                return {"documents": []}  # 直接返回字典而不是使用 jsonify
            documents = [f for f in os.listdir(self.upload_folder) if os.path.isfile(os.path.join(self.upload_folder, f))]
            return {"documents": documents}  # 直接返回字典而不是使用 jsonify
        except Exception as e:
            return {"error": str(e)}, 500  # 错误情况下也直接返回字典

    def download_document(self, filename):
        """
        下载指定文件
        路径参数:
            filename: 文件名
        返回值:
            文件内容
        """
        try:
            return send_from_directory(self.upload_folder, filename)
        except Exception as e:
            return jsonify({"error": str(e)}), 500


    def delete_document(self, filename):
        """
        删除指定文件
        路径参数:
            filename: 文件名
        返回值:
            成功或失败的消息
        """
        try:
            file_path = os.path.join(self.upload_folder, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                return jsonify({"message": f"Document '{filename}' deleted successfully"}), 200
            else:
                return jsonify({"error": f"Document '{filename}' not found"}), 404
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
        api_key = os.environ.get("OPENAI_API_KEY")  # 使用环境变量中的 API 密钥
        api_base = os.environ.get("OPENAI_API_BASE")  # 使用环境变量中的 API 基础 URL
        
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
            print("db",vector_db)
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

