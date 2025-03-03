# 导入必要的库
import os
from flask import Flask, logging, request, jsonify, send_from_directory
import yaml
import uuid
from werkzeug.utils import secure_filename
from RAGAgent import create_db, ask_agent, get_all_databases, delete_database, save_uploaded_file

# 初始化 Flask 应用
app = Flask(__name__)

# 配置全局变量
VECTOR_DBS = {}  # 存储已加载的向量数据库
DEFAULT_EMBED_MODEL = "llama3.1"
DEFAULT_CHAT_MODEL = "qwen-turbo"
ALLOWED_EXTENSIONS = {'csv', 'json', 'txt'}  # 允许上传的文件类型

# 确保上传目录存在
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'documents')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上传文件大小为16MB

def allowed_file(filename):
    """检查文件是否允许上传"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_available_embedding_models():
    """
    获取当前系统中可用的嵌入模型列表。
    :return: 包含模型信息的列表
    """
    try:
        with open('models.yaml', 'r') as f:
            config = yaml.safe_load(f)
        return [model["name"] for model in config.get("embedding_models", [])]
    except Exception as e:
        # 记录错误日志
        logging.error(f"加载嵌入模型失败: {e}")
        return []
    
def get_available_chat_models():
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
      
@app.route("/create_db", methods=["POST"])
def create_database():
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
    if model_name not in get_available_embedding_models():
        return jsonify({"error": f"Embedding model '{model_name}' is not available"}), 400
    
    try:
        # 处理上传的文件
        file_paths = []
        if 'files' in request.files:
            files = request.files.getlist('files')
            for file in files:
                if file and allowed_file(file.filename):
                    # 安全地获取文件名并保存
                    filename = secure_filename(file.filename)
                    # 添加随机字符串避免文件名冲突
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    file_path = save_uploaded_file(file, unique_filename)
                    file_paths.append(file_path)
        
        # 创建数据库
        VECTOR_DBS[db_name] = create_db(model_name, db_name, file_paths)
        return jsonify({
            "message": f"Database '{db_name}' created successfully",
            "db_name": db_name,
            "model_name": model_name,
            "files_processed": len(file_paths)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ask", methods=["POST"])
def ask_question():
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
    global VECTOR_DBS
    
    # 获取请求参数
    query = request.json.get("query")
    db_name = request.json.get("db_name")
    use_api = True  # 默认使用 API
    api_key = os.environ.get("QWEN_API_KEY")  # 使用环境变量中的 API 密钥
    api_base = os.environ.get("QWEN_API_BASE")  # 使用环境变量中的 API 基础 URL
    
    # 获取用户指定的模型名称
    embed_model_name = request.json.get("embed_model_name", DEFAULT_EMBED_MODEL)
    chat_model_name = request.json.get("chat_model_name", DEFAULT_CHAT_MODEL)
    
    # 验证必要参数
    if not query:
        return jsonify({"error": "query is required"}), 400
    if not db_name:
        return jsonify({"error": "db_name is required"}), 400
    
    # 验证模型是否存在
    if embed_model_name not in get_available_embedding_models():
        return jsonify({"error": f"Embedding model '{embed_model_name}' is not available"}), 400
    if chat_model_name not in get_available_chat_models():
        return jsonify({"error": f"Chat model '{chat_model_name}' is not available"}), 400
    
    try:
        # 获取向量数据库
        vector_db = VECTOR_DBS.get(db_name)
        
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

@app.route('/databases', methods=['GET'])
def get_databases():
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

@app.route('/databases/<db_name>', methods=['DELETE'])
def delete_db(db_name):
    """
    删除指定知识库
    路径参数:
        db_name: 知识库名称
    返回值:
        成功或失败的消息
    """
    global VECTOR_DBS
    try:
        # 从内存中移除
        if db_name in VECTOR_DBS:
            del VECTOR_DBS[db_name]
        
        # 从磁盘中删除
        success = delete_database(db_name)
        if success:
            return jsonify({"message": f"Database '{db_name}' deleted successfully"}), 200
        else:
            return jsonify({"error": f"Database '{db_name}' not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/documents', methods=['GET'])
def list_documents():
    """
    获取documents目录下的所有文件
    返回值:
        文件列表
    """
    try:
        documents_dir = app.config['UPLOAD_FOLDER']
        files = [f for f in os.listdir(documents_dir) if os.path.isfile(os.path.join(documents_dir, f))]
        return jsonify({"documents": files}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/documents/<filename>', methods=['GET'])
def download_document(filename):
    """
    下载指定文件
    路径参数:
        filename: 文件名
    返回值:
        文件内容
    """
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/documents/<filename>', methods=['DELETE'])
def delete_document(filename):
    """
    删除指定文件
    路径参数:
        filename: 文件名
    返回值:
        成功或失败的消息
    """
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({"message": f"Document '{filename}' deleted successfully"}), 200
        else:
            return jsonify({"error": f"Document '{filename}' not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/embedding_models', methods=['GET'])
def get_embedding_models():
    with open('models.yaml', 'r') as f:
        config = yaml.safe_load(f)
    return jsonify(config.get("embedding_models", []))

@app.route('/chat_models', methods=['GET'])
def get_chat_models():
    with open('models.yaml', 'r') as f:
        config = yaml.safe_load(f)
    return jsonify(config.get("chat_models", []))

if __name__ == "__main__":
    app.run(debug=True)