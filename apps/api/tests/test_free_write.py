"""自由写作 + 优化提示词 的端到端测试。

覆盖：
- POST /v1/optimize-prompt（扣 1 积分、调用后台模板的 system prompt、失败回退原文）
- POST /v1/writing-tasks（style_profile_id="" 走自由写作，文档挂系统占位风格，跳过鉴评）
- 超管提示词模板 CRUD（set-active 保证同 purpose 仅一个启用）
- 自由写作文档不可鉴评（422）
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.constants import SYSTEM_FREE_WRITE_STYLE_ID
from app.core.model_gateway import ModelGateway, ModelResult
from app.core.prompt_template_service import PURPOSE_OPTIMIZE_PROMPT
from app.main import app


_login_counter = 0


def _ensure_logged_in(client: TestClient) -> None:
    global _login_counter
    if client.cookies.get("pw_session"):
        return
    _login_counter += 1
    username = f"freewriter_{_login_counter:04d}"
    response = client.post(
        "/v1/auth/register",
        json={"username": username, "password": "writer123", "confirm_password": "writer123"},
    )
    assert response.status_code == 200


def _promote_admin(client: TestClient) -> None:
    from app import models
    from app.database import SessionLocal

    me = client.get("/v1/me").json()
    with SessionLocal() as db:
        user = db.get(models.User, me["user_id"])
        user.is_admin = True
        db.commit()


def _grant_pro(client: TestClient) -> None:
    from app import models
    from app.database import SessionLocal

    me = client.get("/v1/me").json()
    with SessionLocal() as db:
        user = db.get(models.User, me["user_id"])
        pro = db.get(models.MembershipTier, "pro")
        user.tier_id = "pro"
        user.points_balance = pro.monthly_points if pro else 200
        db.commit()


def test_optimize_prompt_uses_backend_template_and_charges_one_point(monkeypatch) -> None:
    client = TestClient(app)
    _ensure_logged_in(client)
    _grant_pro(client)

    captured = {}

    def fake_generate(self, *, messages, purpose, fallback):
        captured["messages"] = messages
        captured["purpose"] = purpose
        return ModelResult(
            content="写一篇关于初秋街景与人事变迁的散文，约1200字，基调清冷克制。",
            model_provider="mock",
            model_name="mock-optimize_prompt",
            input_token_count=10,
            output_token_count=20,
        )

    monkeypatch.setattr(ModelGateway, "generate", fake_generate)

    before = client.get("/v1/account/quota").json()["points_balance"]
    resp = client.post("/v1/optimize-prompt", json={"prompt": "写点关于秋天的事"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["optimized_prompt"].startswith("写一篇关于初秋")
    # 调用时应当使用后台 optimize_prompt 模板作为 system prompt
    assert captured["purpose"] == "optimize_prompt"
    system_text = captured["messages"][0]["content"]
    assert "需求优化器" in system_text
    # 固定扣 1 积分
    after = client.get("/v1/account/quota").json()["points_balance"]
    assert before - after == 1


def test_optimize_prompt_rejects_empty() -> None:
    client = TestClient(app)
    _ensure_logged_in(client)
    resp = client.post("/v1/optimize-prompt", json={"prompt": "   "})
    assert resp.status_code == 400


def test_free_writing_creates_document_with_system_style_and_skips_eval() -> None:
    client = TestClient(app)
    _ensure_logged_in(client)
    _grant_pro(client)

    resp = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": "",
            "requested_mode": "style_prompt_only",
            "task": {
                "genre": "散文",
                "title": "街角旧书店",
                "brief": "温暖克制",
                "target_length": "1200字",
                "target_reader": "普通读者",
                "must_include": "",
                "must_avoid": "",
                "eval_focus": "",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    doc = data["document"]
    assert doc["style_profile_id"] == SYSTEM_FREE_WRITE_STYLE_ID
    assert doc["content"].strip() != ""
    # 自由写作不鉴评：响应中不应出现 evaluation 字段
    assert "evaluation" not in data


def test_free_writing_document_cannot_be_evaluated() -> None:
    client = TestClient(app)
    _ensure_logged_in(client)
    _grant_pro(client)

    created = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": "",
            "task": {
                "genre": "散文",
                "title": "夏末傍晚",
                "brief": "写一首短诗",
                "target_length": "12行",
            },
        },
    )
    assert created.status_code == 200
    task_id = created.json()["task_id"]

    eval_resp = client.post(f"/v1/writing-tasks/{task_id}/evaluate")
    assert eval_resp.status_code == 422
    assert "自由写作" in eval_resp.json()["detail"]


def test_admin_prompt_template_crud_and_unique_active() -> None:
    client = TestClient(app)
    _ensure_logged_in(client)
    _promote_admin(client)

    # 列表应已存在初始化种子（优化提示词）
    list_resp = client.get("/v1/admin/prompt-templates")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert any(t["purpose"] == PURPOSE_OPTIMIZE_PROMPT and t["is_active"] for t in items)

    # 新建一个模板并设为启用，原启用模板应被停用
    create_resp = client.post(
        "/v1/admin/prompt-templates",
        json={"name": "优化提示词-v2", "system_prompt": "你是优化器v2。", "is_active": True},
    )
    assert create_resp.status_code == 200, create_resp.text
    new_id = create_resp.json()["id"]

    list2 = client.get("/v1/admin/prompt-templates").json()["items"]
    active = [t for t in list2 if t["is_active"]]
    assert len(active) == 1
    assert active[0]["id"] == new_id

    # 把旧的重新启用
    old = next(t for t in list2 if t["id"] != new_id)
    reenable = client.post(f"/v1/admin/prompt-templates/{old['id']}/set-active")
    assert reenable.status_code == 200
    list3 = client.get("/v1/admin/prompt-templates").json()["items"]
    assert len([t for t in list3 if t["is_active"]]) == 1
    assert [t for t in list3 if t["is_active"]][0]["id"] == old["id"]

    # 更新与删除
    upd = client.patch(
        f"/v1/admin/prompt-templates/{old['id']}",
        json={"system_prompt": "你是优化器v3，更克制。"},
    )
    assert upd.status_code == 200
    assert "优化器v3" in upd.json()["system_prompt"]

    dele = client.delete(f"/v1/admin/prompt-templates/{new_id}")
    assert dele.status_code == 200

    # 非管理员应被拒绝
    anon = TestClient(app)
    denied = anon.get("/v1/admin/prompt-templates")
    assert denied.status_code in (401, 403)
