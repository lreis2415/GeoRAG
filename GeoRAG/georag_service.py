# 导入必要的库
import os
from flask import Flask, request, jsonify
from RAGAgent import create_db, ask_agent

# 初始化 Flask 应用
app = Flask(__name__)

# 配置全局变量
VECTOR_DB = None
EMBED_MODEL_NAME = "llama3.1"
CHAT_MODEL_NAME = "qwen-turbo"

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
            embed_model_name=EMBED_MODEL_NAME,
            chat_model_name=CHAT_MODEL_NAME,
            query=query,
            use_api=use_api,
            api_key=api_key,
            api_base=api_base,
            vector_db=VECTOR_DB
        )
        return jsonify({"response": "\n".join(response)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)