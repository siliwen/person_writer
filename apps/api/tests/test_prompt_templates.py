"""TDD tests for prompt-template backend-config feature (all 6 purposes).

Covers:
- ensure_default_prompt_templates seeds every purpose with exactly one active template
- update_prompt_template changes only system_prompt
- reset_admin_prompt_template restores the code-built-in default
- composer fallbacks to built-in default when no system_prompt passed
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.core.constants import ALL_PURPOSES, PURPOSE_OPTIMIZE_PROMPT, PURPOSE_STYLE_WRITING
from app.core.prompt_composer import compose_prompt, compose_free_prompt
from app.core.prompt_template_service import (
    DEFAULT_OPTIMIZE_PROMPT,
    DEFAULT_STYLE_WRITING_PROMPT,
    ensure_default_prompt_templates,
    get_active_prompt_template,
    reset_admin_prompt_template,
    update_prompt_template,
)
from app.database import Base, _seed_membership_data, get_db
from app.main import app


@pytest.fixture
def env():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SLS = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    _seed_membership_data(SLS)

    def override():
        db = SLS()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c, SLS
    app.dependency_overrides.clear()
    engine.dispose()


def test_seed_creates_one_active_template_per_purpose(env):
    _, SLS = env
    db = SLS()
    ensure_default_prompt_templates(db)
    for purpose in ALL_PURPOSES:
        active = get_active_prompt_template(db, purpose)
        assert active is not None, f"{purpose} should have an active template"
        others = db.scalars(
            select(models.PromptTemplate).where(
                models.PromptTemplate.purpose == purpose,
                models.PromptTemplate.is_active.is_(False),
            )
        ).all()
        assert others == [], f"{purpose} must not have inactive duplicates"
    db.close()


def test_update_changes_only_system_prompt(env):
    _, SLS = env
    db = SLS()
    ensure_default_prompt_templates(db)
    tpl = get_active_prompt_template(db, PURPOSE_OPTIMIZE_PROMPT)
    original_name = tpl.name
    update_prompt_template(db, tpl.id, system_prompt="改写后的优化提示词。")
    refreshed = get_active_prompt_template(db, PURPOSE_OPTIMIZE_PROMPT)
    assert refreshed.system_prompt == "改写后的优化提示词。"
    assert refreshed.name == original_name  # name 锁定
    db.close()


def test_reset_restores_code_default(env):
    _, SLS = env
    db = SLS()
    ensure_default_prompt_templates(db)
    tpl = get_active_prompt_template(db, PURPOSE_OPTIMIZE_PROMPT)
    update_prompt_template(db, tpl.id, system_prompt="被改坏的提示词。")
    reset_admin_prompt_template(db, tpl.id)
    refreshed = get_active_prompt_template(db, PURPOSE_OPTIMIZE_PROMPT)
    assert refreshed.system_prompt == DEFAULT_OPTIMIZE_PROMPT
    db.close()


def test_compose_falls_back_to_builtin_default_when_none():
    task = _dummy_task()
    prompt = compose_prompt(task=task, style_profile={})
    assert prompt.system_prompt == DEFAULT_STYLE_WRITING_PROMPT
    free = compose_free_prompt(task=task)
    assert free.system_prompt  # DEFAULT_FREE_WRITE_PROMPT 非空


def test_compose_uses_injected_system_prompt():
    task = _dummy_task()
    injected = "自定义风格写作提示词XYZ。"
    prompt = compose_prompt(task=task, style_profile={}, system_prompt=injected)
    assert prompt.system_prompt == injected
    free = compose_free_prompt(task=task, system_prompt=injected)
    assert free.system_prompt == injected


def _dummy_task():
    from app.core.prompt_composer import WritingTaskInput

    return WritingTaskInput(
        genre="散文",
        task_type="风格写作",
        title="测试",
        brief="测试",
        target_length="约 800 字",
        target_reader="通用读者",
        must_include="",
        must_avoid="",
        eval_focus="",
    )
