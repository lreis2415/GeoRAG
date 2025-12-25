"""
数据库管理服务
负责向量数据库的创建、删除和管理
"""

import os
import uuid
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from werkzeug.utils import secure_filename

from app.dao.DataBase import (
    create_db,
    delete_database,
    get_all_databases,
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

    def get_databases(self) -> Dict[str, List[str]]:
        """
        获取所有知识库列表

        Returns:
            知识库列表字典
        """
        try:
            databases = get_all_databases()
            self.log_info(f"获取到 {len(databases)} 个数据库")
            return {"databases": databases}
        except Exception as e:
            self.log_error(f"获取数据库列表失败: {e}")
            return {"databases": []}

    def create_database(
        self, model_name: str, db_name: str, files=None
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
                    file_path = save_uploaded_file(real_file, unique_filename)
                    file_paths.append(file_path)
                    self.log_info(f"保存文件: {unique_filename}")

        try:
            # 创建数据库
            self.vector_dbs[db_name] = create_db(  # noqa: E501
                model_name, db_name, file_paths
            )
            self.log_info(f"成功创建数据库: {db_name}")

            return {
                "message": f"Database '{db_name}' created successfully",
                "db_name": db_name,
                "model_name": model_name,
                "files_processed": len(file_paths),
            }
        except Exception as e:
            self.log_error(f"创建数据库失败: {e}")
            raise

    def add_files_to_database(self, db_name: str, files) -> Dict[str, Any]:
        """
        向已有知识库添加新文件

        Args:
            db_name: 知识库名称
            files: 要添加的文件列表

        Returns:
            添加结果信息

        Raises:
            ValueError: 参数验证失败
        """
        # 验证必要参数
        if not db_name:
            raise ValueError("db_name is required")

        # 验证知识库是否存在
        if db_name not in self.vector_dbs:
            raise ValueError(f"Database '{db_name}' not found")

        # 处理上传的文件
        file_paths = []
        if files:
            for file in files:
                if file and self.allowed_file(file.filename):
                    # 安全地获取文件名并保存
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    # FastAPI UploadFile.read 是异步协程，这里统一使用底层 file 对象
                    real_file = getattr(file, "file", file)
                    file_path = save_uploaded_file(real_file, unique_filename)
                    file_paths.append(file_path)
                    self.log_info(f"添加文件: {unique_filename}")

        try:
            # 更新知识库
            self.vector_dbs[db_name].add_files(file_paths)
            self.log_info(f"成功向数据库 {db_name} 添加 {len(file_paths)} 个文件")

            return {
                "message": f"Files added to database '{db_name}' successfully",
                "db_name": db_name,
                "files_processed": len(file_paths),
            }
        except Exception as e:
            self.log_error(f"添加文件到数据库失败: {e}")
            raise

    def delete_database(self, db_name: str) -> Dict[str, str]:
        """
        删除指定知识库

        Args:
            db_name: 知识库名称

        Returns:
            删除结果信息

        Raises:
            ValueError: 数据库不存在
        """
        try:
            # 从内存中移除
            if db_name in self.vector_dbs:
                del self.vector_dbs[db_name]

            # 从磁盘中删除
            success = delete_database(db_name)
            if not success:
                raise ValueError(f"Database '{db_name}' not found")

            self.log_info(f"成功删除数据库: {db_name}")
            return {"message": f"Database '{db_name}' deleted successfully"}
        except Exception as e:
            self.log_error(f"删除数据库失败: {e}")
            raise

    def get_vector_db(self, db_name: str, model_name: Optional[str] = None):
        """
        获取向量数据库实例

        Args:
            db_name: 数据库名称
            model_name: 可选的嵌入模型名称，用于加载已有数据库

        Returns:
            向量数据库实例，如果数据库不存在则返回 None
        """
        # 先从内存缓存中查找
        if db_name in self.vector_dbs:
            return self.vector_dbs[db_name]

        # 内存中没有，检查文件系统中是否存在
        persist_dir = get_persist_directory(db_name)
        if not os.path.exists(persist_dir):
            self.log_warning(f"数据库目录不存在: {persist_dir}")
            return None

        # 文件系统存在，尝试加载
        try:
            embedding_api_url = os.environ.get("EMBEDDING_API_URL")
            if not embedding_api_url:
                self.log_error("未设置 EMBEDDING_API_URL 环境变量")
                return None

            # 使用提供的模型名或默认模型
            if not model_name:
                # 尝试从环境变量获取默认模型，或使用常见默认值
                model_name = os.environ.get(
                    "DEFAULT_EMBEDDING_MODEL", "text-embedding-v4"
                )

            from app.dao.FlexibleVectorDB import FlexibleVectorDB

            vector_db = FlexibleVectorDB(
                embedding_api_url=embedding_api_url,
                model_name=model_name,
                persist_directory=persist_dir,
            )

            # 缓存到内存
            self.vector_dbs[db_name] = vector_db
            self.log_info(f"从文件系统加载数据库: {db_name} (模型: {model_name})")
            return vector_db

        except Exception as e:
            self.log_error(f"加载数据库 '{db_name}' 失败: {e}")
            return None
