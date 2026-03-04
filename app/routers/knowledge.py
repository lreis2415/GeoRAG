"""
知识库管理路由
统一管理知识库和知识文件的API接口
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.services.database_service import DatabaseService
from app.services.document_service import DocumentService
from app.services.model_service import ModelService
from app.services.rag_service import RAGService
from app.utils.dependencies import (
    get_database_service,
    get_document_service,
    get_model_service,
    get_rag_service,
)
from app.utils.models import AskRequest
from app.utils.response import error_response, success_response

router = APIRouter()


# ==================== 知识库管理 ====================


@router.get("/knowledge/bases", tags=["知识库管理"])
async def get_knowledge_bases(
    database_service: DatabaseService = Depends(get_database_service),
):
    """
    获取所有知识库列表
    """
    try:
        result = database_service.get_databases()
        return success_response(data=result)
    except Exception as e:
        return error_response(message=str(e), code=5002)


@router.post("/knowledge/bases", tags=["知识库管理"])
async def create_knowledge_base(
    model_name: str = Form(..., description="嵌入模型名称"),
    db_name: str = Form(..., description="知识库名称"),
    files: list[UploadFile] = File(None, description="要导入的文件列表"),
    database_service: DatabaseService = Depends(get_database_service),
    model_service: ModelService = Depends(get_model_service),
):
    """
    创建新的知识库
    """
    try:
        # 验证模型是否存在
        if not model_service.validate_embedding_model(model_name):
            return error_response(message=f"嵌入模型 '{model_name}' 不可用", code=4000)

        result = database_service.create_database(model_name, db_name, files)
        return success_response(data=result, message="知识库创建成功")
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5008)


@router.delete("/knowledge/bases/{db_name}", tags=["知识库管理"])
async def delete_knowledge_base(
    db_name: str, database_service: DatabaseService = Depends(get_database_service)
):
    """
    删除指定知识库
    """
    try:
        result = database_service.delete_database(db_name)
        return success_response(data=result, message="知识库删除成功")
    except ValueError as e:
        return error_response(message=str(e), code=4004)
    except Exception as e:
        return error_response(message=str(e), code=5004)


@router.post("/knowledge/bases/{db_name}/files", tags=["知识库管理"])
async def add_files_to_knowledge_base(
    db_name: str,
    files: list[UploadFile] = File(..., description="要添加的文件列表"),
    database_service: DatabaseService = Depends(get_database_service),
):
    """
    向知识库添加文件
    """
    try:
        result = database_service.add_files_to_database(db_name, files)
        return success_response(data=result, message="文件添加成功")
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5003)


# ==================== 知识文件管理 ====================


@router.get("/knowledge/files", tags=["知识文件管理"])
async def list_knowledge_files(
    document_service: DocumentService = Depends(get_document_service),
):
    """
    获取所有知识文件列表
    """
    try:
        documents = document_service.get_documents()
        return success_response(data=documents)
    except Exception:
        return error_response(message="无法列出文档", code=5005)


@router.get("/knowledge/files/{filename}/download", tags=["知识文件管理"])
async def download_knowledge_file(
    filename: str, document_service: DocumentService = Depends(get_document_service)
):
    """
    下载指定知识文件
    """
    try:
        file_path = document_service.download_document(filename)
        return FileResponse(file_path, filename=filename)
    except ValueError as e:
        return error_response(message=str(e), code=4004)
    except Exception:
        return error_response(message="无法下载文档", code=5006)


@router.delete("/knowledge/files/{filename}", tags=["知识文件管理"])
async def delete_knowledge_file(
    filename: str, document_service: DocumentService = Depends(get_document_service)
):
    """
    删除指定知识文件
    """
    try:
        result = document_service.delete_document(filename)
        return success_response(data=result, message="文档删除成功")
    except ValueError as e:
        return error_response(message=str(e), code=4004)
    except Exception:
        return error_response(message="无法删除文档", code=5007)


# ==================== 知识库问答 ====================


@router.post("/knowledge/ask", tags=["知识库问答"])
async def ask_knowledge_base(
    request: AskRequest,
    database_service: DatabaseService = Depends(get_database_service),
    model_service: ModelService = Depends(get_model_service),
    rag_service: RAGService = Depends(get_rag_service),
):
    """
    知识库智能问答
    基于RAG技术，根据用户问题从知识库中检索相关信息并生成答案
    """
    try:
        # 验证聊天模型是否存在
        chat_model_name = (
            request.chat_model_name or model_service.get_default_chat_model()
        )
        if not model_service.validate_chat_model(chat_model_name):
            return error_response(
                message=f"聊天模型 '{chat_model_name}' 不可用", code=4000
            )

        # 获取向量数据库
        vector_db = database_service.get_vector_db(request.db_name)
        if not vector_db:
            return error_response(
                message=f"知识库 '{request.db_name}' 未找到", code=4004
            )

        result = rag_service.ask_question(
            query=request.query,
            db_name=request.db_name,
            vector_db=vector_db,
            chat_model_name=chat_model_name,
        )
        return success_response(data=result)
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=str(e), code=5009)
