"""
健康检查路由
提供系统状态检查接口
"""

from fastapi import APIRouter

from app.utils.config import config
from app.utils.response import success_response

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    健康检查接口
    检查GeoRAG服务运行状态
    """
    return success_response(
        data={"status": "running", "version": config.VERSION},
        message="GeoRAG服务正常运行",
    )
