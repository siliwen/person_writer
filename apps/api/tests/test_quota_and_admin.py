"""Tests for the config-driven quota / points / usage system and the admin API.

All config (tiers, length brackets, operation costs, model pricing) is read from
the database, never hardcoded — these tests assert that behavior end-to-end.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base, _seed_membership_data, get_db
from app.main import app


def _make_engine_and_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SLS = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    _seed_membership_data(SLS)
    return engine, SLS


@pytest.fixture
def user_client():
    engine, SLS = _make_engine_and_session()

    def override_get_db():
        db = SLS()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        c.post(
            "/v1/auth/register",
            json={"username": "normaluser", "password": "password123", "confirm_password": "password123"},
        )
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def admin_client():
    engine, SLS = _make_engine_and_session()

    def override_get_db():
        db = SLS()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        c.post(
            "/v1/auth/register",
            json={"username": "adminuser", "password": "password123", "confirm_password": "password123"},
        )
        db = SLS()
        user = db.scalar(select(models.User).where(models.User.username == "adminuser"))
        user.is_admin = True
        db.commit()
        db.close()
        c.post("/v1/auth/login", json={"username": "adminuser", "password": "password123"})
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def _full_style_flow(c: TestClient, target_length: str) -> "TestResponse":
    """Upload a material, analyze style, confirm, then generate an article."""
    upload = c.post(
        "/v1/materials/upload",
        data={"genre": "散文"},
        files=[("files", ("sample.txt", "这是一段用于风格分析的样本文字。".encode("utf-8"), "text/plain"))],
    )
    material_id = upload.json()["materials"][0]["id"]
    job = c.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]}).json()
    style = c.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": "测试风格", "profile": job["draft_profile"]},
    ).json()
    writing = c.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": style["id"],
            "requested_mode": "style_prompt_only",
            "task": {
                "genre": "散文",
                "task_type": "新写",
                "title": "标题",
                "brief": "写点什么",
                "target_length": target_length,
            },
        },
    )
    return writing


def _balance(c: TestClient) -> int:
    return c.get("/v1/account/quota").json()["points_balance"]


def test_register_assigns_free_tier_and_points(user_client: TestClient):
    me = user_client.get("/v1/me").json()
    assert me["tier_code"] == "free"
    assert me["points_balance"] == 10  # 免费版月额度


def test_quota_endpoint_returns_tier_and_brackets(user_client: TestClient):
    quota = user_client.get("/v1/account/quota").json()
    assert quota["tier"]["code"] == "free"
    assert quota["tier"]["monthly_points"] == 10
    assert quota["points_balance"] == 10
    assert quota["operation_points"]["style_analysis"] == 2
    assert quota["operation_points"]["paragraph_rewrite"] == 1
    labels = [b["label"] for b in quota["article_length_brackets"]]
    assert "2000字" in labels and "10000字" in labels


def test_style_analysis_consumes_points(user_client: TestClient):
    before = _balance(user_client)
    upload = user_client.post(
        "/v1/materials/upload",
        data={"genre": "散文"},
        files=[("files", ("s.txt", "样本文字内容。".encode("utf-8"), "text/plain"))],
    )
    mid = upload.json()["materials"][0]["id"]
    user_client.post("/v1/style-analysis-jobs", json={"material_ids": [mid]})
    after = _balance(user_client)
    assert before - after == 2


def test_article_generation_deducts_length_bracket_points(user_client: TestClient):
    before = _balance(user_client)
    resp = _full_style_flow(user_client, "2000字")
    assert resp.status_code == 200
    after = _balance(user_client)
    # 风格分析 2 + 生成 2000字 5 = 7
    assert before - after == 7
    usage = user_client.get("/v1/account/usage").json()
    op_types = [u["op_type"] for u in usage["items"]]
    assert "style_analysis" in op_types and "article_generation" in op_types


def test_free_tier_exceeds_max_length_returns_403(user_client: TestClient):
    resp = _full_style_flow(user_client, "3000字")
    assert resp.status_code == 403
    assert "最大长度" in resp.json()["detail"]


def test_insufficient_points_returns_402(user_client: TestClient):
    _full_style_flow(user_client, "2000字")  # 风格2 + 生成5 = 7，剩 3
    upload = user_client.post(
        "/v1/materials/upload",
        data={"genre": "散文"},
        files=[("files", ("s3.txt", "样本文字内容三。".encode("utf-8"), "text/plain"))],
    )
    mid = upload.json()["materials"][0]["id"]
    job = user_client.post("/v1/style-analysis-jobs", json={"material_ids": [mid]}).json()
    style = user_client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": "风格二", "profile": job["draft_profile"]},
    ).json()
    resp = user_client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": style["id"],
            "requested_mode": "style_prompt_only",
            "task": {"genre": "散文", "task_type": "新写", "title": "t", "brief": "b", "target_length": "2000字"},
        },
    )
    assert resp.status_code == 402


def test_free_tier_cannot_rewrite_or_download(user_client: TestClient):
    writing = _full_style_flow(user_client, "2000字").json()
    doc_id = writing["document"]["id"]
    para_id = writing["document"]["paragraphs"][0]["id"]
    rw = user_client.post(
        f"/v1/documents/{doc_id}/paragraphs/{para_id}/rewrite",
        json={"instruction": "更文艺一点"},
    )
    assert rw.status_code == 403
    dl = user_client.get(f"/v1/documents/{doc_id}/download/docx")
    assert dl.status_code == 403


def test_non_admin_cannot_access_admin_api(user_client: TestClient):
    assert user_client.get("/v1/admin/tiers").status_code == 403
    assert user_client.get("/v1/admin/users").status_code == 403


def test_admin_can_manage_tiers_and_adjust_points(admin_client: TestClient):
    tiers = admin_client.get("/v1/admin/tiers").json()["items"]
    assert len(tiers) == 4
    created = admin_client.post(
        "/v1/admin/tiers",
        json={
            "code": "vip",
            "name": "VIP",
            "monthly_points": 500,
            "price_monthly": 9900,
            "can_download": True,
            "can_rewrite": True,
            "max_article_length": 6000,
        },
    )
    assert created.status_code == 200
    created_tiers = admin_client.get("/v1/admin/tiers").json()["items"]
    assert any(t["code"] == "vip" for t in created_tiers)
    patched = admin_client.patch("/v1/admin/tiers/vip", json={"code": "vip", "name": "VIP", "monthly_points": 777})
    assert patched.json()["monthly_points"] == 777
    admin_client.post(
        "/v1/auth/register",
        json={"username": "adjustme", "password": "password123", "confirm_password": "password123"},
    )
    # 注册会覆盖 admin 会话 cookie，需重新登录管理员
    admin_client.post("/v1/auth/login", json={"username": "adminuser", "password": "password123"})
    users = admin_client.get("/v1/admin/users").json()["items"]
    target = next(u for u in users if u["username"] == "adjustme")
    adj = admin_client.post(f"/v1/admin/users/{target['user_id']}/points", json={"delta": 50, "reason": "补偿"})
    assert adj.status_code == 200
    assert adj.json()["points_balance"] == target["points_balance"] + 50
    assert admin_client.get("/v1/admin/usage").status_code == 200


def test_admin_usage_filter_by_user(admin_client: TestClient):
    admin_client.post(
        "/v1/auth/register",
        json={"username": "user_u2", "password": "password123", "confirm_password": "password123"},
    )
    # 注册会覆盖 admin 会话 cookie，需重新登录管理员
    admin_client.post("/v1/auth/login", json={"username": "adminuser", "password": "password123"})
    users = admin_client.get("/v1/admin/users").json()["items"]
    uid = next(u["user_id"] for u in users if u["username"] == "user_u2")
    resp = admin_client.get(f"/v1/admin/usage?user_id={uid}").json()
    assert resp["total"] >= 0
