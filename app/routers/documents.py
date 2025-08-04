"""
文档管理路由
提供文档上传、下载、删除等API接口
"""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from ..responses import success_response, error_response
from ..dependencies import get_document_service
from ..services.document_service import DocumentService

router = APIRouter()

@router.get("/documents")
async def list_documents(document_service: DocumentService = Depends(get_document_service)):
    """
    获取所有文档列表
    """
    try:
        documents = document_service.get_documents()
        return success_response(data=documents)
    except Exception as e:
        return error_response(message="无法列出文档", code=5005)

@router.get("/documents/download/{filename}")
async def download_document(
    filename: str,
    document_service: DocumentService = Depends(get_document_service)
):
    """
    下载指定文档
    """
    try:
        file_path = document_service.download_document(filename)
        # 文件下载接口保持原样返回FileResponse
        return FileResponse(file_path, filename=filename)
    except ValueError as e:
        return error_response(message=str(e), code=4004)
    except Exception as e:
        return error_response(message="无法下载文档", code=5006)

@router.delete("/documents/delete/{filename}")
async def delete_document(
    filename: str,
    document_service: DocumentService = Depends(get_document_service)
):
    """
    删除指定文档
    """
    try:
        result = document_service.delete_document(filename)
        return success_response(data=result, message="文档删除成功")
    except ValueError as e:
        return error_response(message=str(e), code=4004)
    except Exception as e:
        return error_response(message="无法删除文档", code=5007)