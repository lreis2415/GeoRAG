"""
模型管理路由
提供模型相关的API接口
"""

from fastapi import APIRouter, Depends
from ..responses import success_response, error_response
from ..dependencies import get_model_service
from ..services import ModelService

router = APIRouter()

@router.get("/models")
async def get_models(model_service: ModelService = Depends(get_model_service)):
    """
    获取可用模型列表
    返回嵌入模型和聊天模型列表
    """
    try:
        embedding_models = model_service.get_available_embedding_models()
        chat_models = model_service.get_available_chat_models()
        return success_response(
            data={
                "embedding_models": embedding_models,
                "chat_models": chat_models
            }
        )
    except Exception as e:
        return error_response(message="获取模型列表失败", code=5001)