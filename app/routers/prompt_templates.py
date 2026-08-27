"""Authenticated CRUD endpoints for reusable prompt templates."""

import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.services.prompt_template_service import (
    PromptTemplateConflictError,
    PromptTemplateLimitError,
    PromptTemplateNotFoundError,
    PromptTemplateService,
)
from app.utils.dependencies import get_db
from app.utils.errors import safe_error_message
from app.utils.models import (
    PromptTemplateListResponse,
    PromptTemplateResponse,
    PromptTemplateCreateRequest,
    PromptTemplateUpdateRequest,
    StandardResponse,
)
from app.utils.response import error_response, success_response

logger = logging.getLogger(__name__)
router = APIRouter()
prompt_template_service = PromptTemplateService()


@router.get(
    "/prompt-templates",
    response_model=StandardResponse[PromptTemplateListResponse],
    tags=["提示词库"],
)
async def list_prompt_templates(
    keyword: str = Query("", max_length=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        templates = prompt_template_service.list(db, current_user.user_id, keyword)
        return success_response(data={"templates": templates})
    except Exception as exc:
        logger.exception("获取提示词库失败: user_id=%s", current_user.user_id)
        return error_response(message=safe_error_message(exc), code=5002)


@router.post(
    "/prompt-templates",
    response_model=StandardResponse[PromptTemplateResponse],
    tags=["提示词库"],
)
async def create_prompt_template(
    request: PromptTemplateCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        template = prompt_template_service.create(
            db, current_user.user_id, request.name, request.content
        )
        return success_response(data=template, message="提示词已创建")
    except PromptTemplateLimitError as exc:
        return error_response(message=str(exc), code=4003)
    except ValueError as exc:
        return error_response(message=str(exc), code=4002)
    except Exception as exc:
        logger.exception("创建提示词失败: user_id=%s", current_user.user_id)
        return error_response(message=safe_error_message(exc), code=5002)


@router.put(
    "/prompt-templates/{template_id}",
    response_model=StandardResponse[dict],
    tags=["提示词库"],
)
async def update_prompt_template(
    template_id: str,
    request: PromptTemplateUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        template = prompt_template_service.update(
            db,
            current_user.user_id,
            template_id,
            request.name,
            request.content,
            request.version,
        )
        return success_response(data=template, message="提示词已更新")
    except PromptTemplateConflictError as exc:
        return error_response(
            message=str(exc),
            code=4009,
            data={"current": prompt_template_service.serialize(exc.current)},
        )
    except PromptTemplateNotFoundError as exc:
        return error_response(message=str(exc), code=4004)
    except ValueError as exc:
        return error_response(message=str(exc), code=4002)
    except Exception as exc:
        logger.exception("更新提示词失败: user_id=%s", current_user.user_id)
        return error_response(message=safe_error_message(exc), code=5002)


@router.delete(
    "/prompt-templates/{template_id}",
    response_model=StandardResponse[None],
    tags=["提示词库"],
)
async def delete_prompt_template(
    template_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        prompt_template_service.delete(db, current_user.user_id, template_id)
        return success_response(message="提示词已删除")
    except PromptTemplateNotFoundError as exc:
        return error_response(message=str(exc), code=4004)
    except Exception as exc:
        logger.exception("删除提示词失败: user_id=%s", current_user.user_id)
        return error_response(message=safe_error_message(exc), code=5002)
