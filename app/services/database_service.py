"""
数据库管理服务
负责向量数据库的创建、删除和管理
"""

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from werkzeug.utils import secure_filename

from app.dao.DataBase import (
    create_db,
    delete_database,
    get_all_databases,
    get_database_files,
    get_database_info,
    get_scoped_db_name,
    get_persist_directory,
    save_uploaded_file,
)

from .base_service import BaseService

# 加载环境变量
load_dotenv()


class DatabaseService(BaseService):
    """数据库管理服务类"""

    def __init__(self):
        super().__init__()
        self.vector_dbs = {}  # 存储已加载的向量数据库
        self.allowed_extensions = {"csv", "json", "txt"}

    @staticmethod
    def _cache_key(user_id: Optional[str], db_name: str):
        return user_id, db_name

    def allowed_file(self, filename: str) -> bool:
        """
        检查文件是否允许上传

        Args:
            filename: 文件名

        Returns:
            是否允许上传
        """
        return (
            "." in filename
            and filename.rsplit(".", 1)[1].lower() in self.allowed_extensions
        )

    def get_databases(self, user_id: Optional[str] = None) -> Dict[str, List[Dict]]:
        """
        获取所有知识库列表

        Returns:
            知识库列表字典，包含详细信息
        """
        try:
            databases = get_all_databases(user_id=user_id)
            self.log_info(f"获取到 {len(databases)} 个数据库")
            return {"databases": databases}
        except Exception as e:
            self.log_error(f"获取数据库列表失败: {e}")
            return {"databases": []}

    def get_knowledge_base_info(
        self, db_name: str, user_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        获取单个知识库详细信息

        Args:
            db_name: 知识库名称

        Returns:
            知识库信息字典，不存在返回 None
        """
        try:
            info = get_database_info(db_name, user_id=user_id)
            if info:
                self.log_info(f"获取到知识库 {db_name} 的信息")
            else:
                self.log_warning(f"知识库 {db_name} 不存在")
            return info
        except Exception as e:
            self.log_error(f"获取知识库信息失败: {e}")
            return None

    def get_knowledge_base_files(
        self, db_name: str, user_id: Optional[str] = None
    ) -> List[Dict]:
        """
        获取知识库关联的文件列表

        Args:
            db_name: 知识库名称

        Returns:
            文件信息列表
        """
        try:
            files = get_database_files(db_name, user_id=user_id)
            self.log_info(f"获取到知识库 {db_name} 的 {len(files)} 个文件")
            return files
        except Exception as e:
            self.log_error(f"获取知识库文件列表失败: {e}")
            return []

    def create_database(
        self,
        model_name: str,
        db_name: str,
        files=None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建向量数据库

        Args:
            model_name: 嵌入模型名称
            db_name: 数据库名称
            files: 要上传的文件列表 (可选)

        Returns:
            创建结果信息

        Raises:
            ValueError: 参数验证失败
        """
        # 验证必要参数
        if not model_name:
            raise ValueError("model_name is required")
        if not db_name:
            raise ValueError("db_name is required")

        # 处理上传的文件
        file_paths = []
        if files:
            for file in files:
                if file and self.allowed_file(file.filename):
                    # 安全地获取文件名并保存
                    filename = secure_filename(file.filename)
                    # 添加随机字符串避免文件名冲突
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    # FastAPI UploadFile.read 是异步协程，这里统一使用底层 file 对象
                    real_file = getattr(file, "file", file)
                    file_path = save_uploaded_file(
                        real_file, unique_filename, user_id=user_id
                    )
                    file_paths.append(file_path)
                    self.log_info(f"保存文件: {unique_filename}")

        try:
            # 创建数据库
            self.vector_dbs[self._cache_key(user_id, db_name)] = create_db(  # noqa: E501
                model_name, db_name, file_paths, user_id=user_id
            )
            self.log_info(f"成功创建数据库: {db_name}")

            # 获取创建后的知识库信息
            db_info = get_database_info(db_name, user_id=user_id)

            return {
                "id": db_info.get("id") if db_info else None,
                "message": f"Database '{db_name}' created successfully",
                "db_name": db_name,
                "model_name": model_name,
                "files_processed": len(file_paths),
                "created_at": (
                    db_info.get("created_at") if db_info else datetime.now().isoformat()
                ),
                "document_count": db_info.get("document_count", 0) if db_info else 0,
            }
        except Exception as e:
            self.log_error(f"创建数据库失败: {e}")
            raise

    def add_files_to_database(
        self, db_name: str, files, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        向已有知识库添加新文件

        Args:
            db_name: 知识库名称
            files: 要添加的文件列表

        Returns:
            添加结果信息

        Raises:
            ValueError: 参数验证失败或知识库不存在
        """
        if not db_name:
            raise ValueError("db_name is required")

        # 存在性检查：内存缓存命中视为已知存在，否则查持久化存储
        cache_key = self._cache_key(user_id, db_name)
        if cache_key not in self.vector_dbs and get_database_info(
            db_name, user_id=user_id
        ) is None:
            raise ValueError(f"Database '{db_name}' not found")

        # 处理上传的文件
        file_paths = []
        if files:
            for file in files:
                if file and self.allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    real_file = getattr(file, "file", file)
                    file_path = save_uploaded_file(
                        real_file, unique_filename, user_id=user_id
                    )
                    file_paths.append(file_path)
                    self.log_info(f"添加文件: {unique_filename}")

        try:
            # 获取（或加载）向量数据库实例
            vector_db = self.get_vector_db(db_name, user_id=user_id)
            if vector_db is None:
                raise ValueError(f"无法加载数据库 '{db_name}'")

            vector_db.add_files(file_paths)
            self.log_info(f"成功向数据库 {db_name} 添加 {len(file_paths)} 个文件")

            db_info = get_database_info(db_name, user_id=user_id)
            return {
                "id": (db_info or {}).get("id"),
                "message": f"Files added to database '{db_name}' successfully",
                "db_name": db_name,
                "model_name": (db_info or {}).get("embedding_model_name", ""),
                "files_processed": len(file_paths),
                "created_at": (db_info or {}).get(
                    "created_at", datetime.now().isoformat()
                ),
                "document_count": (db_info or {}).get("document_count", 0),
            }
        except ValueError:
            raise
        except Exception as e:
            self.log_error(f"添加文件到数据库失败: {e}")
            raise

    def delete_database(
        self, db_name: str, user_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        删除指定知识库

        Args:
            db_name: 知识库名称

        Returns:
            删除结果信息

        Raises:
            ValueError: 数据库不存在
        """
        # 先做存在性检查，不存在提前报错
        if get_database_info(db_name, user_id=user_id) is None:
            raise ValueError(f"Database '{db_name}' not found")

        try:
            # 从内存中移除
            self.vector_dbs.pop(self._cache_key(user_id, db_name), None)

            # 从磁盘/数据库中删除
            success = delete_database(db_name, user_id=user_id)
            if not success:
                raise ValueError(f"Database '{db_name}' not found")

            self.log_info(f"成功删除数据库: {db_name}")
            return {"message": f"Database '{db_name}' deleted successfully"}
        except ValueError:
            raise
        except Exception as e:
            self.log_error(f"删除数据库失败: {e}")
            raise

    def get_vector_db(
        self,
        db_name: str,
        model_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """
        获取向量数据库实例。

        先确认知识库确实存在（pgvector: 查 langchain_pg_collection；
        ChromaDB: 检查目录），不存在则返回 None，避免创建空集合。

        Args:
            db_name: 数据库名称
            model_name: 可选的嵌入模型名称，用于加载已有数据库

        Returns:
            向量数据库实例，如果数据库不存在则返回 None
        """
        # 先从内存缓存中查找
        cache_key = self._cache_key(user_id, db_name)
        if cache_key in self.vector_dbs:
            return self.vector_dbs[cache_key]

        # 确定使用的后端
        use_pgvector = os.environ.get("USE_PGVECTOR", "true").lower() == "true"

        # ── 存在性检查 ──────────────────────────────────────────────────
        # 必须在实例化 VectorDB 之前做，否则 PGVector 会懒创建集合
        if use_pgvector:
            exists = get_database_info(db_name, user_id=user_id) is not None
        else:
            persist_dir = get_persist_directory(db_name, user_id)
            exists = os.path.exists(persist_dir)

        if not exists:
            self.log_warning(f"知识库 '{db_name}' 不存在，跳过加载")
            return None
        # ────────────────────────────────────────────────────────────────

        # 内存中没有，尝试从持久化存储加载
        try:
            embedding_api_url = os.environ.get("EMBEDDING_API_URL")
            if not embedding_api_url:
                self.log_error("未设置 EMBEDDING_API_URL 环境变量")
                return None

            # 使用提供的模型名或默认模型
            if not model_name:
                # 优先使用知识库自身记录的模型名
                info = get_database_info(db_name, user_id=user_id)
                model_name = (info or {}).get("embedding_model_name") or os.environ.get(
                    "DEFAULT_EMBEDDING_MODEL", "text-embedding-v4"
                )

            if use_pgvector:
                # 从 PostgreSQL 加载
                db_url = os.environ.get("DB_URL")
                if not db_url:
                    self.log_error("未设置 DB_URL 环境变量")
                    return None

                from app.dao.PgvectorVectorDB import PgvectorVectorDB

                vector_db = PgvectorVectorDB(
                    connection_string=db_url,
                    db_name=get_scoped_db_name(user_id, db_name),
                    model_name=model_name,
                    embedding_api_url=embedding_api_url,
                    user_id=user_id,
                )
                self.log_info(
                    f"从 PostgreSQL 加载数据库: {db_name} (模型: {model_name})"
                )
            else:
                from app.dao.FlexibleVectorDB import FlexibleVectorDB

                vector_db = FlexibleVectorDB(
                    embedding_api_url=embedding_api_url,
                    model_name=model_name,
                    persist_directory=persist_dir,
                    user_id=user_id,
                )
                self.log_info(f"从文件系统加载数据库: {db_name} (模型: {model_name})")

            # 缓存到内存
            self.vector_dbs[cache_key] = vector_db
            return vector_db

        except Exception as e:
            self.log_error(f"加载数据库 '{db_name}' 失败: {e}")
            return None

    def update_database_metadata(
        self,
        db_name: str,
        new_name: Optional[str] = None,
        new_description: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        更新知识库的显示名称和/或描述（PATCH 语义）。

        Args:
            db_name: 知识库 ID（集合名称）
            new_name: 新的显示名称（None 表示不修改）
            new_description: 新的描述（None 表示不修改）

        Returns:
            更新后的知识库信息字典

        Raises:
            ValueError: 知识库不存在
        """
        info = get_database_info(db_name, user_id=user_id)
        if info is None:
            raise ValueError(f"Database '{db_name}' not found")

        use_pgvector = os.environ.get("USE_PGVECTOR", "true").lower() == "true"

        if use_pgvector:
            try:
                import json

                from sqlalchemy import create_engine, text

                db_url = os.environ.get("DB_URL")
                engine = create_engine(db_url)
                with engine.connect() as conn:
                    row = conn.execute(
                        text(
                            "SELECT cmetadata FROM langchain_pg_collection"
                            " WHERE name = :name"
                        ),
                        {"name": get_scoped_db_name(user_id, db_name)},
                    ).fetchone()
                    metadata = dict(row[0]) if row and row[0] else {}
                    if user_id is not None and metadata.get("user_id") != user_id:
                        raise ValueError(f"Database '{db_name}' not found")

                if new_name is not None:
                    metadata["name"] = new_name
                if new_description is not None:
                    metadata["description"] = new_description

                with engine.connect() as conn:
                    conn.execute(
                        text(
                            "UPDATE langchain_pg_collection"
                            " SET cmetadata = CAST(:meta AS jsonb)"
                            " WHERE name = :name"
                        ),
                        {
                            "meta": json.dumps(metadata, ensure_ascii=False),
                            "name": get_scoped_db_name(user_id, db_name),
                        },
                    )
                    conn.commit()
            except Exception as e:
                self.log_error(f"更新元数据失败: {e}")
                raise
        else:
            import json

            from app.dao.DataBase import get_persist_directory

            db_path = get_persist_directory(db_name, user_id)
            metadata_file = os.path.join(db_path, "metadata.json")
            metadata = {}
            if os.path.exists(metadata_file):
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            if new_name is not None:
                metadata["name"] = new_name
            if new_description is not None:
                metadata["description"] = new_description
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

        self.log_info(f"知识库 {db_name} 元数据已更新")
        return get_database_info(db_name, user_id=user_id)
