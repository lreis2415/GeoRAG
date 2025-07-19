from flask import Flask, abort, request, send_file, jsonify
from waitress import serve
from dotenv import load_dotenv
from GeoRAGService.georag_service_flask import GeoRAGService
from flasgger import Swagger
import os

load_dotenv()
app = Flask(__name__)
app.debug = True

# 配置 Swagger
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs/"
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "GeoRAG API",
        "description": "基于RAG技术的地理信息问答系统API",
        "version": "1.0.0",
        "termsOfService": "",
        "contact": {
            "name": "GeoRAG Team",
            "url": "https://github.com/your-repo/GeoRAG",
        },
        "license": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        }
    },
    "host": "localhost:7512",
    "basePath": "/",
    "schemes": ["http"],
    "consumes": ["application/json", "multipart/form-data"],
    "produces": ["application/json"],
    "tags": [
        {
            "name": "健康检查",
            "description": "系统健康状态检查"
        },
        {
            "name": "模型管理",
            "description": "模型信息查询相关接口"
        },
        {
            "name": "数据库管理",
            "description": "向量数据库管理相关接口"
        },
        {
            "name": "文档管理",
            "description": "文档上传、下载、删除等管理接口"
        },
        {
            "name": "智能问答",
            "description": "RAG智能问答相关接口"
        },
        {
            "name": "会话管理",
            "description": "聊天会话管理相关接口"
        }
    ]
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

OPEN_API_KEY = os.getenv("OPENAI_API_KEY")
OPEN_API_BASE = os.getenv("OPENAI_API_BASE")
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL")
# 初始化服务
georag_service = GeoRAGService()

@app.route('/')
def start():
    """
    健康检查接口
    ---
    tags:
      - 健康检查
    summary: 系统健康状态检查
    description: 检查GeoRAG服务是否正常运行
    responses:
      200:
        description: 服务正常运行
        schema:
          type: object
          properties:
            status:
              type: string
              example: "running"
            message:
              type: string
              example: "GeoRAG服务正常运行"
            version:
              type: string
              example: "1.0.0"
    """
    return jsonify({
        "status": "running",
        "message": "GeoRAG服务正常运行",
        "version": "1.0.0"
    }), 200

@app.route('/models', methods=['GET'])
def get_models():
    """
    获取可用模型列表
    ---
    tags:
      - 模型管理
    summary: 获取系统可用的模型列表
    description: 获取系统中所有可用的嵌入模型和聊天模型
    responses:
      200:
        description: 成功获取模型列表
        schema:
          type: object
          properties:
            embedding_models:
              type: array
              items:
                type: string
              description: 可用的嵌入模型列表
              example:
                - "text-embedding-v3"
                - "text-embedding-ada-002"
            chat_models:
              type: array
              items:
                type: string
              description: 可用的聊天模型列表
              example:
                - "qwen-turbo-latest"
                - "deepseek-v3"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "获取模型列表失败"
    """
    try:
        embedding_models = georag_service.get_available_embedding_models()
        chat_models = georag_service.get_available_chat_models()
        return jsonify({
            "embedding_models": embedding_models,
            "chat_models": chat_models
        }), 200
    except Exception as e:
        return jsonify({"error": "获取模型列表失败"}), 500

@app.route('/databases', methods=['GET'])
def get_databases():
    """
    获取所有数据库列表
    ---
    tags:
      - 数据库管理
    summary: 获取所有向量数据库列表
    description: 获取系统中所有已创建的向量数据库信息
    responses:
      200:
        description: 成功获取数据库列表
        schema:
          type: object
          properties:
            databases:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                    description: 数据库名称
                  model_name:
                    type: string
                    description: 使用的嵌入模型
                  created_at:
                    type: string
                    description: 创建时间
              example:
                - name: "geo_knowledge"
                  model_name: "text-embedding-v3"
                  created_at: "2024-01-01T10:00:00Z"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "获取数据库列表失败"
    """
    try:
        result = georag_service.get_databases(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/databases/add', methods=['POST'])
def add_database():
    """
    向数据库添加文件
    ---
    tags:
      - 数据库管理
    summary: 向已有数据库添加文件
    description: 将文件上传并添加到指定的向量数据库中
    consumes:
      - multipart/form-data
    parameters:
      - name: db_name
        in: formData
        type: string
        required: true
        description: 数据库名称
        example: "geo_knowledge"
      - name: files
        in: formData
        type: file
        required: true
        description: 要上传的文件（支持CSV、JSON、TXT格式）
    responses:
      200:
        description: 文件添加成功
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Files added to database 'geo_knowledge' successfully"
            db_name:
              type: string
              example: "geo_knowledge"
            files_processed:
              type: integer
              example: 3
      400:
        description: 参数错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "db_name is required"
      404:
        description: 数据库不存在
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Database 'geo_knowledge' not found"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "文件处理失败"
    """
    try:
        result = georag_service.add_files_to_database(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/databases/<db_name>', methods=['DELETE'])
def delete_db(db_name):
    """
    删除指定数据库
    ---
    tags:
      - 数据库管理
    summary: 删除指定的向量数据库
    description: 删除指定名称的向量数据库及其所有数据
    parameters:
      - name: db_name
        in: path
        type: string
        required: true
        description: 要删除的数据库名称
        example: "geo_knowledge"
    responses:
      200:
        description: 数据库删除成功
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Database 'geo_knowledge' deleted successfully"
      404:
        description: 数据库不存在
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Database 'geo_knowledge' not found"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "删除数据库失败"
    """
    try:
        result = georag_service.delete_db(db_name)
        return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/documents', methods=['GET'])
def list_documents():
    """
    获取所有文档列表
    ---
    tags:
      - 文档管理
    summary: 获取documents目录下的所有文件列表
    description: 获取系统中所有已上传的文档文件信息
    responses:
      200:
        description: 成功获取文档列表
        schema:
          type: object
          properties:
            documents:
              type: array
              items:
                type: string
                description: 文档文件名
              example:
                - "sample_data.csv"
                - "knowledge_base.json"
                - "readme.txt"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "无法列出文档"
    """
    try:
        documents = georag_service.get_documents()
        return jsonify(documents), 200
    except Exception as e:
        return jsonify({"error": "无法列出文档"}), 500

@app.route('/documents/download/<filename>', methods=['GET'])
def download_document(filename):
    """
    下载指定文档
    ---
    tags:
      - 文档管理
    summary: 下载指定的文档文件
    description: 根据文件名下载指定的文档文件
    parameters:
      - name: filename
        in: path
        type: string
        required: true
        description: 要下载的文件名
        example: "sample_data.csv"
    responses:
      200:
        description: 文件下载成功
        schema:
          type: file
      404:
        description: 文档未找到
        schema:
          type: object
          properties:
            error:
              type: string
              example: "文档未找到"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "无法下载文档"
    """
    try:
        file_path = georag_service.download_document(filename)
        if not file_path:
            return jsonify({"error": "文档未找到"}), 404
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": "无法下载文档"}), 500

@app.route('/documents/delete/<filename>', methods=['DELETE'])
def delete_document(filename):
    """
    删除指定文档
    ---
    tags:
      - 文档管理
    summary: 删除指定的文档文件
    description: 根据文件名删除指定的文档文件
    parameters:
      - name: filename
        in: path
        type: string
        required: true
        description: 要删除的文件名
        example: "sample_data.csv"
    responses:
      200:
        description: 文档删除成功
        schema:
          type: object
          properties:
            message:
              type: string
              example: "文档已删除"
      404:
        description: 文档未找到
        schema:
          type: object
          properties:
            error:
              type: string
              example: "文档未找到"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "无法删除文档"
    """
    try:
        result = georag_service.delete_document(filename)
        return result
    except Exception as e:
        return jsonify({"error": "无法删除文档"}), 500

@app.route('/create_db', methods=['POST'])
def create_database():
    """
    创建新的向量数据库
    ---
    tags:
      - 数据库管理
    summary: 创建新的向量数据库
    description: 使用指定的嵌入模型创建新的向量数据库，可选择性地添加初始文件
    consumes:
      - multipart/form-data
    parameters:
      - name: model_name
        in: formData
        type: string
        required: true
        description: 嵌入模型名称
        example: "text-embedding-v3"
      - name: db_name
        in: formData
        type: string
        required: true
        description: 数据库名称
        example: "geo_knowledge"
      - name: files
        in: formData
        type: file
        required: false
        description: 要上传的初始文件（支持CSV、JSON、TXT格式）
    responses:
      200:
        description: 数据库创建成功
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Database 'geo_knowledge' created successfully"
            db_name:
              type: string
              example: "geo_knowledge"
            model_name:
              type: string
              example: "text-embedding-v3"
            files_processed:
              type: integer
              example: 2
      400:
        description: 参数错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "model_name is required"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "创建数据库失败"
    """
    try:
        result = georag_service.create_database(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    """
    RAG智能问答
    ---
    tags:
      - 智能问答
    summary: 基于RAG的智能问答
    description: 使用指定的向量数据库和聊天模型进行智能问答
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - query
            - db_name
          properties:
            query:
              type: string
              description: 用户查询问题
              example: "什么是数字地形模型？"
            db_name:
              type: string
              description: 向量数据库名称
              example: "geo_knowledge"
            chat_model_name:
              type: string
              description: 聊天模型名称（可选）
              example: "qwen-turbo-latest"
    responses:
      200:
        description: 问答成功
        schema:
          type: object
          properties:
            response:
              type: string
              description: AI回答内容
              example: "数字地形模型（Digital Terrain Model, DTM）是通过数字化的方式表示地形地貌的三维模型..."
      400:
        description: 参数错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "query is required"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "问答处理失败"
    """
    try:
        result = georag_service.ask_question(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat_with_agent():
    """
    聊天对话（支持记忆功能）
    ---
    tags:
      - 会话管理
    summary: 与AI助手进行对话
    description: 支持记忆功能的AI聊天对话，可以记住历史对话内容
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - prompt
            - query
          properties:
            prompt:
              type: string
              description: 系统提示词
              example: "你是一个地理信息专家助手"
            query:
              type: string
              description: 用户查询问题
              example: "什么是数字地形模型？"
            chat_model_name:
              type: string
              description: 聊天模型名称（可选）
              example: "qwen-turbo-latest"
            session_id:
              type: string
              description: 会话ID（可选，不提供则创建新会话）
              example: "550e8400-e29b-41d4-a716-446655440000"
            use_memory:
              type: boolean
              description: 是否使用记忆功能（可选，默认true）
              example: true
    responses:
      200:
        description: 对话成功
        schema:
          type: object
          properties:
            response:
              type: string
              description: AI回答内容
              example: "数字地形模型（Digital Terrain Model, DTM）是通过数字化的方式表示地形地貌的三维模型..."
            session_id:
              type: string
              description: 会话ID
              example: "550e8400-e29b-41d4-a716-446655440000"
            message_count:
              type: integer
              description: 当前会话中的消息数量
              example: 2
      400:
        description: 参数错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "prompt is required"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "聊天处理失败"
    """
    try:
        result = georag_service.chat_with_agent(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/chat/sessions', methods=['GET'])
def get_chat_sessions():
    """
    获取所有会话信息
    ---
    tags:
      - 会话管理
    summary: 获取所有聊天会话列表
    description: 获取系统中所有活跃的聊天会话信息
    responses:
      200:
        description: 成功获取会话列表
        schema:
          type: object
          properties:
            sessions:
              type: object
              description: 会话信息字典
              additionalProperties:
                type: object
                properties:
                  created_at:
                    type: string
                    format: date-time
                    description: 会话创建时间
                  last_active:
                    type: string
                    format: date-time
                    description: 最后活跃时间
                  message_count:
                    type: integer
                    description: 消息数量
              example:
                "550e8400-e29b-41d4-a716-446655440000":
                  created_at: "2024-01-01T10:00:00"
                  last_active: "2024-01-01T10:30:00"
                  message_count: 5
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "无法获取会话信息"
    """
    try:
        sessions = georag_service.get_chat_sessions()
        return jsonify({"sessions": sessions}), 200
    except Exception as e:
        return jsonify({"error": "无法获取会话信息"}), 500

@app.route('/chat/sessions/<session_id>', methods=['DELETE'])
def delete_chat_session(session_id):
    """
    删除指定会话
    ---
    tags:
      - 会话管理
    summary: 删除指定的聊天会话
    description: 根据会话ID删除指定的聊天会话及其历史记录
    parameters:
      - name: session_id
        in: path
        type: string
        required: true
        description: 要删除的会话ID
        example: "550e8400-e29b-41d4-a716-446655440000"
    responses:
      200:
        description: 会话删除成功
        schema:
          type: object
          properties:
            message:
              type: string
              example: "会话已删除"
      404:
        description: 会话未找到
        schema:
          type: object
          properties:
            error:
              type: string
              example: "会话未找到"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "无法删除会话"
    """
    try:
        success = georag_service.delete_chat_session(session_id)
        if not success:
            return jsonify({"error": "会话未找到"}), 404
        return jsonify({"message": "会话已删除"}), 200
    except Exception as e:
        return jsonify({"error": "无法删除会话"}), 500

@app.route('/chat/sessions/clear', methods=['POST'])
def clear_all_sessions():
    """
    清空所有会话
    ---
    tags:
      - 会话管理
    summary: 清空所有聊天会话
    description: 删除系统中所有的聊天会话及其历史记录
    responses:
      200:
        description: 会话清空成功
        schema:
          type: object
          properties:
            message:
              type: string
              example: "所有会话已清空"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "无法清空会话"
    """
    try:
        georag_service.clear_all_sessions()
        return jsonify({"message": "所有会话已清空"}), 200
    except Exception as e:
        return jsonify({"error": "无法清空会话"}), 500

@app.route('/chat/history', methods=['POST'])
def get_chat_history():
    """
    获取会话历史记录
    ---
    tags:
      - 会话管理
    summary: 获取指定会话的历史记录
    description: 根据会话ID获取该会话的完整历史对话记录
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - session_id
          properties:
            session_id:
              type: string
              description: 会话ID
              example: "550e8400-e29b-41d4-a716-446655440000"
    responses:
      200:
        description: 成功获取历史记录
        schema:
          type: object
          properties:
            session_id:
              type: string
              description: 会话ID
              example: "550e8400-e29b-41d4-a716-446655440000"
            history:
              type: array
              items:
                type: object
                properties:
                  role:
                    type: string
                    enum: ["system", "user", "assistant"]
                    description: 消息角色
                  content:
                    type: string
                    description: 消息内容
              example:
                - role: "system"
                  content: "你是一个地理信息专家助手"
                - role: "user"
                  content: "什么是数字地形模型？"
                - role: "assistant"
                  content: "数字地形模型（Digital Terrain Model, DTM）是..."
            message_count:
              type: integer
              description: 消息数量
              example: 3
      400:
        description: 参数错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "session_id is required"
      404:
        description: 会话未找到
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Session not found"
      500:
        description: 服务器内部错误
        schema:
          type: object
          properties:
            error:
              type: string
              example: "获取历史记录失败"
    """
    try:
        result = georag_service.get_chat_history(request)
        return result
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # 使用waitress运行Flask应用，挂载到0.0.0.0:7513
    serve(app, host='0.0.0.0', port=7513)
    #app.run()