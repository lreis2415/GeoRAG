from flask import Flask, request
from waitress import serve
from georag_service import GeoRAGService

app = Flask(__name__)
app.debug = True

# 初始化服务
georag_service = GeoRAGService()

@app.route('/')
def start():  # put application's code here
    return "The service is running!"

@app.route('/databases', methods=['GET'])
def get_databases():
    return georag_service.get_databases(request)

@app.route('/create_db', methods=['POST'])
def create_database():
    return georag_service.create_database(request)

@app.route('/ask', methods=['POST'])
def ask_question():
    return georag_service.ask_question(request)

if __name__ == '__main__':
    # 使用waitress运行Flask应用，挂载到0.0.0.0:7512
    serve(app, host='0.0.0.0', port=7512)
    #app.run()