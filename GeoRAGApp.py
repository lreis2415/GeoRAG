from flask import Flask, abort, request, send_file
from waitress import serve
from dotenv import load_dotenv
from GeoRAGService.georag_service import GeoRAGService
import os

load_dotenv()
app = Flask(__name__)
app.debug = True

OPEN_API_KEY = os.getenv("OPENAI_API_KEY")
OPEN_API_BASE = os.getenv("OPENAI_API_BASE")
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL")
# 初始化服务
georag_service = GeoRAGService()

@app.route('/')
def start():  # put application's code here
    return f"The service is running!"

@app.route('/databases', methods=['GET'])
def get_databases():
    return georag_service.get_databases(request)

@app.route('/databases/add', methods=['POST'])
def add_database():
    return georag_service.add_files_to_database(request)

@app.route('/databases/<db_name>', methods=['DELETE'])
def delete_db(db_name):
    return georag_service.delete_db(db_name)

@app.route('/documents', methods=['GET'])
def list_documents():
    """列出所有文档"""
    try:
        documents = georag_service.get_documents()
        return {"documents": documents}, 200
    except Exception as e:
        abort(500, description="无法列出文档")

@app.route('/documents/download/<filename>', methods=['GET'])
def download_document(filename):
    """下载指定文档"""
    try:
        file_path = georag_service.download_document(filename)
        if not file_path:
            abort(404, description="文档未找到")
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        abort(500, description="无法下载文档")

@app.route('/documents/delete/<filename>', methods=['DELETE'])
def delete_document(filename):
    """删除指定文档"""
    try:
        success = georag_service.delete_document(filename)
        if not success:
            abort(404, description="文档未找到")
        return {"message": "文档已删除"}, 200
    except Exception as e:
        abort(500, description="无法删除文档")

@app.route('/create_db', methods=['POST'])
def create_database():
    return georag_service.create_database(request)

@app.route('/ask', methods=['POST'])
def ask_question():
    return georag_service.ask_question(request)

@app.route('/chat', methods=['POST'])
def chat_with_agent():
    return georag_service.chat_with_agent(request)

if __name__ == '__main__':
    # 使用waitress运行Flask应用，挂载到0.0.0.0:7512
    serve(app, host='0.0.0.0', port=7512)
    #app.run()