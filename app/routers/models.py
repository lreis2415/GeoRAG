"""
模型管理路由
提供模型相关的API接口
"""

from fastapi import APIRouter, Depends

from app.services import ModelService
from app.utils.dependencies import get_model_service
from app.utils.response import error_response, success_response

router = APIRouter()


@router.get("/models", tags=["可用LLM"])
async def get_models(
    refresh: bool = False, model_service: ModelService = Depends(get_model_service)
):
    """
    获取可用模型列表
    返回嵌入模型和聊天模型列表，默认从网关动态拉取（带缓存）

    Args:
        refresh: 跳过缓存强制刷新（网关渠道变更后使用）
    """
    try:
        embedding_models = model_service.get_available_embedding_models(refresh=refresh)
        chat_models = model_service.get_available_chat_models(refresh=refresh)
        return success_response(
            data={
                "embedding_models": embedding_models,
                "chat_models": chat_models,
                "source": model_service.get_model_source(refresh=refresh),
            }
        )
    except Exception:
        return error_response(message="Failed to fetch model list", code=5001)
