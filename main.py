#!/usr/bin/env python3
"""
GeoRAG 主应用文件

功能：
    - 定义 FastAPI 应用工厂函数
    - 支持直接运行或作为模块导入

使用方式：
    # 开发模式启动（推荐）
    python main.py

    # 或使用 uvicorn 直接启动
    uvicorn main:app --host 0.0.0.0 --port 7512 --reload

    # 作为模块导入
    from main import app
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.routers import (
    chat_router,
    health_router,
    knowledge_router,
    models_router,
)
from app.services import MCPService
from app.utils.config import config
from app.utils.dependencies import set_global_mcp_service
from app.utils.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化MCP工具
    mcp_service = MCPService()
    await mcp_service.init_mcp_tools()
    set_global_mcp_service(mcp_service)
    yield
    # 关闭时清理 MCP 资源（关闭持久化连接）
    await mcp_service.cleanup()


def create_app() -> FastAPI:
    """
    创建FastAPI应用实例

    Returns:
        配置完成的FastAPI应用
    """
    # 创建FastAPI应用
    app = FastAPI(
        title=config.APP_NAME,
        version=config.VERSION,
        description=config.DESCRIPTION,
        redoc_url=config.REDOC_URL,
        lifespan=lifespan,
    )

    # 配置CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_methods=config.CORS_METHODS,
        allow_headers=config.CORS_HEADERS,
    )

    # 注册异常处理器
    register_exception_handlers(app)

    # 注册路由
    app.include_router(health_router, prefix=config.API_PREFIX)
    app.include_router(models_router, prefix=config.API_PREFIX)
    app.include_router(knowledge_router, prefix=config.API_PREFIX)
    app.include_router(chat_router, prefix=config.API_PREFIX)

    # 自定义OpenAPI文档
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=config.APP_NAME,
            version=config.VERSION,
            description=config.DESCRIPTION,
            routes=app.routes,
        )
        app.openapi_schema = openapi_schema
        return openapi_schema

    app.openapi = custom_openapi

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    """直接运行此文件时启动开发服务器"""
    print(f"🚀 启动 {config.APP_NAME}")
    print(f"📍 服务地址: http://{config.HOST}:{config.PORT}")
    print(f"📖 API文档: http://{config.HOST}:{config.PORT}/docs")
    print(f"🔍 健康检查: http://{config.HOST}:{config.PORT}{config.API_PREFIX}/")

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,  # 开发模式下自动重载
        log_level="info",
    )
