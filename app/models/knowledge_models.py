"""
知识库 Pydantic Schema
定义知识库管理相关的 API 请求体和响应体
"""

from typing import List, Optional

from pydantic import BaseModel, Field

# ==================== 基础信息模型 ====================


class KnowledgeBaseInfo(BaseModel):
    """单个知识库信息"""

    id: str = Field(..., description="知识库唯一标识符（数据库集合名称）")
    name: str = Field(..., description="知识库显示名称")
    embedding_model_name: str = Field(..., description="嵌入模型名称")
    document_count: int = Field(0, description="已嵌入的文档块总数")
    created_at: str = Field(..., description="创建时间，ISO 8601 格式")
    description: Optional[str] = Field(None, description="知识库描述")


class KnowledgeBaseFileInfo(BaseModel):
    """知识库中单个关联文件信息"""

    filename: str = Field(..., description="文件名")
    file_path: str = Field(..., description="服务器端文件路径")
    file_size: int = Field(..., description="文件大小（字节）")
    created_at: str = Field(..., description="文件创建时间，ISO 8601 格式")
    modified_at: str = Field(..., description="文件最后修改时间，ISO 8601 格式")


# ==================== 请求模型 ====================


class KnowledgeBaseCreateRequest(BaseModel):
    """
    创建知识库请求（multipart/form-data 中对应字段）

    注意：文件通过 UploadFile 单独传入，不在此 Schema 中声明。
    """

    name: str = Field(
        ...,
        description="知识库显示名称",
        json_schema_extra={"example": "地理信息知识库"},
    )
    embedding_model_name: str = Field(
        ...,
        description="嵌入模型名称",
        json_schema_extra={"example": "text-embedding-v4"},
    )
    description: Optional[str] = Field(None, description="知识库描述（可选）")


class KnowledgeBaseUpdateRequest(BaseModel):
    """
    更新知识库元数据请求（PATCH 语义，所有字段均可选）
    只传入需要修改的字段，未传字段保持原值。
    """

    name: Optional[str] = Field(None, description="新的显示名称")
    description: Optional[str] = Field(None, description="新的描述")


# ==================== 响应模型 ====================


class KnowledgeBaseListResponse(BaseModel):
    """知识库列表响应"""

    databases: List[KnowledgeBaseInfo] = Field(
        default_factory=list, description="知识库列表"
    )
    total_count: int = Field(0, description="知识库总数")


class KnowledgeBaseCreateResponse(BaseModel):
    """创建知识库响应"""

    message: str = Field(..., description="操作结果描述")
    db_name: str = Field(..., description="知识库 ID（集合名称）")
    model_name: str = Field(..., description="嵌入模型名称")
    files_processed: int = Field(0, description="本次已处理并嵌入的文件数量")
    created_at: str = Field(..., description="创建时间，ISO 8601 格式")
    document_count: int = Field(0, description="当前知识库文档块总数")


class KnowledgeBaseFilesResponse(BaseModel):
    """知识库文件列表响应"""

    db_name: str = Field(..., description="知识库 ID")
    db_id: Optional[str] = Field(None, description="知识库 UUID（pgvector 内部字段）")
    files: List[KnowledgeBaseFileInfo] = Field(
        default_factory=list, description="关联的文件列表"
    )
    total_count: int = Field(0, description="关联文件总数")
