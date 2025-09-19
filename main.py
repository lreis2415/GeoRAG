"""
主应用文件
整合所有模块，创建FastAPI应用实例
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.routers import (
    chat_router,
    databases_router,
    documents_router,
    health_router,
    models_router,
)
from app.services import MCPService
from app.utils.config import config
from app.utils.dependencies import get_global_mcp_service, set_global_mcp_service
from app.utils.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化MCP工具
    mcp_service = MCPService()
    await mcp_service.init_mcp_tools()
    set_global_mcp_service(mcp_service)
    yield
    # 关闭时的清理工作（如果需要）


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
    app.include_router(databases_router, prefix=config.API_PREFIX)
    app.include_router(documents_router, prefix=config.API_PREFIX)
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
