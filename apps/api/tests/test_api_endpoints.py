from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient) -> None:
    response = client.post(
        "/v1/auth/register",
        json={"username": "endpoint_user", "password": "writer123", "confirm_password": "writer123", "agreed_terms": True},
    )
    assert response.status_code == 200


def test_healthz() -> None:
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_poetry_task_forces_prompt_only_policy() -> None:
    client = TestClient(app)
    _login(client)

    response = client.post(
        "/v1/writing-tasks",
        json={
            "writer_id": "writer_demo",
            "requested_mode": "style_profile_rag",
            "style_profile": {
                "style_profile_id": "style_demo_v1",
                "writer_id": "writer_demo",
                "voice": {"tone": ["克制"]},
            },
            "rag_snippets": ["诗歌任务不应默认使用 RAG。"],
            "task": {
                "genre": "诗歌",
                "task_type": "新写",
                "title": "雨伞",
                "brief": "写一首短诗",
                "target_length": "12行",
                "target_reader": "诗歌读者",
                "must_include": "雨声",
                "must_avoid": "意象堆叠",
                "eval_focus": "节奏；留白",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["effective_mode"] == "style_prompt_only"
    assert body["rag_enabled"] is False
    assert body["prompt_version"] == "style_prompt_only_v1"


def test_compose_prompt_accepts_style_intensity_and_anti_copy_rules() -> None:
    client = TestClient(app)

    response = client.post(
        "/v1/prompt/compose",
        json={
            "requested_mode": "style_prompt_only",
            "style_profile": {
                "style_profile_id": "style_demo_v1",
                "generation_rules": {
                    "must_do": ["保持克制语气"],
                    "must_avoid": ["空泛抒情"],
                },
            },
            "task": {
                "genre": "散文",
                "task_type": "新写",
                "title": "街角",
                "brief": "写一篇关于街角小店的文章。",
                "target_length": "800字",
                "target_reader": "普通读者",
                "must_include": "街角、小店",
                "must_avoid": "照搬原文",
                "eval_focus": "风格贴近但表达原创",
                "style_intensity": "light",
            },
        },
    )

    assert response.status_code == 200
    user_prompt = response.json()["messages"][1]["content"]
    assert "风格贴近程度：轻度参考" in user_prompt
    assert "语气、节奏、句式结构" in user_prompt
    assert "不要照搬原文人物、地名、事件、固定意象组合或标志性表达" in user_prompt
