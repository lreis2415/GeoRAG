"""
路由模块
按功能划分的API路由
"""

from .chat import router as chat_router
from .health import router as health_router
from .knowledge import router as knowledge_router
from .models import router as models_router

__all__ = [
    "health_router",
    "models_router",
    "knowledge_router",
    "chat_router",
]
