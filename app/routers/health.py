"""
健康检查路由
提供系统状态检查接口
"""

from fastapi import APIRouter
from ..responses import success_response
from ..config import config

router = APIRouter()

@router.get("/")
async def health_check():
    """
    健康检查接口
    检查GeoRAG服务运行状态
    """
    return success_response(
        data={
            "status": "running",
            "version": config.VERSION
        },
        message="GeoRAG服务正常运行"
    )