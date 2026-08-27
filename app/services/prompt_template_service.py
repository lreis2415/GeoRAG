"""Business rules for the user prompt-template library."""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.dao.prompt_template_dao import PromptTemplateDAO
from app.models.prompt_template_models import PromptTemplate


class PromptTemplateLimitError(ValueError):
    """Raised when a user has reached the template quota."""


class PromptTemplateConflictError(ValueError):
    """Raised when a write was based on an outdated template version."""

    def __init__(self, current: PromptTemplate):
        super().__init__("Prompt template was updated elsewhere")
        self.current = current


class PromptTemplateNotFoundError(ValueError):
    """Raised for a missing template, including records owned by another user."""


class PromptTemplateService:
    MAX_TEMPLATES_PER_USER = 100
    MAX_NAME_LENGTH = 100
    MAX_CONTENT_LENGTH = 20_000

    def __init__(self, dao: Optional[PromptTemplateDAO] = None):
        self.dao = dao or PromptTemplateDAO()

    @classmethod
    def _validate_input(cls, name: str, content: str) -> tuple[str, str]:
        normalized_name = name.strip()
        normalized_content = content.strip()
        if not normalized_name or not normalized_content:
            raise ValueError("提示词名称和内容不能为空")
        if len(normalized_name) > cls.MAX_NAME_LENGTH:
            raise ValueError("提示词名称不能超过100个字符")
        if len(normalized_content) > cls.MAX_CONTENT_LENGTH:
            raise ValueError("提示词内容不能超过20000个字符")
        return normalized_name, normalized_content

    @staticmethod
    def serialize(template: PromptTemplate) -> Dict[str, object]:
        def iso(value: Optional[datetime]) -> Optional[str]:
            return value.isoformat() if value is not None else None

        return {
            "id": template.id,
            "name": template.name,
            "content": template.content,
            "version": template.version,
            "created_at": iso(template.created_at),
            "updated_at": iso(template.updated_at),
        }

    def list(
        self, db: Session, user_id: str, keyword: Optional[str] = None
    ) -> List[Dict[str, object]]:
        return [self.serialize(item) for item in self.dao.list(db, user_id, keyword)]

    def create(
        self, db: Session, user_id: str, name: str, content: str
    ) -> Dict[str, object]:
        normalized_name, normalized_content = self._validate_input(name, content)
        if self.dao.count(db, user_id) >= self.MAX_TEMPLATES_PER_USER:
            raise PromptTemplateLimitError("提示词数量已达到100条上限")
        template = self.dao.create(db, user_id, normalized_name, normalized_content)
        return self.serialize(template)

    def update(
        self,
        db: Session,
        user_id: str,
        template_id: str,
        name: str,
        content: str,
        version: int,
    ) -> Dict[str, object]:
        normalized_name, normalized_content = self._validate_input(name, content)
        status, template = self.dao.update(
            db,
            template_id,
            user_id,
            normalized_name,
            normalized_content,
            version,
        )
        if status == "missing" or template is None:
            raise PromptTemplateNotFoundError("Prompt template not found")
        if status == "conflict":
            raise PromptTemplateConflictError(template)
        return self.serialize(template)

    def delete(self, db: Session, user_id: str, template_id: str) -> None:
        if not self.dao.delete(db, template_id, user_id):
            raise PromptTemplateNotFoundError("Prompt template not found")
