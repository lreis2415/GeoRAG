# 导入必要的库
import os
from flask import Flask, logging, request, jsonify
import yaml
from RAGAgent import create_db, ask_agent

# 初始化 Flask 应用
app = Flask(__name__)

# 配置全局变量
VECTOR_DB = None
DEFAULT_EMBED_MODEL = "llama3.1"
DEFAULT_CHAT_MODEL = "qwen-turbo"

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
        model_name: 模型名称
    返回值:
        成功或失败的消息
    """
    global VECTOR_DB
    model_name = request.json.get("model_name")
    if not model_name:
        return jsonify({"error": "model_name is required"}), 400
    try:
        VECTOR_DB = create_db(model_name)
        return jsonify({"message": f"Database created for model {model_name}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ask", methods=["POST"])
def ask_question():
    """
    运行RAG智能体的接口
    请求参数:
        query: 用户查询
        use_api: 是否使用API (可选，默认False)
        api_key: API密钥 (可选)
        api_base: API基础URL (可选)
    返回值:
        智能体的回答
    """
    global VECTOR_DB
    query = request.json.get("query")
    use_api = True  # 默认使用 API
    api_key = os.environ.get("QWEN_API_KEY")  # 使用环境变量中的 API 密钥
    api_base = os.environ.get("QWEN_API_BASE")  # 使用环境变量中的 API 基础 URL
    # 获取用户指定的模型名称
    embed_model_name = request.json.get("embed_model_name", DEFAULT_EMBED_MODEL)
    chat_model_name = request.json.get("chat_model_name", DEFAULT_CHAT_MODEL)
    # 验证模型是否存在
    if embed_model_name not in get_available_embedding_models():
        return jsonify({"error": f"Embedding model '{embed_model_name}' is not available"}), 400
    if chat_model_name not in get_available_chat_models():
        return jsonify({"error": f"Chat model '{chat_model_name}' is not available"}), 400
    if not query:
        return jsonify({"error": "query is required"}), 400
    
    try:
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
            use_api=use_api,
            api_key=api_key,
            api_base=api_base,
            vector_db=VECTOR_DB,
            callback=stream_response  # 添加回调函数参数
        )
        return jsonify({"response": "\n".join(response)}), 200
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