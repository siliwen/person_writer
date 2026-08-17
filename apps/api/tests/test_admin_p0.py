"""P0 admin UI backend support: overview metrics, user search, set-tier, audit logs."""
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
            json={"username": "adminuser", "password": "password123", "confirm_password": "password123", "agreed_terms": True},
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


def test_admin_metrics_overview(admin_client: TestClient):
    r = admin_client.get("/v1/admin/metrics/overview")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "total_users" in data and "tier_distribution" in data
    assert isinstance(data["tier_distribution"], list)
    # adminuser + 默认免费版 seed 已存在
    assert data["total_users"] >= 1


def test_admin_user_search_and_set_tier(admin_client: TestClient):
    admin_client.post(
        "/v1/auth/register",
        json={"username": "targetuser", "password": "password123", "confirm_password": "password123", "agreed_terms": True},
    )
    admin_client.post("/v1/auth/login", json={"username": "adminuser", "password": "password123"})
    search = admin_client.get("/v1/admin/users?q=targetuser")
    assert search.status_code == 200
    items = search.json()["items"]
    assert any(i["username"] == "targetuser" for i in items)
    user_id = next(i["user_id"] for i in items if i["username"] == "targetuser")

    # 默认应为 free
    detail = admin_client.get(f"/v1/admin/users/{user_id}")
    assert detail.json()["tier_code"] == "free"

    set_tier = admin_client.post(
        f"/v1/admin/users/{user_id}/set-tier",
        json={"tier_code": "pro", "grant_monthly_points": True, "reason": "测试升级"},
    )
    assert set_tier.status_code == 200, set_tier.text
    assert set_tier.json()["tier_code"] == "pro"
    assert set_tier.json()["points_balance"] == 200  # pro 月额度

    # 审计日志应有 set_tier 记录
    logs = admin_client.get("/v1/admin/audit-logs?target_type=user")
    assert logs.status_code == 200
    actions = [e["action"] for e in logs.json()["items"]]
    assert "set_tier" in actions


def test_admin_audit_logs_after_points_adjust(admin_client: TestClient):
    admin_client.post(
        "/v1/auth/register",
        json={"username": "adjustuser", "password": "password123", "confirm_password": "password123", "agreed_terms": True},
    )
    admin_client.post("/v1/auth/login", json={"username": "adminuser", "password": "password123"})
    uid = next(
        i["user_id"] for i in admin_client.get("/v1/admin/users?q=adjustuser").json()["items"]
        if i["username"] == "adjustuser"
    )
    adj = admin_client.post(
        f"/v1/admin/users/{uid}/points",
        json={"delta": 50, "reason": "补偿"},
    )
    assert adj.status_code == 200
    assert adj.json()["points_balance"] >= 50

    logs = admin_client.get("/v1/admin/audit-logs")
    assert any(e["action"] == "adjust_points" for e in logs.json()["items"])


def test_admin_grant_points_not_counted_as_consumption(admin_client: TestClient):
    """管理员补发积分应记为负消耗，不能被仪表盘统计成「本月消耗」。"""
    admin_client.post(
        "/v1/auth/register",
        json={"username": "grantuser", "password": "password123", "confirm_password": "password123", "agreed_terms": True},
    )
    admin_client.post("/v1/auth/login", json={"username": "adminuser", "password": "password123"})
    uid = next(
        i["user_id"] for i in admin_client.get("/v1/admin/users?q=grantuser").json()["items"]
        if i["username"] == "grantuser"
    )
    before = admin_client.get("/v1/admin/metrics/overview").json()["points_consumed_month"]

    admin_client.post(f"/v1/admin/users/{uid}/points", json={"delta": 80, "reason": "补偿"})

    usage = admin_client.get(f"/v1/admin/usage?user_id={uid}").json()
    record = next(r for r in usage["items"] if r["op_type"] == "admin_adjust")
    assert record["points_consumed"] == -80, "补发积分应写成负数（负消耗）"

    after = admin_client.get("/v1/admin/metrics/overview").json()["points_consumed_month"]
    assert after == before, "补发积分不应计入本月消耗"


def test_admin_deduct_points_counted_as_consumption(admin_client: TestClient):
    """管理员扣减积分应记为正消耗，并计入本月消耗。"""
    admin_client.post(
        "/v1/auth/register",
        json={"username": "deductuser", "password": "password123", "confirm_password": "password123", "agreed_terms": True},
    )
    admin_client.post("/v1/auth/login", json={"username": "adminuser", "password": "password123"})
    uid = next(
        i["user_id"] for i in admin_client.get("/v1/admin/users?q=deductuser").json()["items"]
        if i["username"] == "deductuser"
    )
    # 先补到足够额度再扣，避免被 max(0, ...) 截断影响断言
    admin_client.post(f"/v1/admin/users/{uid}/points", json={"delta": 100, "reason": "预置"})
    before = admin_client.get("/v1/admin/metrics/overview").json()["points_consumed_month"]

    admin_client.post(f"/v1/admin/users/{uid}/points", json={"delta": -30, "reason": "违规扣减"})

    usage = admin_client.get(f"/v1/admin/usage?user_id={uid}").json()
    assert any(r["points_consumed"] == 30 for r in usage["items"]), "扣减应写成正数（正消耗）"

    after = admin_client.get("/v1/admin/metrics/overview").json()["points_consumed_month"]
    assert after == before + 30


def test_patch_bracket_is_partial(admin_client: TestClient):
    """PATCH 只应更新请求体里出现的字段，不能把未传字段重置成默认值。"""
    created = admin_client.post(
        "/v1/admin/article-length-brackets",
        json={
            "id": "bracket_partial",
            "label": "局部更新档位",
            "min_length": 9001,
            "max_length": 9999,
            "points": 99,
            "sort_order": 42,
            "is_active": True,
        },
    )
    assert created.status_code == 200

    patched = admin_client.patch(
        "/v1/admin/article-length-brackets/bracket_partial",
        json={"label": "改了名", "points": 55},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["label"] == "改了名"
    assert body["points"] == 55
    # 未传的字段必须原样保留
    assert body["min_length"] == 9001
    assert body["max_length"] == 9999
    assert body["sort_order"] == 42
    assert body["is_active"] is True


def test_patch_tier_is_partial(admin_client: TestClient):
    """会员等级 PATCH 同样必须是局部更新，避免改个名字把权益清空。"""
    before = admin_client.get("/v1/admin/tiers").json()["items"]
    pro = next(t for t in before if t["code"] == "pro")

    patched = admin_client.patch("/v1/admin/tiers/pro", json={"name": "专业版（改）"})
    assert patched.status_code == 200
    body = patched.json()
    assert body["name"] == "专业版（改）"
    assert body["monthly_points"] == pro["monthly_points"]
    assert body["price_monthly"] == pro["price_monthly"]
    assert body["can_download"] == pro["can_download"]
    assert body["max_article_length"] == pro["max_article_length"]


def test_admin_user_search_by_tier(admin_client: TestClient):
    # 升级一个用户到 pro，再按 tier 过滤
    admin_client.post(
        "/v1/auth/register",
        json={"username": "proband", "password": "password123", "confirm_password": "password123", "agreed_terms": True},
    )
    admin_client.post("/v1/auth/login", json={"username": "adminuser", "password": "password123"})
    uid = next(
        i["user_id"] for i in admin_client.get("/v1/admin/users?q=proband").json()["items"]
        if i["username"] == "proband"
    )
    admin_client.post(f"/v1/admin/users/{uid}/set-tier", json={"tier_code": "pro"})
    filtered = admin_client.get("/v1/admin/users?tier=pro")
    assert filtered.status_code == 200
    assert any(i["username"] == "proband" for i in filtered.json()["items"])
