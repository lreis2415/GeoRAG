"""
文档管理服务
负责文档的上传、下载、删除等管理功能
"""

import os
import hashlib
from typing import Dict, List

from .base_service import BaseService


class DocumentService(BaseService):
    """文档管理服务类"""

    def __init__(self):
        super().__init__()
        # 设置上传目录
        self.upload_folder = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ),
            "data",
            "documents",
        )
        os.makedirs(self.upload_folder, exist_ok=True)
        self.log_info(f"文档上传目录: {self.upload_folder}")

    def _user_folder(self, user_id: str) -> str:
        user_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
        folder = os.path.join(self.upload_folder, user_hash)
        os.makedirs(folder, exist_ok=True)
        return folder

    def _user_file_path(self, filename: str, user_id: str) -> str:
        if not filename or filename != os.path.basename(filename):
            raise ValueError("Invalid document filename")
        return os.path.join(self._user_folder(user_id), filename)

    def get_documents(self, user_id: str) -> Dict[str, List[str]]:
        """
        获取documents目录下的所有文件列表

        Returns:
            文件列表字典
        """
        try:
            upload_folder = self._user_folder(user_id)
            if not os.path.exists(upload_folder):
                self.log_warning("上传目录不存在")
                return {"documents": []}

            documents = [
                f
                for f in os.listdir(upload_folder)
                if os.path.isfile(os.path.join(upload_folder, f))
            ]

            self.log_info(f"找到 {len(documents)} 个文档")
            return {"documents": documents}
        except Exception as e:
            self.log_error(f"获取文档列表失败: {e}")
            return {"documents": []}

    def download_document(self, filename: str, user_id: str) -> str:
        """
        获取文档下载路径

        Args:
            filename: 文件名

        Returns:
            文件完整路径

        Raises:
            ValueError: 文件不存在
        """
        file_path = self._user_file_path(filename, user_id)

        if not os.path.exists(file_path):
            self.log_warning(f"文件不存在: {filename}")
            raise ValueError(f"Document '{filename}' not found")

        self.log_info(f"准备下载文件: {filename}")
        return file_path

    def delete_document(self, filename: str, user_id: str) -> Dict[str, str]:
        """
        删除指定文档

        Args:
            filename: 文件名

        Returns:
            删除结果信息

        Raises:
            ValueError: 文件不存在
        """
        file_path = self._user_file_path(filename, user_id)

        if not os.path.exists(file_path):
            self.log_warning(f"要删除的文件不存在: {filename}")
            raise ValueError(f"Document '{filename}' not found")

        try:
            os.remove(file_path)
            self.log_info(f"成功删除文件: {filename}")
            return {"message": f"Document '{filename}' deleted successfully"}
        except Exception as e:
            self.log_error(f"删除文件失败: {e}")
            raise

    def get_upload_folder(self) -> str:
        """
        获取上传目录路径

        Returns:
            上传目录路径
        """
        return self.upload_folder

    def file_exists(self, filename: str, user_id: str) -> bool:
        """
        检查文件是否存在

        Args:
            filename: 文件名

        Returns:
            文件是否存在
        """
        file_path = self._user_file_path(filename, user_id)
        return os.path.exists(file_path)
