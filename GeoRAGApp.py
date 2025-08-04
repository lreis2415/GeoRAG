from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Depends, APIRouter
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from dotenv import load_dotenv
from GeoRAGService.georag_service import GeoRAGService
import uvicorn
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union, TypeVar, Generic
import logging

logging.basicConfig(level=logging.INFO)

# 定义通用响应数据类型
T = TypeVar('T')

# 标准API响应模型
class StandardResponse(Generic[T]):
    """标准API响应格式"""
    success: bool  # 操作是否成功
    code: int  # 状态码，如2000表示成功
    message: str  # 描述信息
    data: Optional[T] = None  # 返回数据，可以是任何类型
    
    def __init__(self, success: bool, code: int, message: str, data: Optional[T] = None):
        self.success = success
        self.code = code
        self.message = message
        self.data = data
    
    def dict(self):
        """转换为字典格式"""
        return {
            "success": self.success,
            "code": self.code,
            "message": self.message,
            "data": self.data
        }

# 成功响应工具函数
def success_response(data: Any = None, message: str = "成功", code: int = 2000) -> Dict:
    """创建成功响应"""
    return StandardResponse(success=True, code=code, message=message, data=data).dict()

# 错误响应工具函数
def error_response(message: str = "失败", code: int = 5000, data: Any = None) -> Dict:
    """创建错误响应"""
    return StandardResponse(success=False, code=code, message=message, data=data).dict()

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

# 全局异常处理器
@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError):
    """处理ValueError异常"""
    return JSONResponse(
        status_code=400,
        content=error_response(message=str(exc), code=4000)
    )

@app.exception_handler(FileNotFoundError)
async def file_not_found_exception_handler(request: Request, exc: FileNotFoundError):
    """处理FileNotFoundError异常"""
    return JSONResponse(
        status_code=404,
        content=error_response(message="文件未找到", code=4004)
    )

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """处理HTTPException异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(message=exc.detail, code=exc.status_code * 10)
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证异常"""
    return JSONResponse(
        status_code=422,
        content=error_response(message="请求参数验证失败", code=4220, data=exc.errors())
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理所有其他异常"""
    logging.error(f"未处理的异常: {type(exc).__name__}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=error_response(message="服务器内部错误", code=5000)
    )



class AskRequest(BaseModel):
    prompt: str = Field(..., description="系统提示词",example="你是一个地理信息专家助手")
    query: str = Field(..., description="用户查询问题",example="什么是数字地形模型？")
    db_name: str = Field(..., description="知识库名称",example="geo_knowledge")
    chat_model_name: Optional[str] = Field(None, description="聊天模型名称",example="qwen-turbo-latest")

class ChatRequest(BaseModel):
    prompt: str = Field(..., description="系统提示词",example="你是一个地理信息专家助手")
    query: str = Field(..., description="用户查询问题",example="什么是数字地形模型？")
    chat_model_name: Optional[str] = Field(None, description="聊天模型名称",example="qwen-turbo-latest")
    session_id: Optional[str] = Field(None, description="会话ID",example="550e8400-e29b-41d4-a716-446655440000")
    use_memory: Optional[bool] = Field(None, description="是否使用记忆功能",example=True)

class ChatHistoryRequest(BaseModel):
    session_id: str = Field(..., description="会话ID",example="550e8400-e29b-41d4-a716-446655440000")


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

# 创建带有前缀的路由器
router = APIRouter(prefix="/llm")

@router.get("/")
async def start():
    """
    健康检查接口
    """
    return success_response(
        data={
            "status": "running",
            "version": "1.0.0"
        },
        message="GeoRAG服务正常运行"
    )

@router.get("/models")
async def get_models():
    """
    获取可用模型列表
    """
    try:
        embedding_models = georag_service.get_available_embedding_models()
        chat_models = georag_service.get_available_chat_models()
        return success_response(
            data={
                "embedding_models": embedding_models,
                "chat_models": chat_models
            }
        )
    except Exception as e:
        return error_response(message="获取模型列表失败", code=5001)

@router.get("/databases")
async def get_databases():
    """
    获取所有数据库列表
    """
    try:
        result = georag_service.get_databases()
        return success_response(data=result)
    except Exception as e:
        return error_response(message=str(e), code=5002)

@router.post("/databases/add")
async def add_database(request: Request):
    """
    向数据库添加文件
    """
    try:
        # 获取表单数据
        form = await request.form()
        db_name = form.get("db_name")
        files = form.getlist("files") if "files" in form else None
        
        result = georag_service.add_files_to_database(db_name, files)
        return success_response(data=result, message="文件添加成功")
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5003)

@router.delete("/databases/{db_name}")
async def delete_db(db_name: str):
    """
    删除指定数据库
    """
    try:
        result = georag_service.delete_db(db_name)
        return success_response(data=result, message="数据库删除成功")
    except ValueError as e:
        return error_response(message=str(e), code=4004)
    except Exception as e:
        return error_response(message=str(e), code=5004)

@router.get("/documents")
async def list_documents():
    """
    获取所有文档列表
    """
    try:
        documents = georag_service.get_documents()
        return success_response(data=documents)
    except Exception as e:
        return error_response(message="无法列出文档", code=5005)

@router.get("/documents/download/{filename}")
async def download_document(filename: str):
    """
    下载指定文档
    """
    try:
        file_path = georag_service.download_document(filename)
        if not file_path:
            return error_response(message="文档未找到", code=4004)
        # 文件下载接口保持原样返回FileResponse
        return FileResponse(file_path, filename=filename)
    except Exception as e:
        return error_response(message="无法下载文档", code=5006)

@router.delete("/documents/delete/{filename}")
async def delete_document(filename: str):
    """
    删除指定文档
    """
    try:
        result = georag_service.delete_document(filename)
        return success_response(data=result, message="文档删除成功")
    except ValueError as e:
        return error_response(message=str(e), code=4004)
    except Exception as e:
        return error_response(message="无法删除文档", code=5007)

@router.post("/create_db")
async def create_database(request: Request):
    """
    创建新的向量数据库
    """
    try:
        # 获取表单数据
        form = await request.form()
        model_name = form.get("model_name")
        db_name = form.get("db_name")
        files = form.getlist("files") if "files" in form else None
        
        result = georag_service.create_database(model_name, db_name, files)
        return success_response(data=result, message="数据库创建成功")
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5008)

@router.post("/ask")
async def ask_question(request: AskRequest):
    """
    RAG智能问答
    ---
    通过RAG智能问答，根据用户问题返回答案
    """
    try:
        result = georag_service.ask_question(request.query, request.db_name, request.chat_model_name)
        return success_response(data=result)
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5009)

@router.post("/chat")
async def chat_with_agent(request: ChatRequest):
    """
    聊天对话（支持记忆功能）
    """
    try:
        result = await georag_service.chat_with_agent(
            prompt=request.prompt,
            query=request.query,
            chat_model_name=request.chat_model_name,
            session_id=request.session_id,
            use_memory=request.use_memory
        )
        return success_response(data=result)
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5010)

@router.get("/chat/sessions")
async def get_chat_sessions():
    """
    获取所有会话信息
    """
    try:
        sessions = georag_service.get_chat_sessions()
        return success_response(data={"sessions": sessions})
    except Exception as e:
        return error_response(message="无法获取会话信息", code=5011)

@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """
    删除指定会话
    """
    try:
        success = georag_service.delete_chat_session(session_id)
        if not success:
            return error_response(message="会话未找到", code=4004)
        return success_response(message="会话已删除")
    except Exception as e:
        return error_response(message="无法删除会话", code=5012)

@router.post("/chat/sessions/clear")
async def clear_all_sessions():
    """
    清空所有会话
    """
    try:
        georag_service.clear_all_sessions()
        return success_response(message="所有会话已清空")
    except Exception as e:
        return error_response(message="无法清空会话", code=5013)

@router.post("/chat/history")
async def get_chat_history(request: ChatHistoryRequest):
    """
    获取会话历史记录
    """
    try:
        result = georag_service.get_chat_history(request.session_id)
        return success_response(data=result)
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5014)

# 将路由器包含到主应用
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7512)
