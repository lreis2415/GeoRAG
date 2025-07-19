from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Depends, APIRouter
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from GeoRAGService.georag_service import GeoRAGService
import uvicorn
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
import logging

logging.basicConfig(level=logging.INFO)

load_dotenv()
# 初始化服务
georag_service = GeoRAGService()
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the MCP tools
    await georag_service._init_mcp_tools()
    yield

app = FastAPI(redoc_url=None, lifespan=lifespan)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



class AskRequest(BaseModel):
    prompt: str = Field(..., description="系统提示词",example="你是一个地理信息专家助手")
    query: str = Field(..., description="用户查询问题",example="什么是数字地形模型？")

class ChatRequest(BaseModel):
    prompt: str = Field(..., description="系统提示词",example="你是一个地理信息专家助手")
    query: str = Field(..., description="用户查询问题",example="什么是数字地形模型？")
    chat_model_name: Optional[str] = Field(None, description="聊天模型名称",example="qwen-turbo-latest")
    session_id: Optional[str] = Field(None, description="会话ID",example="550e8400-e29b-41d4-a716-446655440000")
    use_memory: Optional[bool] = Field(None, description="是否使用记忆功能",example=True)


# 自定义OpenAPI文档
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="GeoAgent API",
        version="1.0.0",
        description="GeoAgent API Documentation with Swagger",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return openapi_schema

app.openapi = custom_openapi



@app.get("/")
async def start():
    """
    健康检查接口
    """
    return {
        "status": "running",
        "message": "GeoRAG服务正常运行",
        "version": "1.0.0"
    }

@app.get("/models")
async def get_models():
    """
    获取可用模型列表
    """
    try:
        embedding_models = georag_service.get_available_embedding_models()
        chat_models = georag_service.get_available_chat_models()
        return {
            "embedding_models": embedding_models,
            "chat_models": chat_models
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="获取模型列表失败")

@app.get("/databases")
async def get_databases():
    """
    获取所有数据库列表
    """
    try:
        result = georag_service.get_databases()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/databases/add")
async def add_database():
    """
    向数据库添加文件
    """
    try:
        result = georag_service.add_files_to_database()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/databases/{db_name}")
async def delete_db(db_name: str):
    """
    删除指定数据库
    """
    try:
        result = georag_service.delete_db(db_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents")
async def list_documents():
    """
    获取所有文档列表
    """
    try:
        documents = georag_service.get_documents()
        return documents
    except Exception as e:
        raise HTTPException(status_code=500, detail="无法列出文档")

@app.get("/documents/download/{filename}")
async def download_document(filename: str):
    """
    下载指定文档
    """
    try:
        file_path = georag_service.download_document(filename)
        if not file_path:
            raise HTTPException(status_code=404, detail="文档未找到")
        return FileResponse(file_path, filename=filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail="无法下载文档")

@app.delete("/documents/delete/{filename}")
async def delete_document(filename: str):
    """
    删除指定文档
    """
    try:
        result = georag_service.delete_document(filename)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="无法删除文档")

@app.post("/create_db")
async def create_database():
    """
    创建新的向量数据库
    """
    try:
        result = georag_service.create_database()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ask")
async def ask_question(request: AskRequest):
    """
    RAG智能问答
    ---
    通过RAG智能问答，根据用户问题返回答案
    """
    try:
        result = georag_service.ask_question(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat_with_agent(request: ChatRequest):
    """
    聊天对话（支持记忆功能）
    """
    try:
        result = await georag_service.chat_with_agent(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/sessions")
async def get_chat_sessions():
    """
    获取所有会话信息
    """
    try:
        sessions = georag_service.get_chat_sessions()
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail="无法获取会话信息")

@app.delete("/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """
    删除指定会话
    """
    try:
        success = georag_service.delete_chat_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="会话未找到")
        return {"message": "会话已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="无法删除会话")

@app.post("/chat/sessions/clear")
async def clear_all_sessions():
    """
    清空所有会话
    """
    try:
        georag_service.clear_all_sessions()
        return {"message": "所有会话已清空"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="无法清空会话")

@app.post("/chat/history")
async def get_chat_history():
    """
    获取会话历史记录
    """
    try:
        result = georag_service.get_chat_history()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7512)
