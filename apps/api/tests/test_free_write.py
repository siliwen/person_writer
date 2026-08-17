"""自由写作 + 优化提示词 的端到端测试。

覆盖：
- POST /v1/optimize-prompt（扣 1 积分、调用后台模板的 system prompt、失败回退原文）
- POST /v1/writing-tasks（style_profile_id="" 走自由写作，文档挂系统占位风格，跳过鉴评）
- 超管提示词模板 CRUD（set-active 保证同 purpose 仅一个启用）
- 自由写作文档不可鉴评（422）
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

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
        json={"username": username, "password": "writer123", "confirm_password": "writer123", "agreed_terms": True},
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


def test_admin_prompt_template_list_and_edit_and_reset() -> None:
    from app.core.constants import ALL_PURPOSES

    client = TestClient(app)
    _ensure_logged_in(client)
    _promote_admin(client)

    # 初始化 seed：全部用途各一条启用模板
    list_resp = client.get("/v1/admin/prompt-templates")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    seeded_purposes = {t["purpose"] for t in items}
    assert seeded_purposes == set(ALL_PURPOSES)
    # 每个用途恰好一条且启用
    for purpose in ALL_PURPOSES:
        matching = [t for t in items if t["purpose"] == purpose]
        assert len(matching) == 1
        assert matching[0]["is_active"] is True

    # 编辑：仅 system_prompt 可变
    target = next(t for t in items if t["purpose"] == PURPOSE_OPTIMIZE_PROMPT)
    upd = client.patch(
        f"/v1/admin/prompt-templates/{target['id']}",
        json={"system_prompt": "你是优化器v3，更克制。"},
    )
    assert upd.status_code == 200
    assert "优化器v3" in upd.json()["system_prompt"]

    # 重置为代码默认（恢复为内置 DEFAULT_OPTIMIZE_PROMPT 片段）
    reset = client.post(f"/v1/admin/prompt-templates/{target['id']}/reset")
    assert reset.status_code == 200
    assert "需求优化器" in reset.json()["system_prompt"]

    # 非管理员应被拒绝
    anon = TestClient(app)
    denied = anon.get("/v1/admin/prompt-templates")
    assert denied.status_code in (401, 403)


def test_free_writing_title_parsed_from_model_output(monkeypatch) -> None:
    """标题由模型生成（标题：XXX 格式），解析后存入 document.title，正文不含标题行。"""
    client = TestClient(app)
    _ensure_logged_in(client)
    _grant_pro(client)

    def fake_generate(self, *, messages, purpose, fallback):
        return ModelResult(
            content="标题：街角的旧书店\n\n那家书店藏在巷子尽头，木质招牌被雨水浸得发暗。\n\n每个周末我都会去翻几本旧书，老板从不催促。",
            model_provider="mock",
            model_name="mock-free-write",
            input_token_count=10,
            output_token_count=60,
        )

    monkeypatch.setattr(ModelGateway, "generate", fake_generate)

    resp = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": "",
            "requested_mode": "style_prompt_only",
            "task": {
                "genre": "散文",
                "title": "",
                "brief": "写一篇关于街角旧书店的散文，温暖克制",
                "target_length": "1200字",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["document"]
    assert doc["title"] == "街角的旧书店"
    assert "标题：街角的旧书店" not in doc["content"]
    assert "那家书店藏在巷子尽头" in doc["content"]


def test_free_writing_title_fallback_when_model_skips_format(monkeypatch) -> None:
    """模型未按格式输出标题时，兜底为需求首行（清洗指令前缀，最多 30 字）。"""
    client = TestClient(app)
    _ensure_logged_in(client)
    _grant_pro(client)

    def fake_generate(self, *, messages, purpose, fallback):
        return ModelResult(
            content="那家书店藏在巷子尽头，木质招牌被雨水浸得发暗。\n\n每个周末我都会去翻几本旧书。",
            model_provider="mock",
            model_name="mock-free-write",
            input_token_count=10,
            output_token_count=60,
        )

    monkeypatch.setattr(ModelGateway, "generate", fake_generate)

    resp = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": "",
            "requested_mode": "style_prompt_only",
            "task": {
                "genre": "散文",
                "title": "",
                "brief": "街角旧书店的温暖往事",
                "target_length": "1200字",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["document"]
    assert doc["title"] == "街角旧书店的温暖往事"
    assert "那家书店藏在巷子尽头" in doc["content"]


def test_free_writing_revise_replaces_document_and_charges(monkeypatch) -> None:
    client = TestClient(app)
    _ensure_logged_in(client)
    _grant_pro(client)

    created = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": "",
            "task": {
                "genre": "散文",
                "title": "街角旧书店",
                "brief": "温暖克制",
                "target_length": "1200字",
            },
        },
    )
    assert created.status_code == 200, created.text
    doc_body = created.json()["document"]
    doc_id = doc_body["id"]
    original_content = doc_body["content"]

    def fake_generate(self, *, messages, purpose, fallback):
        user_text = messages[1]["content"]
        if "修改意见" in user_text:
            return ModelResult(
                content="这是改写后的全新文章。\n\n第二段也根据意见重写了。",
                model_provider="mock",
                model_name="mock-revise",
                input_token_count=50,
                output_token_count=40,
            )
        return ModelResult(
            content="原文内容。",
            model_provider="mock",
            model_name="mock-writing",
            input_token_count=30,
            output_token_count=20,
        )

    monkeypatch.setattr(ModelGateway, "generate", fake_generate)

    before = client.get("/v1/account/quota").json()["points_balance"]
    resp = client.post(
        f"/v1/documents/{doc_id}/revise", json={"instruction": "把结尾写得更克制一些"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["content"] != original_content
    assert "改写后" in data["content"]
    assert len(data["paragraphs"]) == 2

    # 自由写作改写按原文 target_length 扣文章生成积分
    after = client.get("/v1/account/quota").json()["points_balance"]
    assert before - after > 0

    # 审计：应新增一条 task_type=改写 的写作任务
    from app import models
    from app.database import SessionLocal

    with SessionLocal() as db:
        tasks = db.scalars(
            select(models.WritingTask).where(models.WritingTask.document_id == doc_id)
        ).all()
        assert any(t.requirements.get("task_type") == "改写" for t in tasks)


def test_free_writing_uses_default_pricing_when_target_length_is_auto(monkeypatch) -> None:
    """无字数选择时，genre='不限'/target_length='按需求' 应正常生成，按默认 1200 字扣积分。"""
    client = TestClient(app)
    _ensure_logged_in(client)
    _grant_pro(client)

    captured: dict[str, Any] = {}

    def fake_generate(self, *, messages, purpose, fallback):
        captured["user_prompt"] = messages[1]["content"]
        return ModelResult(
            content="一首关于光的短诗。\n\n第二段。",
            model_provider="mock",
            model_name="mock-free-auto",
            input_token_count=20,
            output_token_count=20,
        )

    monkeypatch.setattr(ModelGateway, "generate", fake_generate)

    before = client.get("/v1/account/quota").json()["points_balance"]
    resp = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": "",
            "task": {
                "genre": "不限",
                "title": "光的褶皱",
                "brief": "请创作一首现代抒情诗",
                "target_length": "按需求",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    after = client.get("/v1/account/quota").json()["points_balance"]
    # 默认按 1200 字计费，应扣除大于 0 的积分
    assert before - after > 0

    user_prompt = captured.get("user_prompt", "")
    # prompt 中不应再强制指定文体和长度，交由用户 brief 决定
    assert "- 文体：" not in user_prompt
    assert "- 目标长度：" not in user_prompt
    assert "文体由需求自定" in user_prompt
