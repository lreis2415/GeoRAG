"""
数据库管理路由
提供向量数据库相关的API接口
"""

from fastapi import APIRouter, Request, Depends
from ..responses import success_response, error_response
from ..models import AskRequest
from ..dependencies import get_database_service, get_model_service, get_rag_service
from ..services.database_service import DatabaseService
from ..services.rag_service import RAGService
from ..services.model_service import ModelService

router = APIRouter()

@router.get("/databases")
async def get_databases(database_service: DatabaseService = Depends(get_database_service)):
    """
    获取所有数据库列表
    """
    try:
        result = database_service.get_databases()
        return success_response(data=result)
    except Exception as e:
        return error_response(message=str(e), code=5002)

@router.post("/databases/add")
async def add_database(
    request: Request,
    database_service: DatabaseService = Depends(get_database_service)
):
    """
    向数据库添加文件
    """
    try:
        # 获取表单数据
        form = await request.form()
        db_name = form.get("db_name")
        files = form.getlist("files") if "files" in form else None
        
        result = database_service.add_files_to_database(db_name, files)
        return success_response(data=result, message="文件添加成功")
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5003)

@router.delete("/databases/{db_name}")
async def delete_db(
    db_name: str,
    database_service: DatabaseService = Depends(get_database_service)
):
    """
    删除指定数据库
    """
    try:
        result = database_service.delete_database(db_name)
        return success_response(data=result, message="数据库删除成功")
    except ValueError as e:
        return error_response(message=str(e), code=4004)
    except Exception as e:
        return error_response(message=str(e), code=5004)

@router.post("/create_db")
async def create_database(
    request: Request,
    database_service: DatabaseService = Depends(get_database_service),
    model_service: ModelService = Depends(get_model_service)
):
    """
    创建新的向量数据库
    """
    try:
        # 获取表单数据
        form = await request.form()
        model_name = form.get("model_name")
        db_name = form.get("db_name")
        files = form.getlist("files") if "files" in form else None
        
        # 验证模型是否存在
        if not model_service.validate_embedding_model(model_name):
            return error_response(message=f"嵌入模型 '{model_name}' 不可用", code=4000)
        
        result = database_service.create_database(model_name, db_name, files)
        return success_response(data=result, message="数据库创建成功")
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5008)

@router.post("/ask")
async def ask_question(
    request: AskRequest,
    database_service: DatabaseService = Depends(get_database_service),
    model_service: ModelService = Depends(get_model_service),
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    RAG智能问答
    通过RAG智能问答，根据用户问题返回答案
    """
    try:
        # 验证聊天模型是否存在
        chat_model_name = request.chat_model_name or model_service.get_default_chat_model()
        if not model_service.validate_chat_model(chat_model_name):
            return error_response(message=f"聊天模型 '{chat_model_name}' 不可用", code=4000)
        
        # 获取向量数据库
        vector_db = database_service.get_vector_db(request.db_name)
        if not vector_db:
            return error_response(message=f"数据库 '{request.db_name}' 未找到", code=4004)
        
        result = rag_service.ask_question(
            query=request.query,
            db_name=request.db_name,
            vector_db=vector_db,
            chat_model_name=chat_model_name
        )
        return success_response(data=result)
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5009)