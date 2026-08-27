"""Data access helpers for persisted prompt templates."""

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.prompt_template_models import PromptTemplate


class PromptTemplateDAO:
    """All operations scope records by the JWT-derived user id."""

    @staticmethod
    def list(
        db: Session, user_id: str, keyword: Optional[str] = None
    ) -> List[PromptTemplate]:
        query = db.query(PromptTemplate).filter(PromptTemplate.user_id == user_id)
        normalized_keyword = (keyword or "").strip().lower()
        if normalized_keyword:
            query = query.filter(
                func.lower(PromptTemplate.name).like(f"%{normalized_keyword}%")
            )
        return query.order_by(PromptTemplate.updated_at.desc()).all()

    @staticmethod
    def count(db: Session, user_id: str) -> int:
        return (
            db.query(PromptTemplate)
            .filter(PromptTemplate.user_id == user_id)
            .count()
        )

    @staticmethod
    def get(db: Session, template_id: str, user_id: str) -> Optional[PromptTemplate]:
        return (
            db.query(PromptTemplate)
            .filter(
                PromptTemplate.id == template_id,
                PromptTemplate.user_id == user_id,
            )
            .first()
        )

    @staticmethod
    def create(
        db: Session, user_id: str, name: str, content: str
    ) -> PromptTemplate:
        template = PromptTemplate(user_id=user_id, name=name, content=content)
        try:
            db.add(template)
            db.commit()
            db.refresh(template)
            return template
        except SQLAlchemyError:
            db.rollback()
            raise

    @staticmethod
    def update(
        db: Session,
        template_id: str,
        user_id: str,
        name: str,
        content: str,
        version: int,
    ) -> Tuple[str, Optional[PromptTemplate]]:
        """Return ``updated``, ``missing`` or ``conflict`` and the record."""
        try:
            updated = (
                db.query(PromptTemplate)
                .filter(
                    PromptTemplate.id == template_id,
                    PromptTemplate.user_id == user_id,
                    PromptTemplate.version == version,
                )
                .update(
                    {
                        PromptTemplate.name: name,
                        PromptTemplate.content: content,
                        PromptTemplate.version: PromptTemplate.version + 1,
                        PromptTemplate.updated_at: datetime.utcnow(),
                    },
                    synchronize_session=False,
                )
            )
            if not updated:
                current = PromptTemplateDAO.get(db, template_id, user_id)
                return ("missing" if current is None else "conflict", current)

            db.commit()
            return "updated", PromptTemplateDAO.get(db, template_id, user_id)
        except SQLAlchemyError:
            db.rollback()
            raise

    @staticmethod
    def delete(db: Session, template_id: str, user_id: str) -> bool:
        try:
            deleted = (
                db.query(PromptTemplate)
                .filter(
                    PromptTemplate.id == template_id,
                    PromptTemplate.user_id == user_id,
                )
                .delete(synchronize_session=False)
            )
            db.commit()
            return deleted > 0
        except SQLAlchemyError:
            db.rollback()
            raise
