"""
基础服务类
定义服务层的基础功能和通用方法
"""

import logging
from abc import ABC, abstractmethod

class BaseService(ABC):
    """服务基类，提供通用的服务功能"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"{self.__class__.__name__} 初始化完成")
    
    def log_info(self, message: str):
        """记录信息日志"""
        self.logger.info(message)
    
    def log_error(self, message: str):
        """记录错误日志"""
        self.logger.error(message)
    
    def log_warning(self, message: str):
        """记录警告日志"""
        self.logger.warning(message)