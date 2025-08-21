"""
响应处理模块
提供标准化的API响应工具函数
"""

from typing import Any, Dict
from .models import StandardResponse
from .config import config

def success_response(data: Any = None, message: str = "成功", code: int = None) -> Dict:
    """
    创建成功响应
    
    Args:
        data: 返回数据
        message: 响应消息
        code: 状态码，默认使用配置中的成功码
    
    Returns:
        标准响应字典
    """
    if code is None:
        code = config.SUCCESS_CODE
    return StandardResponse(success=True, code=code, message=message, data=data).dict()

def error_response(message: str = "失败", code: int = None, data: Any = None) -> Dict:
    """
    创建错误响应
    
    Args:
        message: 错误消息
        code: 错误码，默认使用配置中的错误码
        data: 附加数据
    
    Returns:
        标准响应字典
    """
    if code is None:
        code = config.ERROR_CODE
    return StandardResponse(success=False, code=code, message=message, data=data).dict()