"""
数据库管理服务
负责向量数据库的创建、删除和管理
"""

import uuid
from typing import Dict, List, Optional, Any
from werkzeug.utils import secure_filename
from .base_service import BaseService
from app.dao.DataBase import create_db, delete_database, get_all_databases, save_uploaded_file

class DatabaseService(BaseService):
    """数据库管理服务类"""
    
    def __init__(self):
        super().__init__()
        self.vector_dbs = {}  # 存储已加载的向量数据库
        self.allowed_extensions = {'csv', 'json', 'txt'}
    
    def allowed_file(self, filename: str) -> bool:
        """
        检查文件是否允许上传
        
        Args:
            filename: 文件名
            
        Returns:
            是否允许上传
        """
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
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
    
    def create_database(self, model_name: str, db_name: str, files=None) -> Dict[str, Any]:
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
                    file_path = save_uploaded_file(file, unique_filename)
                    file_paths.append(file_path)
                    self.log_info(f"保存文件: {unique_filename}")
        
        try:
            # 创建数据库
            self.vector_dbs[db_name] = create_db(model_name, db_name, file_paths)
            self.log_info(f"成功创建数据库: {db_name}")
            
            return {
                "message": f"Database '{db_name}' created successfully",
                "db_name": db_name,
                "model_name": model_name,
                "files_processed": len(file_paths)
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
                    file_path = save_uploaded_file(file, unique_filename)
                    file_paths.append(file_path)
                    self.log_info(f"添加文件: {unique_filename}")
        
        try:
            # 更新知识库
            self.vector_dbs[db_name].add_files(file_paths)
            self.log_info(f"成功向数据库 {db_name} 添加 {len(file_paths)} 个文件")
            
            return {
                "message": f"Files added to database '{db_name}' successfully",
                "db_name": db_name,
                "files_processed": len(file_paths)
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
    
    def get_vector_db(self, db_name: str):
        """
        获取向量数据库实例
        
        Args:
            db_name: 数据库名称
            
        Returns:
            向量数据库实例
        """
        return self.vector_dbs.get(db_name)