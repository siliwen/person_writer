from __future__ import annotations

from io import BytesIO
import json
import zipfile

from fastapi.testclient import TestClient

from app.core.model_gateway import ModelGateway, ModelResult

from app.main import app


_login_counter = 0


def _ensure_logged_in(client: TestClient) -> None:
    global _login_counter
    if client.cookies.get("pw_session"):
        return
    _login_counter += 1
    username = f"testuser_{_login_counter:04d}"
    response = client.post(
        "/v1/auth/register",
        json={"username": username, "password": "writer123", "confirm_password": "writer123"},
    )
    assert response.status_code == 200

def _force_gateway_fallback(monkeypatch) -> None:
    def fake_generate(self, *, messages, purpose, fallback):
        return ModelResult(
            content=fallback.strip(),
            model_provider="mock",
            model_name=f"mock-{purpose}",
            input_token_count=1,
            output_token_count=max(1, len(fallback) // 2),
        )

    monkeypatch.setattr(ModelGateway, "generate", fake_generate)

def _make_minimal_docx(paragraphs: list[str]) -> bytes:
    document_body = "".join(
        f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>" for paragraph in paragraphs
    )
    document_xml = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        f"<w:body>{document_body}</w:body>"
        "</w:document>"
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _upload_material(client: TestClient, filename: str, content: str) -> str:
    _ensure_logged_in(client)
    response = client.post(
        "/v1/materials/upload",
        data={"genre": "散文"},
        files=[("files", (filename, content.encode("utf-8"), "text/plain"))],
    )
    assert response.status_code == 200
    material = response.json()["materials"][0]
    assert material["paragraph_count"] == 2
    return material["id"]


def _grant_paid_features(client: TestClient) -> None:
    """将当前登录用户提升到 pro 等级，使其在 mvp 流程测试中拥有重写/下载权限与充足积分。

    免费版的功能限制（不能重写/下载、积分限额）由 tests/test_quota_and_admin.py 单独覆盖，
    此处仅为让「功能可用性」类测试不受会员等级限制影响。
    """
    from app import models
    from app.database import SessionLocal

    me = client.get("/v1/me").json()
    with SessionLocal() as db:
        user = db.get(models.User, me["user_id"])
        if user is not None:
            pro = db.get(models.MembershipTier, "pro")
            user.tier_id = "pro"
            user.points_balance = pro.monthly_points if pro else 200
            db.commit()


def test_demo_user_can_upload_analyze_confirm_write_and_rewrite_one_paragraph() -> None:
    client = TestClient(app)

    first_id = _upload_material(client, "a.txt", "门口有一把旧椅子。\n\n风从巷子里过来。")
    second_id = _upload_material(client, "b.txt", "雨落在铁皮棚上。\n\n母亲把灯拧暗。")
    _grant_paid_features(client)

    job_response = client.post("/v1/style-analysis-jobs", json={"material_ids": [first_id, second_id]})
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "draft_pending_confirmation"
    assert job["draft_profile"]["status"] == "draft_pending_confirmation"

    unavailable_response = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": job["id"],
            "task": {"genre": "散文", "title": "附近生活", "brief": "写街角小店"},
        },
    )
    assert unavailable_response.status_code == 404

    confirm_response = client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": "旧巷散文", "profile": job["draft_profile"]},
    )
    assert confirm_response.status_code == 200
    style = confirm_response.json()
    assert style["status"] == "active"
    assert style["name"] == "旧巷散文"

    styles_response = client.get("/v1/style-profiles")
    assert styles_response.status_code == 200
    assert [item["id"] for item in styles_response.json()["styles"]] == [style["id"]]

    writing_response = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": style["id"],
            "requested_mode": "style_profile_rag",
            "task": {
                "genre": "诗歌",
                "title": "雨伞",
                "brief": "写一首关于旧雨伞的短诗",
                "target_length": "12行",
                "target_reader": "文学读者",
                "must_include": "门口、雨声",
                "must_avoid": "空泛抒情",
            },
        },
    )
    assert writing_response.status_code == 200
    writing = writing_response.json()
    assert writing["status"] == "completed"
    assert writing["effective_mode"] == "style_prompt_only"
    assert writing["rag_enabled"] is False
    document = writing["document"]
    original_paragraphs = document["paragraphs"]
    assert len(original_paragraphs) >= 3

    target = original_paragraphs[1]
    rewrite_response = client.post(
        f"/v1/documents/{document['id']}/paragraphs/{target['id']}/rewrite",
        json={"instruction": "更克制一点，减少解释"},
    )
    assert rewrite_response.status_code == 200
    rewritten_content = rewrite_response.json()["rewritten_content"]
    assert rewritten_content
    assert rewritten_content != target["content"]

    # Verify the original document is NOT modified (preview mode)
    doc_response = client.get(f"/v1/documents/{document['id']}")
    assert doc_response.status_code == 200
    doc_after = doc_response.json()
    assert doc_after["paragraphs"][1]["content"] == target["content"]
    assert doc_after["paragraphs"][1]["rewrite_count"] == 0

    # Now overwrite the paragraph with the rewritten content
    overwrite_response = client.put(
        f"/v1/documents/{document['id']}/paragraphs/{target['id']}",
        json={"content": rewritten_content},
    )
    assert overwrite_response.status_code == 200
    overwritten = overwrite_response.json()["paragraphs"]
    assert overwritten[0]["content"] == original_paragraphs[0]["content"]
    assert overwritten[2]["content"] == original_paragraphs[2]["content"]
    assert overwritten[1]["content"] == rewritten_content
    assert overwritten[1]["rewrite_count"] == 1


def test_style_analysis_uses_model_to_create_actionable_v2_profile(monkeypatch) -> None:
    captured: dict[str, object] = {}
    model_profile = {
        "status": "draft_pending_confirmation",
        "profile_version": "style_profile_v2",
        "style_summary": {
            "one_sentence": "从旧物和日常动作进入，以克制观察收束。",
            "stable_features": ["具体物件开篇", "少量判断", "动作收束"],
            "unstable_features": [],
            "confidence": 0.82,
        },
        "source_stats": {
            "material_count": 2,
            "paragraph_count": 4,
            "char_count": 46,
            "avg_paragraph_chars": 11.5,
        },
        "lexical_style": {"noun_preference": ["旧椅子", "铁皮棚"], "avoid_words": ["宏大口号"]},
        "syntax_style": {"sentence_length_pattern": "短句为主", "punctuation_habits": ["句号高频"]},
        "rhetoric_style": {"imagery_sources": ["市井旧物"], "sensory_focus": {"visual": "高"}},
        "narrative_style": {"opening_patterns": ["从物件进入"], "ending_patterns": ["动作收束"]},
        "emotional_tone": {"emotion_intensity": "low", "restraint_level": "high"},
        "topic_boundary": {"common_scenes": ["巷口"], "suitable_topics": ["附近生活"]},
        "language_period_style": {"modernity": "现代书面语"},
        "generation_rules": {
            "must_do": ["从具体物件或动作进入"],
            "must_avoid": ["不要使用 AI 套话"],
            "opening_rule": "从场景、物件或动作开篇。",
            "paragraph_rule": "保留自然段。",
            "sentence_rule": "长短句交替。",
            "ending_rule": "以动作或物件收束。",
            "copying_risk_rules": ["不要复制原文连续短语"],
        },
        "evidence_map": [
            {
                "claim": "常从具体物件进入叙述",
                "material_title": "a.txt",
                "paragraph_index": 1,
                "evidence_type": "structure",
            }
        ],
        "split_recommendation": {"should_split": False, "reason": "", "suggested_profiles": []},
    }

    def fake_generate(self, *, messages, purpose, fallback):
        captured["purpose"] = purpose
        captured["messages"] = messages
        return ModelResult(
            content=json.dumps(model_profile, ensure_ascii=False),
            model_provider="mock",
            model_name="mock-style-analysis",
            input_token_count=10,
            output_token_count=20,
        )

    monkeypatch.setattr(ModelGateway, "generate", fake_generate)
    client = TestClient(app)
    first_id = _upload_material(client, "a.txt", "门口有一把旧椅子。\n\n风从巷子里过来。")
    second_id = _upload_material(client, "b.txt", "雨落在铁皮棚上。\n\n母亲把灯拧暗。")

    response = client.post("/v1/style-analysis-jobs", json={"material_ids": [first_id, second_id]})

    assert response.status_code == 200
    draft = response.json()["draft_profile"]
    assert captured["purpose"] == "style_analysis"
    user_prompt = captured["messages"][1]["content"]  # type: ignore[index]
    assert "词汇与句法层" in user_prompt
    assert "修辞与表达层" in user_prompt
    assert "叙事与结构层" in user_prompt
    assert draft["profile_version"] == "style_profile_v2"
    assert draft["style_summary"]["one_sentence"] == "从旧物和日常动作进入，以克制观察收束。"
    assert draft["generation_rules"]["opening_rule"] == "从场景、物件或动作开篇。"


def test_style_analysis_falls_back_to_v2_profile_when_model_output_is_invalid_json(monkeypatch) -> None:
    def fake_generate(self, *, messages, purpose, fallback):
        return ModelResult(
            content="这不是 JSON",
            model_provider="mock",
            model_name="mock-style-analysis",
            input_token_count=10,
            output_token_count=20,
        )

    monkeypatch.setattr(ModelGateway, "generate", fake_generate)
    client = TestClient(app)
    material_id = _upload_material(client, "fallback-style.txt", "门口有一把旧椅子。\n\n风从巷子里过来。")

    response = client.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]})

    assert response.status_code == 200
    draft = response.json()["draft_profile"]
    assert draft["profile_version"] == "style_profile_v2"
    assert draft["status"] == "draft_pending_confirmation"
    assert "source_stats" in draft
    assert "lexical_style" in draft
    assert "syntax_style" in draft
    assert "rhetoric_style" in draft
    assert "narrative_style" in draft
    assert "generation_rules" in draft
    assert "copying_risk_rules" in draft["generation_rules"]


def test_style_analysis_returns_plain_language_display_report_for_user_confirmation() -> None:
    client = TestClient(app)
    material_id = _upload_material(client, "plain-report.txt", "门口有一把旧椅子。\n\n风从巷子里过来。")

    response = client.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]})

    assert response.status_code == 200
    report = response.json()["draft_profile"]["display_report"]
    assert "我们理解到" in report["plain_summary"]
    dimension_titles = [item["title"] for item in report["dimensions"]]
    assert dimension_titles == [
        "词汇和句子",
        "修辞和表达",
        "叙事和结构",
        "情绪和基调",
        "题材和人物",
        "时代和语体",
    ]
    assert all(item["what_we_found"] for item in report["dimensions"])
    assert report["writing_rules_plain"]["must_do"]
    assert report["writing_rules_plain"]["must_avoid"]
    assert report["evidence_plain"]


def test_chinese_style_analysis_display_report_does_not_show_english_terms(monkeypatch) -> None:
    english_report_profile = {
        "profile_version": "style_profile_v2",
        "style_summary": {"one_sentence": "medium factual reporting style", "stable_features": [], "unstable_features": [], "confidence": 0.7},
        "display_report": {
            "plain_summary": "We found a predominantly medium sentence style.",
            "dimensions": [
                {
                    "key": f"dimension_{index}",
                    "title": title,
                    "what_we_found": ["predominantly medium sentences, used for factual reporting"],
                    "why_it_matters": "this controls writing tools and rhythm",
                    "editable_summary": "",
                }
                for index, title in enumerate(["词汇和句子", "修辞和表达", "叙事和结构", "情绪和基调", "题材和人物", "时代和语体"])
            ],
            "writing_rules_plain": {"must_do": ["avoid English style tags"], "must_avoid": ["AI cliche"]},
            "evidence_plain": ["source paragraph uses writing tools"],
        },
    }

    def fake_generate(self, *, messages, purpose, fallback):
        return ModelResult(
            content=json.dumps(english_report_profile, ensure_ascii=False),
            model_provider="mock",
            model_name="mock-style-analysis",
            input_token_count=10,
            output_token_count=20,
        )

    monkeypatch.setattr(ModelGateway, "generate", fake_generate)
    client = TestClient(app)
    material_id = _upload_material(client, "chinese-report.txt", "门口有一把旧椅子。\n\n风从巷子里过来。")

    response = client.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]})

    assert response.status_code == 200
    report_text = "\n".join(_collect_string_values(response.json()["draft_profile"]["display_report"]))
    assert "predominantly" not in report_text
    assert "medium" not in report_text
    assert "factual" not in report_text
    assert "writing" not in report_text
    assert "AI" not in report_text


def _collect_string_values(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _collect_string_values(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _collect_string_values(item)]
    return []


def test_confirming_style_requires_name() -> None:
    client = TestClient(app)
    material_id = _upload_material(client, "a.txt", "第一段。\n\n第二段。")
    job = client.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]}).json()

    response = client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": "   ", "profile": job["draft_profile"]},
    )

    assert response.status_code == 400


def test_confirming_style_rejects_duplicate_active_name() -> None:
    client = TestClient(app)
    first_material_id = _upload_material(client, "first.txt", "第一段。\n\n第二段。")
    first_job = client.post("/v1/style-analysis-jobs", json={"material_ids": [first_material_id]}).json()
    first_response = client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": first_job["id"], "name": "同名风格", "profile": first_job["draft_profile"]},
    )
    assert first_response.status_code == 200

    second_material_id = _upload_material(client, "second.txt", "第三段。\n\n第四段。")
    second_job = client.post("/v1/style-analysis-jobs", json={"material_ids": [second_material_id]}).json()
    duplicate_response = client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": second_job["id"], "name": " 同名风格 ", "profile": second_job["draft_profile"]},
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "风格名称已存在，请换一个名称。"
    styles = client.get("/v1/style-profiles").json()["styles"]
    assert [style["name"] for style in styles] == ["同名风格"]


def test_reconfirming_same_style_analysis_job_returns_existing_style() -> None:
    client = TestClient(app)
    material_id = _upload_material(client, "source.txt", "第一段。\n\n第二段。")
    job = client.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]}).json()
    payload = {"job_id": job["id"], "name": "可重复确认风格", "profile": job["draft_profile"]}

    first_response = client.post("/v1/style-profiles/confirm", json=payload)
    second_response = client.post("/v1/style-profiles/confirm", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["id"] == first_response.json()["id"]
    styles = client.get("/v1/style-profiles").json()["styles"]
    assert len(styles) == 1


def test_deleting_style_profile_soft_deletes_and_hides_it() -> None:
    client = TestClient(app)
    material_id = _upload_material(client, "delete-style.txt", "第一段。\n\n第二段。")
    job = client.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]}).json()
    style = client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": "待删除风格", "profile": job["draft_profile"]},
    ).json()

    delete_response = client.delete(f"/v1/style-profiles/{style['id']}")

    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"
    assert client.get("/v1/style-profiles").json()["styles"] == []

    writing_response = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": style["id"],
            "task": {
                "genre": "散文",
                "title": "旧风格写作",
                "brief": "删除后的风格不能继续写作。",
            },
        },
    )
    assert writing_response.status_code == 409

    second_delete_response = client.delete(f"/v1/style-profiles/{style['id']}")
    assert second_delete_response.status_code == 200
    assert second_delete_response.json()["status"] == "deleted"


def test_organization_register_intent_is_reserved_only() -> None:
    client = TestClient(app)

    response = client.post("/v1/organizations/register-intent")

    assert response.status_code == 501
    assert response.json()["status"] == "not_implemented"


def test_local_network_frontend_origin_can_call_upload_api() -> None:
    client = TestClient(app)

    response = client.options(
        "/v1/materials/upload",
        headers={
            "Origin": "http://192.168.0.112:3002",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://192.168.0.112:3002"


def test_user_can_upload_docx_and_get_paragraphs() -> None:
    client = TestClient(app)
    _ensure_logged_in(client)
    docx = _make_minimal_docx(["门口有一把旧椅子。", "风从巷子里过来。"])

    response = client.post(
        "/v1/materials/upload",
        data={"genre": "散文"},
        files=[
            (
                "files",
                (
                    "sample.docx",
                    docx,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            )
        ],
    )

    assert response.status_code == 200
    material = response.json()["materials"][0]
    assert material["source_filename"] == "sample.docx"
    assert material["paragraph_count"] == 2
    assert material["paragraphs"][0]["content"] == "门口有一把旧椅子。"



def test_mock_writing_fallback_outputs_article_not_instructions(monkeypatch) -> None:
    _force_gateway_fallback(monkeypatch)
    client = TestClient(app)
    material_id = _upload_material(client, "fallback.txt", "巷口的灯亮得很慢。\n\n木门后有旧年的灰尘。")
    job = client.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]}).json()
    style = client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": "克制散文", "profile": job["draft_profile"]},
    ).json()

    response = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": style["id"],
            "requested_mode": "style_prompt_only",
            "task": {
                "genre": "散文",
                "title": "附近生活",
                "brief": "写一篇关于街角小店和旧物的文章。",
                "target_length": "600字",
                "target_reader": "普通读者",
                "must_include": "具体场景、自然段、克制表达",
                "must_avoid": "AI 套话、空泛抒情、宏大口号",
            },
        },
    )

    assert response.status_code == 200
    document = response.json()["document"]
    content = document["content"]
    assert document["paragraphs"][0]["content"] != document["title"]
    assert len(document["paragraphs"]) >= 4
    assert "这是按" not in content
    assert "生成的" not in content
    assert "第二个自然段" not in content
    assert "必须包含" not in content
    assert "避免：" not in content
    assert "AI 套话" not in content
    assert len(content) >= 300


def test_repeated_mock_writing_requests_create_distinct_documents(monkeypatch) -> None:
    _force_gateway_fallback(monkeypatch)
    client = TestClient(app)
    material_id = _upload_material(client, "repeat.txt", "门口有一只旧木箱。\n\n雨停后，地上还有水痕。")
    _grant_paid_features(client)
    job = client.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]}).json()
    style = client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": "重复生成风格", "profile": job["draft_profile"]},
    ).json()
    payload = {
        "style_profile_id": style["id"],
        "requested_mode": "style_prompt_only",
        "task": {
            "genre": "散文",
            "title": "附近生活",
            "brief": "写一篇关于街角小店和旧物的文章。",
            "target_length": "1200字",
            "target_reader": "普通读者",
            "must_include": "具体场景、自然段、克制表达",
            "must_avoid": "AI 套话、空泛抒情、宏大口号",
        },
    }

    first = client.post("/v1/writing-tasks", json=payload).json()["document"]
    second = client.post("/v1/writing-tasks", json=payload).json()["document"]

    assert first["id"] != second["id"]
    assert first["content"] != second["content"]


def test_writing_task_sends_style_intensity_to_model_prompt(monkeypatch) -> None:
    captured_user_prompt = ""

    def fake_generate(self, *, messages, purpose, fallback):
        nonlocal captured_user_prompt
        # 散文生成完成后会自动触发一次鉴评（purpose="article_evaluate"），
        # 这里只捕获写作本身的 prompt，避免被后续调用覆盖。
        if purpose == "writing":
            captured_user_prompt = messages[1]["content"]
        return ModelResult(
            content="第一段原创内容。\n\n第二段原创内容。\n\n第三段原创内容。",
            model_provider="mock",
            model_name=f"mock-{purpose}",
            input_token_count=1,
            output_token_count=10,
        )

    monkeypatch.setattr(ModelGateway, "generate", fake_generate)
    client = TestClient(app)
    material_id = _upload_material(client, "intensity.txt", "门口有一把旧椅子。\n\n风从巷子里过来。")
    job = client.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]}).json()
    style = client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": "贴近程度测试风格", "profile": job["draft_profile"]},
    ).json()

    response = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": style["id"],
            "requested_mode": "style_prompt_only",
            "task": {
                "genre": "散文",
                "title": "新街角",
                "brief": "写一篇新的街角文章。",
                "target_length": "800字",
                "target_reader": "普通读者",
                "must_include": "街角",
                "must_avoid": "照搬原文",
                "style_intensity": "close",
            },
        },
    )

    assert response.status_code == 200
    assert "风格贴近程度：高度贴近" in captured_user_prompt
    assert "避免让结果像替换内容后的改写稿" in captured_user_prompt


def test_preview_rewrite_does_not_modify_original_document(monkeypatch) -> None:
    _force_gateway_fallback(monkeypatch)
    client = TestClient(app)
    material_id = _upload_material(client, "preview-rewrite.txt", "门口有一把旧椅子。\n\n风从巷子里过来。")
    _grant_paid_features(client)
    job = client.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]}).json()
    style = client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": "预览重写风格", "profile": job["draft_profile"]},
    ).json()

    writing = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": style["id"],
            "requested_mode": "style_prompt_only",
            "task": {
                "genre": "散文",
                "title": "预览测试",
                "brief": "写一篇短文",
                "target_length": "600字",
            },
        },
    ).json()
    document = writing["document"]
    target = document["paragraphs"][0]
    original_content = target["content"]

    rewrite_response = client.post(
        f"/v1/documents/{document['id']}/paragraphs/{target['id']}/rewrite",
        json={"instruction": "更简短"},
    )
    assert rewrite_response.status_code == 200
    assert "rewritten_content" in rewrite_response.json()
    rewritten = rewrite_response.json()["rewritten_content"]
    assert rewritten != original_content

    # Verify original document unchanged
    doc_after = client.get(f"/v1/documents/{document['id']}").json()
    assert doc_after["paragraphs"][0]["content"] == original_content
    assert doc_after["paragraphs"][0]["rewrite_count"] == 0


def test_update_paragraph_overwrites_content_directly(monkeypatch) -> None:
    _force_gateway_fallback(monkeypatch)
    client = TestClient(app)
    material_id = _upload_material(client, "overwrite.txt", "门口有一把旧椅子。\n\n风从巷子里过来。")
    job = client.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]}).json()
    style = client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": "覆盖测试风格", "profile": job["draft_profile"]},
    ).json()

    writing = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": style["id"],
            "requested_mode": "style_prompt_only",
            "task": {
                "genre": "散文",
                "title": "覆盖测试",
                "brief": "写一篇短文",
                "target_length": "600字",
            },
        },
    ).json()
    document = writing["document"]
    target = document["paragraphs"][0]
    original_content = target["content"]
    manual_edit = "这是我手动修改的段落内容，不经过AI。"

    overwrite_response = client.put(
        f"/v1/documents/{document['id']}/paragraphs/{target['id']}",
        json={"content": manual_edit},
    )
    assert overwrite_response.status_code == 200
    updated = overwrite_response.json()
    assert updated["paragraphs"][0]["content"] == manual_edit
    assert updated["paragraphs"][0]["content"] != original_content
    assert updated["paragraphs"][0]["rewrite_count"] == 1
    # Other paragraphs unchanged
    assert updated["paragraphs"][1]["content"] == document["paragraphs"][1]["content"]
    # Document content field is updated too
    assert manual_edit in updated["content"]


def test_update_paragraph_rejects_empty_content(monkeypatch) -> None:
    _force_gateway_fallback(monkeypatch)
    client = TestClient(app)
    material_id = _upload_material(client, "empty-test.txt", "门口有一把旧椅子。\n\n风从巷子里过来。")
    job = client.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]}).json()
    style = client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": "空内容测试风格", "profile": job["draft_profile"]},
    ).json()

    writing = client.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": style["id"],
            "requested_mode": "style_prompt_only",
            "task": {"genre": "散文", "title": "空内容", "brief": "写一篇短文", "target_length": "600字"},
        },
    ).json()
    document = writing["document"]
    target = document["paragraphs"][0]

    response = client.put(
        f"/v1/documents/{document['id']}/paragraphs/{target['id']}",
        json={"content": "   "},
    )
    assert response.status_code == 200
    # Whitespace-only content should be stripped to empty
    assert response.json()["paragraphs"][0]["content"] == ""


def _confirm_style(client: TestClient, name: str, profile: dict | None = None) -> dict:
    first_id = _upload_material(client, "a.txt", "门口有一把旧椅子。\n\n风从巷子里过来。")
    second_id = _upload_material(client, "b.txt", "雨落在铁皮棚上。\n\n母亲把灯拧暗。")
    job_response = client.post("/v1/style-analysis-jobs", json={"material_ids": [first_id, second_id]})
    assert job_response.status_code == 200
    job = job_response.json()
    confirm_response = client.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": name, "profile": profile or job["draft_profile"]},
    )
    assert confirm_response.status_code == 200
    return confirm_response.json()


def test_updating_style_profile_changes_name_and_profile() -> None:
    client = TestClient(app)
    _ensure_logged_in(client)
    style = _confirm_style(client, "旧巷散文")

    response = client.patch(
        f"/v1/style-profiles/{style['id']}",
        json={"name": "改后的风格", "profile": {"tone": "冷峻"}},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "改后的风格"
    assert updated["profile"]["tone"] == "冷峻"
    assert updated["profile"]["style_name"] == "改后的风格"

    # Profile-only update (name unchanged) is allowed
    profile_only = client.patch(
        f"/v1/style-profiles/{style['id']}",
        json={"name": "改后的风格", "profile": {"tone": "温柔"}},
    )
    assert profile_only.status_code == 200
    assert profile_only.json()["name"] == "改后的风格"
    assert profile_only.json()["profile"]["tone"] == "温柔"


def test_updating_style_profile_rejects_duplicate_name() -> None:
    client = TestClient(app)
    _ensure_logged_in(client)
    _confirm_style(client, "风格A")
    style_b = _confirm_style(client, "风格B")

    response = client.patch(
        f"/v1/style-profiles/{style_b['id']}",
        json={"name": "风格A", "profile": None},
    )
    assert response.status_code == 409
    assert "风格名称已存在" in response.json()["detail"]


def test_updating_style_profile_requires_non_empty_name() -> None:
    client = TestClient(app)
    _ensure_logged_in(client)
    style = _confirm_style(client, "旧巷散文")

    response = client.patch(
        f"/v1/style-profiles/{style['id']}",
        json={"name": "   ", "profile": None},
    )
    assert response.status_code == 400


def test_setting_default_style_marks_only_one_active_style() -> None:
    client = TestClient(app)
    _ensure_logged_in(client)
    first = _confirm_style(client, "风格A")
    second = _confirm_style(client, "风格B")

    set_response = client.post(f"/v1/style-profiles/{second['id']}/set-default")
    assert set_response.status_code == 200
    assert set_response.json()["is_default"] is True

    styles_response = client.get("/v1/style-profiles")
    styles = styles_response.json()["styles"]
    defaults = [s for s in styles if s["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == second["id"]
    assert first["id"] != second["id"]

    # Setting default on the same style again is idempotent
    repeat = client.post(f"/v1/style-profiles/{second['id']}/set-default")
    assert repeat.status_code == 200
    assert repeat.json()["is_default"] is True


