"""
知识库管理路由
统一管理知识库和知识文件的API接口
"""

from typing import Dict, List

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.auth.dependencies import CurrentUser, get_current_user
from app.models.knowledge_models import (
    KnowledgeBaseCreateResponse,
    KnowledgeBaseFilesResponse,
    KnowledgeBaseInfo,
    KnowledgeBaseListResponse,
    KnowledgeBaseUpdateRequest,
)
from app.services.database_service import DatabaseService
from app.services.document_service import DocumentService
from app.services.model_service import ModelService
from app.utils.dependencies import (
    get_database_service,
    get_document_service,
    get_model_service,
)
from app.utils.errors import safe_error_message
from app.utils.models import StandardResponse
from app.utils.response import error_response, success_response

router = APIRouter()


# ==================== 知识库管理 ====================


@router.get(
    "/knowledge/bases",
    tags=["知识库管理"],
    response_model=StandardResponse[KnowledgeBaseListResponse],
    summary="获取所有知识库列表",
)
async def get_knowledge_bases(
    current_user: CurrentUser = Depends(get_current_user),
    database_service: DatabaseService = Depends(get_database_service),
) -> StandardResponse[KnowledgeBaseListResponse]:
    """
    返回所有知识库的概要信息，包含：
    - `id` / `name`：标识符与显示名称
    - `embedding_model_name`：嵌入模型
    - `document_count`：已嵌入的文档块总数
    - `created_at`：创建时间（ISO 8601）
    - `description`：可选描述
    """
    try:
        raw = database_service.get_databases(user_id=current_user.user_id)
        data = KnowledgeBaseListResponse(
            databases=raw.get("databases", []),
            total_count=len(raw.get("databases", [])),
        )
        return success_response(data=data.model_dump())
    except Exception as e:
        return error_response(message=safe_error_message(e), code=5002)


@router.get(
    "/knowledge/bases/{db_name}",
    tags=["知识库管理"],
    response_model=StandardResponse[KnowledgeBaseInfo],
    summary="获取单个知识库详情",
)
async def get_knowledge_base_detail(
    db_name: str,
    current_user: CurrentUser = Depends(get_current_user),
    database_service: DatabaseService = Depends(get_database_service),
) -> StandardResponse[KnowledgeBaseInfo]:
    """
    根据知识库 ID（`db_name`）返回详细信息。
    若知识库不存在，返回 `code=4004`。
    """
    try:
        info = database_service.get_knowledge_base_info(
            db_name, user_id=current_user.user_id
        )
        if not info:
            return error_response(
                message=f"Knowledge base '{db_name}' not found", code=4004
            )
        return success_response(data=info)
    except Exception as e:
        return error_response(message=safe_error_message(e), code=5002)


@router.post(
    "/knowledge/bases",
    tags=["知识库管理"],
    response_model=StandardResponse[KnowledgeBaseCreateResponse],
    summary="创建新知识库",
)
async def create_knowledge_base(
    model_name: str = Form(..., description="嵌入模型名称，需在 models.yaml 中已注册"),
    db_name: str = Form(..., description="知识库唯一名称（集合 ID）"),
    files: list[UploadFile] | None = File(
        None, description="可选：创建时同步导入的文件（csv/json/txt）"
    ),
    current_user: CurrentUser = Depends(get_current_user),
    database_service: DatabaseService = Depends(get_database_service),
    model_service: ModelService = Depends(get_model_service),
) -> StandardResponse[KnowledgeBaseCreateResponse]:
    """
    创建一个新的知识库集合。

    - 若 `files` 不为空，文件将在创建时立即嵌入。
    - `model_name` 必须是 `GET /llm/v1/models` 返回的有效嵌入模型。
    - 返回 `code=4000` 表示参数错误（模型不可用 / 字段缺失）。

    **请求格式**：
    - 必须使用 multipart/form-data 编码
    - 示例：
      `curl -X POST -F "model_name=text-embedding-v4" -F "db_name=my_kb"`
      `-F "files=@file.txt" http://localhost:7512/llm/v1/knowledge/bases`
    """
    try:
        if not model_service.validate_embedding_model(model_name):
            return error_response(
                message=f"Embedding model '{model_name}' is not available", code=4000
            )

        result = database_service.create_database(
            model_name, db_name, files, user_id=current_user.user_id
        )
        return success_response(data=result, message="知识库创建成功")
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=safe_error_message(e), code=5008)


@router.delete(
    "/knowledge/bases/{db_name}",
    tags=["知识库管理"],
    response_model=StandardResponse[Dict[str, str]],
    summary="删除知识库",
)
async def delete_knowledge_base(
    db_name: str,
    current_user: CurrentUser = Depends(get_current_user),
    database_service: DatabaseService = Depends(get_database_service),
) -> StandardResponse[Dict[str, str]]:
    """
    永久删除指定知识库及其全部向量数据。

    - pgvector 后端：删除 `langchain_pg_collection` 及关联的 `langchain_pg_embedding` 记录。
    - ChromaDB 后端：删除对应的本地目录。
    - 若知识库不存在，返回 `code=4004`。
    """
    try:
        result = database_service.delete_database(db_name, user_id=current_user.user_id)
        return success_response(data=result, message="知识库删除成功")
    except ValueError as e:
        return error_response(message=str(e), code=4004)
    except Exception as e:
        return error_response(message=safe_error_message(e), code=5004)


@router.patch(
    "/knowledge/bases/{db_name}",
    tags=["知识库管理"],
    response_model=StandardResponse[KnowledgeBaseInfo],
    summary="更新知识库元数据",
)
async def update_knowledge_base(
    db_name: str,
    body: KnowledgeBaseUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    database_service: DatabaseService = Depends(get_database_service),
) -> StandardResponse[KnowledgeBaseInfo]:
    """
    更新知识库的显示名称和/或描述（PATCH 语义，只修改传入的字段）。

    - 若知识库不存在，返回 `code=4004`。
    - `name` 和 `description` 均为可选，不传则保留原值。
    """
    try:
        updated = database_service.update_database_metadata(
            db_name,
            new_name=body.name,
            new_description=body.description,
            user_id=current_user.user_id,
        )
        return success_response(data=updated, message="知识库元数据已更新")
    except ValueError as e:
        return error_response(message=str(e), code=4004)
    except Exception as e:
        return error_response(message=safe_error_message(e), code=5002)


@router.post(
    "/knowledge/bases/{db_name}/files",
    tags=["知识库管理"],
    response_model=StandardResponse[KnowledgeBaseCreateResponse],
    summary="向知识库追加文件",
)
async def add_files_to_knowledge_base(
    db_name: str,
    files: list[UploadFile] = File(..., description="要追加的文件列表（csv/json/txt）"),
    current_user: CurrentUser = Depends(get_current_user),
    database_service: DatabaseService = Depends(get_database_service),
) -> StandardResponse[KnowledgeBaseCreateResponse]:
    """
    向已有知识库追加新文件并完成嵌入。

    - 仅支持 `.csv` / `.json` / `.txt` 格式。
    - 若知识库不存在，返回 `code=4000`。

    **请求格式**：
    - 必须使用 multipart/form-data 编码
    - 示例：
      `curl -X POST -F "files=@file1.txt" -F "files=@file2.csv"`
      `http://localhost:7512/llm/v1/knowledge/bases/my_kb/files`
    """
    try:
        result = database_service.add_files_to_database(
            db_name, files, user_id=current_user.user_id
        )
        return success_response(data=result, message="文件添加成功")
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=safe_error_message(e), code=5003)


@router.get(
    "/knowledge/bases/{db_name}/files",
    tags=["知识库管理"],
    response_model=StandardResponse[KnowledgeBaseFilesResponse],
    summary="获取知识库关联文件列表",
)
async def get_knowledge_base_files(
    db_name: str,
    current_user: CurrentUser = Depends(get_current_user),
    database_service: DatabaseService = Depends(get_database_service),
) -> StandardResponse[KnowledgeBaseFilesResponse]:
    """
    返回指定知识库所关联的全部原始文件信息（文件名、大小、时间等）。

    - 若知识库不存在，返回 `code=4004`。
    """
    try:
        info = database_service.get_knowledge_base_info(
            db_name, user_id=current_user.user_id
        )
        if not info:
            return error_response(
                message=f"Knowledge base '{db_name}' not found", code=4004
            )

        files = database_service.get_knowledge_base_files(
            db_name, user_id=current_user.user_id
        )
        data = KnowledgeBaseFilesResponse(
            db_name=db_name,
            db_id=info.get("id"),
            files=files,
            total_count=len(files),
        )
        return success_response(data=data.model_dump())
    except ValueError as e:
        return error_response(message=str(e), code=4000)
    except Exception as e:
        return error_response(message=safe_error_message(e), code=5003)


# ==================== 知识文件管理 ====================


@router.get(
    "/knowledge/files",
    tags=["知识文件管理"],
    response_model=StandardResponse[Dict[str, List[str]]],
    summary="列出 documents 目录下的所有文件",
)
async def list_knowledge_files(
    current_user: CurrentUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
) -> StandardResponse[Dict[str, List[str]]]:
    """
    返回服务器 `data/documents/` 目录中的全部文件名列表，
    格式为 `{"documents": ["file1.txt", "file2.csv", ...]}`。
    """
    try:
        documents = document_service.get_documents(current_user.user_id)
        return success_response(data=documents)
    except Exception:
        return error_response(message="Failed to list documents", code=5005)


@router.get(
    "/knowledge/files/{filename}/download",
    tags=["知识文件管理"],
    summary="下载指定文件",
    response_class=FileResponse,
    responses={
        200: {"description": "文件二进制流"},
        404: {"description": "文件不存在"},
    },
)
async def download_knowledge_file(
    filename: str,
    current_user: CurrentUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
):
    """
    下载 `data/documents/` 目录中的指定文件。
    若文件不存在，返回标准错误响应（`code=4004`，HTTP 200）。
    """
    try:
        file_path = document_service.download_document(filename, current_user.user_id)
        return FileResponse(file_path, filename=filename)
    except ValueError as e:
        return error_response(message=str(e), code=4004)
    except FileNotFoundError as e:
        return error_response(message=str(e), code=4004)
    except Exception:
        return error_response(message="Failed to download document", code=5006)


@router.delete(
    "/knowledge/files/{filename}",
    tags=["知识文件管理"],
    response_model=StandardResponse[Dict[str, str]],
    summary="删除指定文件",
)
async def delete_knowledge_file(
    filename: str,
    current_user: CurrentUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
) -> StandardResponse[Dict[str, str]]:
    """
    从 `data/documents/` 目录中永久删除指定文件。
    若文件不存在，返回 `code=4004`。
    """
    try:
        result = document_service.delete_document(filename, current_user.user_id)
        return success_response(data=result, message="文档删除成功")
    except ValueError as e:
        return error_response(message=str(e), code=4004)
    except Exception:
        return error_response(message="Failed to delete document", code=5007)
