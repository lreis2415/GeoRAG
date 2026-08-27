"""Regression tests for the persisted, user-scoped prompt library."""

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.dependencies import CurrentUser
from app.db.base import Base
from app.models.prompt_template_models import PromptTemplate
from app.routers.prompt_templates import (
    create_prompt_template,
    delete_prompt_template,
    list_prompt_templates,
    update_prompt_template,
)
from app.services.prompt_template_service import (
    PromptTemplateLimitError,
    PromptTemplateService,
)
from app.utils.models import (
    PromptTemplateCreateRequest,
    PromptTemplateUpdateRequest,
)


def run(coroutine):
    return asyncio.run(coroutine)


def user(user_id: str) -> CurrentUser:
    return CurrentUser(user_id=user_id, username=user_id, role="USER", claims={})


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def create(db_session, owner="user-a", name="Assistant", content="Be helpful."):
    return run(
        create_prompt_template(
            PromptTemplateCreateRequest(name=name, content=content),
            current_user=user(owner),
            db=db_session,
        )
    )


def test_crud_search_and_recent_update_order(db_session):
    first = create(db_session, name="GIS analyst", content="Analyze maps.")
    second = create(db_session, name="Paper reviewer", content="Review papers.")
    assert first["success"] is True
    assert second["success"] is True

    first_id = first["data"]["id"]
    updated = run(
        update_prompt_template(
            first_id,
            PromptTemplateUpdateRequest(
                name="GIS analyst", content="Analyze raster maps.", version=1
            ),
            current_user=user("user-a"),
            db=db_session,
        )
    )
    assert updated["success"] is True
    assert updated["data"]["version"] == 2

    listed = run(
        list_prompt_templates(keyword="GIS", current_user=user("user-a"), db=db_session)
    )
    assert [item["id"] for item in listed["data"]["templates"]] == [first_id]

    all_templates = run(
        list_prompt_templates(keyword="", current_user=user("user-a"), db=db_session)
    )
    assert all_templates["data"]["templates"][0]["id"] == first_id

    deleted = run(
        delete_prompt_template(first_id, current_user=user("user-a"), db=db_session)
    )
    assert deleted["success"] is True
    assert db_session.get(PromptTemplate, first_id) is None


def test_templates_are_isolated_by_authenticated_user(db_session):
    created = create(db_session, owner="user-a")
    template_id = created["data"]["id"]

    assert run(
        list_prompt_templates(keyword="", current_user=user("user-b"), db=db_session)
    )["data"]["templates"] == []

    forbidden_update = run(
        update_prompt_template(
            template_id,
            PromptTemplateUpdateRequest(name="Changed", content="Changed", version=1),
            current_user=user("user-b"),
            db=db_session,
        )
    )
    assert forbidden_update["success"] is False
    assert forbidden_update["code"] == 4004

    forbidden_delete = run(
        delete_prompt_template(template_id, current_user=user("user-b"), db=db_session)
    )
    assert forbidden_delete["success"] is False
    assert forbidden_delete["code"] == 4004


def test_stale_version_returns_the_current_template(db_session):
    created = create(db_session)
    template_id = created["data"]["id"]

    assert run(
        update_prompt_template(
            template_id,
            PromptTemplateUpdateRequest(name="New", content="New content", version=1),
            current_user=user("user-a"),
            db=db_session,
        )
    )["success"] is True

    conflict = run(
        update_prompt_template(
            template_id,
            PromptTemplateUpdateRequest(name="Stale", content="Stale content", version=1),
            current_user=user("user-a"),
            db=db_session,
        )
    )
    assert conflict["success"] is False
    assert conflict["code"] == 4009
    assert conflict["data"]["current"]["name"] == "New"
    assert conflict["data"]["current"]["version"] == 2


def test_validation_and_quota_are_enforced(db_session):
    blank = create(db_session, name="   ", content="content")
    assert blank["success"] is False
    assert blank["code"] == 4002

    service = PromptTemplateService()
    service.MAX_TEMPLATES_PER_USER = 1
    service.create(db_session, "limited-user", "One", "First prompt")
    with pytest.raises(PromptTemplateLimitError):
        service.create(db_session, "limited-user", "Two", "Second prompt")
