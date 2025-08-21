"""
异常处理模块
定义全局异常处理器和自定义异常类
"""

import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from .response import error_response

# 配置日志
logger = logging.getLogger(__name__)

async def value_error_exception_handler(request: Request, exc: ValueError):
    """处理ValueError异常"""
    logger.warning(f"ValueError: {str(exc)}")
    return JSONResponse(
        status_code=400,
        content=error_response(message=str(exc), code=4000)
    )

async def file_not_found_exception_handler(request: Request, exc: FileNotFoundError):
    """处理FileNotFoundError异常"""
    logger.warning(f"FileNotFoundError: {str(exc)}")
    return JSONResponse(
        status_code=404,
        content=error_response(message="文件未找到", code=4004)
    )

async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """处理HTTPException异常"""
    logger.warning(f"HTTPException: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(message=exc.detail, code=exc.status_code * 10)
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证异常"""
    logger.warning(f"ValidationError: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content=error_response(message="请求参数验证失败", code=4220, data=exc.errors())
    )

async def general_exception_handler(request: Request, exc: Exception):
    """处理所有其他异常"""
    logger.error(f"未处理的异常: {type(exc).__name__}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=error_response(message="服务器内部错误", code=5000)
    )

def register_exception_handlers(app):
    """注册所有异常处理器到FastAPI应用"""
    app.add_exception_handler(ValueError, value_error_exception_handler)
    app.add_exception_handler(FileNotFoundError, file_not_found_exception_handler)
    app.add_exception_handler(HTTPException, custom_http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)