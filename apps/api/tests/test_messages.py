"""TDD smoke + functional tests for the 消息中心 (Message Center) feature.

Covers:
- admin compose + targeted send (all / tier / specific)
- recipients preview before send
- recall
- admin sent-list with delivery/read stats
- templates CRUD
- user inbox, unread count, mark read / read-all
- system (automated) messages via create_system_message
- low-points automation hook in charge()
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


@pytest.fixture
def msg_env():
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


def _register(c: TestClient, username: str, password: str = "password123") -> None:
    c.post(
        "/v1/auth/register",
        json={"username": username, "password": password, "confirm_password": password},
    )


def _login(c: TestClient, username: str, password: str = "password123") -> None:
    c.post("/v1/auth/login", json={"username": username, "password": password})


def _set_admin(SLS, username: str) -> None:
    db = SLS()
    u = db.scalar(select(models.User).where(models.User.username == username))
    u.is_admin = True
    db.commit()
    db.close()


def _set_tier(SLS, username: str, tier_code: str) -> None:
    db = SLS()
    u = db.scalar(select(models.User).where(models.User.username == username))
    u.tier_id = tier_code
    db.commit()
    db.close()


def _user_id(SLS, username: str) -> str:
    db = SLS()
    u = db.scalar(select(models.User).where(models.User.username == username))
    uid = u.id
    db.close()
    return uid


def _list_user_ids(c: TestClient, SLS, *usernames: str) -> list[str]:
    return [_user_id(SLS, u) for u in usernames]


# ---------------- 冒烟测试 ----------------

def test_message_endpoints_exist(msg_env):
    c, _ = msg_env
    # 匿名访问受保护端点应被拒（401/403），证明路由已挂载
    assert c.get("/v1/messages").status_code in (401, 403)
    assert c.get("/v1/messages/unread-count").status_code in (401, 403)
    assert c.get("/v1/admin/messages").status_code in (401, 403)
    # 注册普通用户后可访问用户侧收件箱
    _register(c, "smokeuser")
    assert c.get("/v1/messages").status_code == 200
    assert c.get("/v1/messages/unread-count").status_code == 200


def test_normal_user_cannot_send_messages(msg_env):
    c, _ = msg_env
    _register(c, "plainuser")
    resp = c.post(
        "/v1/admin/messages",
        json={"title": "x", "body": "y", "target_type": "all"},
    )
    assert resp.status_code == 403


# ---------------- 管理员发送（功能测试） ----------------

def test_admin_send_to_all(msg_env):
    c, SLS = msg_env
    _register(c, "adminuser")
    _set_admin(SLS, "adminuser")
    _register(c, "reader_a")
    _register(c, "reader_b")
    _login(c, "adminuser")

    total_users = len(SLS().scalars(select(models.User)).all())
    resp = c.post(
        "/v1/admin/messages",
        json={"title": "全员公告", "body": "大家好", "target_type": "all", "category": "announcement"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # 发送者本人不计入接收人
    assert body["recipient_count"] == total_users - 1
    assert body["status"] == "sent"
    assert body["target_type"] == "all"

    # reader_a 能收到
    _login(c, "reader_a")
    inbox = c.get("/v1/messages").json()
    assert any(m["title"] == "全员公告" for m in inbox["items"])
    # reader_b 也能收到
    _login(c, "reader_b")
    inbox_b = c.get("/v1/messages").json()
    assert any(m["title"] == "全员公告" for m in inbox_b["items"])


def test_admin_send_to_tier(msg_env):
    c, SLS = msg_env
    _register(c, "adminuser")
    _set_admin(SLS, "adminuser")
    _register(c, "free_user")
    _register(c, "pro_user")
    _set_tier(SLS, "pro_user", "pro")
    _login(c, "adminuser")

    resp = c.post(
        "/v1/admin/messages",
        json={"title": "专业版专属", "body": "hi pro", "target_type": "tier", "target_tiers": ["pro"]},
    )
    assert resp.status_code == 200
    assert resp.json()["recipient_count"] == 1

    _login(c, "free_user")
    assert c.get("/v1/messages").json()["total"] == 0
    _login(c, "pro_user")
    assert c.get("/v1/messages").json()["total"] == 1


def test_admin_send_to_specific(msg_env):
    c, SLS = msg_env
    _register(c, "adminuser")
    _set_admin(SLS, "adminuser")
    _register(c, "specifica")
    _register(c, "specificb")
    _register(c, "specificc")
    _login(c, "adminuser")
    targets = _list_user_ids(c, SLS, "specifica", "specificc")

    resp = c.post(
        "/v1/admin/messages",
        json={"title": "定向", "body": "b", "target_type": "specific", "target_user_ids": targets},
    )
    assert resp.status_code == 200
    assert resp.json()["recipient_count"] == 2

    _login(c, "specificb")
    assert c.get("/v1/messages").json()["total"] == 0
    _login(c, "specifica")
    assert c.get("/v1/messages").json()["total"] == 1


def test_recipients_preview_matches_send(msg_env):
    c, SLS = msg_env
    _register(c, "adminuser")
    _set_admin(SLS, "adminuser")
    _register(c, "previewa")
    _register(c, "previewb")
    _login(c, "adminuser")

    prev = c.get(
        "/v1/admin/messages/recipients-preview",
        params={"target_type": "all"},
    ).json()
    assert prev["recipient_count"] >= 2  # 除发送者外的全部

    sent = c.post(
        "/v1/admin/messages",
        json={"title": "t", "body": "b", "target_type": "all"},
    ).json()
    assert sent["recipient_count"] == prev["recipient_count"]


def test_recall_message(msg_env):
    c, SLS = msg_env
    _register(c, "adminuser")
    _set_admin(SLS, "adminuser")
    _register(c, "reader")
    _login(c, "adminuser")
    mid = c.post(
        "/v1/admin/messages",
        json={"title": "待撤回", "body": "b", "target_type": "all"},
    ).json()["id"]

    recall = c.post(f"/v1/admin/messages/{mid}/recall")
    assert recall.status_code == 200
    assert recall.json()["status"] == "recalled"

    _login(c, "reader")
    inbox = c.get("/v1/messages").json()
    # 撤回后用户侧不再展示
    assert all(m["id"] != mid for m in inbox["items"])


def test_admin_sent_list_with_stats(msg_env):
    c, SLS = msg_env
    _register(c, "adminuser")
    _set_admin(SLS, "adminuser")
    _register(c, "reader")
    _login(c, "adminuser")
    mid = c.post(
        "/v1/admin/messages",
        json={"title": "统计测试", "body": "b", "target_type": "all"},
    ).json()["id"]

    detail = c.get(f"/v1/admin/messages/{mid}").json()
    assert detail["recipient_count"] == 1  # 只有 reader
    assert detail["read_count"] == 0

    _login(c, "reader")
    c.post(f"/v1/messages/{mid}/read")

    _login(c, "adminuser")
    detail2 = c.get(f"/v1/admin/messages/{mid}").json()
    assert detail2["read_count"] == 1


def test_unauthorized_recall_returns_404_for_unknown(msg_env):
    c, SLS = msg_env
    _register(c, "adminuser")
    _set_admin(SLS, "adminuser")
    _login(c, "adminuser")
    assert c.post("/v1/admin/messages/nope/recall").status_code == 404


# ---------------- 用户侧：未读 / 已读 ----------------

def test_unread_count_and_mark_read(msg_env):
    c, SLS = msg_env
    _register(c, "adminuser")
    _set_admin(SLS, "adminuser")
    _register(c, "reader")
    _login(c, "adminuser")
    c.post("/v1/admin/messages", json={"title": "m1", "body": "b", "target_type": "all"})
    c.post("/v1/admin/messages", json={"title": "m2", "body": "b", "target_type": "all"})

    _login(c, "reader")
    assert c.get("/v1/messages/unread-count").json()["unread_count"] == 2
    items = c.get("/v1/messages").json()["items"]
    m1 = next(m for m in items if m["title"] == "m1")
    c.post(f"/v1/messages/{m1['id']}/read")
    assert c.get("/v1/messages/unread-count").json()["unread_count"] == 1

    c.post("/v1/messages/read-all")
    assert c.get("/v1/messages/unread-count").json()["unread_count"] == 0


def test_mark_read_idempotent(msg_env):
    c, SLS = msg_env
    _register(c, "adminuser")
    _set_admin(SLS, "adminuser")
    _register(c, "reader")
    _login(c, "adminuser")
    mid = c.post("/v1/admin/messages", json={"title": "once", "body": "b", "target_type": "all"}).json()["id"]
    _login(c, "reader")
    assert c.post(f"/v1/messages/{mid}/read").status_code == 200
    assert c.post(f"/v1/messages/{mid}/read").status_code == 200
    assert c.get("/v1/messages/unread-count").json()["unread_count"] == 0


def test_unread_only_filter(msg_env):
    c, SLS = msg_env
    _register(c, "adminuser")
    _set_admin(SLS, "adminuser")
    _register(c, "reader")
    _login(c, "adminuser")
    mid = c.post("/v1/admin/messages", json={"title": "f", "body": "b", "target_type": "all"}).json()["id"]
    _login(c, "reader")
    c.post(f"/v1/messages/{mid}/read")
    unread_only = c.get("/v1/messages", params={"unread_only": "true"}).json()
    assert unread_only["total"] == 0
    all_msgs = c.get("/v1/messages").json()
    assert all_msgs["total"] == 1


# ---------------- 系统自动消息 ----------------

def test_create_system_message_appears_in_inbox(msg_env):
    c, SLS = msg_env
    _register(c, "reader")
    from app.core import message_service

    db = SLS()
    u = db.scalar(select(models.User).where(models.User.username == "reader"))
    msg_service = message_service.create_system_message(
        db, u.id, title="积分提醒", body="您的积分即将用尽", category="system"
    )
    db.commit()
    db.close()

    inbox = c.get("/v1/messages").json()
    assert any(m["title"] == "积分提醒" and m["is_automated"] for m in inbox["items"])


def test_low_points_triggers_system_message(msg_env):
    c, SLS = msg_env
    _register(c, "lowuser")
    # 走完整流程把积分耗到阈值以下，触发自动消息
    upload = c.post(
        "/v1/materials/upload",
        data={"genre": "散文"},
        files=[("files", ("s.txt", "样本文字内容。".encode("utf-8"), "text/plain"))],
    )
    mid = upload.json()["materials"][0]["id"]
    job = c.post("/v1/style-analysis-jobs", json={"material_ids": [mid]}).json()
    style = c.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": "风格", "profile": job["draft_profile"]},
    ).json()
    # 生成文章，把免费版额度 10 耗到阈值以下（风格分析 2 + 生成 5 = 7，剩 3）
    c.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": style["id"],
            "requested_mode": "style_prompt_only",
            "task": {"genre": "散文", "task_type": "新写", "title": "t", "brief": "b", "target_length": "2000字"},
        },
    )
    inbox = c.get("/v1/messages").json()
    # 至少应有一条系统提醒（积分相关）被创建
    assert any(m["is_automated"] and m["category"] == "system" for m in inbox["items"])


# ---------------- 消息模板 ----------------

def test_message_template_crud(msg_env):
    c, SLS = msg_env
    _register(c, "adminuser")
    _set_admin(SLS, "adminuser")
    _login(c, "adminuser")

    created = c.post(
        "/v1/admin/message-templates",
        json={"name": "活动预告", "title": "新活动", "body": "内容", "category": "announcement"},
    )
    assert created.status_code == 200
    tid = created.json()["id"]

    listed = c.get("/v1/admin/message-templates").json()
    assert any(t["id"] == tid for t in listed["items"])

    patched = c.patch(f"/v1/admin/message-templates/{tid}", json={"name": "活动预告2", "title": "新活动", "body": "内容", "category": "announcement"})
    assert patched.json()["name"] == "活动预告2"

    assert c.delete(f"/v1/admin/message-templates/{tid}").status_code == 200
    assert c.get("/v1/admin/message-templates").json()["total"] == 0
