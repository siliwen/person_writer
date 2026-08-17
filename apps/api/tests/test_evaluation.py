"""TDD tests for 文章鉴评（article evaluation）feature.

Covers:
- deterministic feature extraction (sentence stats / TTR / AI-tell flags)
- weighted scoring + grade mapping
- POST /v1/writing-tasks/{id}/evaluate  (manual re-evaluation)
- GET  /v1/writing-tasks/{id}/evaluation (latest report)
- genre gating (首版仅散文)
- ownership isolation
- auto evaluation hook after 散文 generation + system message
- op_article_evaluate seed row (预留计费开关，首版 points=0)
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
def eval_env():
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
        json={"username": username, "password": password, "confirm_password": password, "agreed_terms": True},
    )


def _login(c: TestClient, username: str, password: str = "password123") -> None:
    c.post("/v1/auth/login", json={"username": username, "password": password})


def _make_style(c: TestClient, name: str = "样例风格") -> str:
    upload = c.post(
        "/v1/materials/upload",
        data={"genre": "散文"},
        files=[("files", ("s.txt", "样本文字内容，用来诊断风格。".encode("utf-8"), "text/plain"))],
    )
    mid = upload.json()["materials"][0]["id"]
    job = c.post("/v1/style-analysis-jobs", json={"material_ids": [mid]}).json()
    style = c.post(
        "/v1/style-profiles/confirm",
        json={"job_id": job["id"], "name": name, "profile": job["draft_profile"]},
    ).json()
    return style["id"]


def _make_task(c: TestClient, style_id: str, *, genre: str = "散文", length: str = "1000字") -> dict:
    resp = c.post(
        "/v1/writing-tasks",
        json={
            "style_profile_id": style_id,
            "requested_mode": "style_prompt_only",
            "task": {
                "genre": genre,
                "task_type": "新写",
                "title": "附近生活",
                "brief": "写一篇关于街角小店的散文",
                "target_length": length,
            },
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------- 单元：确定性特征抽取 ----------------

def test_extract_features_basic_stats():
    from app.core import evaluation_service as ev

    text = "春天来了。花开了，鸟叫了。\n\n我在窗边站着，看了很久。"
    features = ev.extract_features(text, target_length="1000字")
    assert features["paragraph_count"] == 2
    assert features["sentence_count"] >= 3
    assert features["char_count"] > 0
    assert 0 < features["ttr"] <= 1
    assert features["avg_sentence_length"] > 0
    # 目标 1000 字，实际远低于 → 偏差为负且显著
    assert features["length_deviation_ratio"] < 0


def test_extract_features_detects_ai_tells():
    from app.core import evaluation_service as ev

    text = (
        "这不仅是一场旅行——更是一次心灵的洗礼。"
        "它不仅关乎风景，更关乎人生的意义。"
        "在这个快节奏的时代，我们每个人都值得拥有诗和远方。"
        "总而言之，让我们一起拥抱生活，拥抱未来，拥抱希望。"
    )
    features = ev.extract_features(text, target_length="1000字")
    assert isinstance(features["ai_tell_flags"], list)
    assert len(features["ai_tell_flags"]) >= 1


# ---------------- 单元：评分与等级 ----------------

def test_grade_mapping():
    from app.core import evaluation_service as ev

    assert ev.grade_for(9.5) == "S"
    assert ev.grade_for(8.2) == "A"
    assert ev.grade_for(7.1) == "B"
    assert ev.grade_for(6.0) == "C"
    assert ev.grade_for(3.0) == "D"


def test_weighted_overall_score():
    from app.core import evaluation_service as ev

    dims = [{"key": key, "score": 8.0} for key, _label, _w in ev.DIMENSIONS]
    assert ev.weighted_score(dims) == pytest.approx(8.0, abs=0.01)
    assert sum(weight for _k, _l, weight in ev.DIMENSIONS) == pytest.approx(1.0, abs=0.001)


def test_supported_genres_prose_only():
    from app.core import evaluation_service as ev

    assert ev.is_supported_genre("散文") is True
    assert ev.is_supported_genre("诗歌") is False


# ---------------- 配置种子 ----------------

def test_operation_cost_seed_row_exists(eval_env):
    _c, SLS = eval_env
    db = SLS()
    row = db.scalar(select(models.OperationCost).where(models.OperationCost.op_type == "article_evaluate"))
    db.close()
    assert row is not None
    assert row.points == 0  # 首版暂免费，预留开关


# ---------------- 接口：鉴评 ----------------

def test_evaluate_requires_auth(eval_env):
    c, _SLS = eval_env
    resp = c.post("/v1/writing-tasks/task_missing/evaluate")
    assert resp.status_code == 401


def test_evaluate_prose_returns_structured_report(eval_env):
    c, _SLS = eval_env
    _register(c, "evaluser")
    style_id = _make_style(c)
    task = _make_task(c, style_id)

    resp = c.post(f"/v1/writing-tasks/{task['task_id']}/evaluate")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["genre"] == "散文"
    assert body["grade"] in {"S", "A", "B", "C", "D"}
    assert 0 <= body["overall_score"] <= 10

    report = body["report"]
    assert set(["overall", "dimensions", "suggestions", "style_deviations", "ai_tell_flags", "features"]) <= set(report)
    assert len(report["dimensions"]) == 5
    for dim in report["dimensions"]:
        assert {"key", "label", "weight", "score", "comment"} <= set(dim)
        assert 0 <= dim["score"] <= 10
    assert isinstance(report["suggestions"], list)
    assert "仅供参考" in report["disclaimer"]


def test_evaluate_rejects_unsupported_genre(eval_env):
    c, _SLS = eval_env
    _register(c, "poetuser")
    style_id = _make_style(c)
    task = _make_task(c, style_id, genre="诗歌")

    resp = c.post(f"/v1/writing-tasks/{task['task_id']}/evaluate")
    assert resp.status_code == 422
    assert "散文" in resp.json()["detail"]


def test_get_evaluation_returns_latest(eval_env):
    c, _SLS = eval_env
    _register(c, "latestuser")
    style_id = _make_style(c)
    task = _make_task(c, style_id)

    first = c.post(f"/v1/writing-tasks/{task['task_id']}/evaluate").json()
    second = c.post(f"/v1/writing-tasks/{task['task_id']}/evaluate").json()
    assert first["id"] != second["id"]

    got = c.get(f"/v1/writing-tasks/{task['task_id']}/evaluation")
    assert got.status_code == 200
    assert got.json()["id"] == second["id"]


def test_get_evaluation_404_when_absent(eval_env):
    c, _SLS = eval_env
    _register(c, "absentuser")
    style_id = _make_style(c)
    task = _make_task(c, style_id, genre="诗歌")  # 非散文不会自动鉴评

    resp = c.get(f"/v1/writing-tasks/{task['task_id']}/evaluation")
    assert resp.status_code == 404


def test_evaluate_other_users_task_is_hidden(eval_env):
    c, _SLS = eval_env
    _register(c, "owneruser")
    style_id = _make_style(c)
    task = _make_task(c, style_id)
    c.post("/v1/auth/logout")

    _register(c, "otheruser")
    resp = c.post(f"/v1/writing-tasks/{task['task_id']}/evaluate")
    assert resp.status_code == 404


def test_evaluation_row_is_persisted(eval_env):
    c, SLS = eval_env
    _register(c, "persistuser")
    style_id = _make_style(c)
    task = _make_task(c, style_id)

    db = SLS()
    rows = db.scalars(
        select(models.ArticleEvaluation).where(models.ArticleEvaluation.writing_task_id == task["task_id"])
    ).all()
    db.close()
    assert len(rows) >= 1
    assert rows[0].report is not None


# ---------------- 自动化钩子 ----------------

def test_auto_evaluation_after_prose_generation(eval_env):
    c, _SLS = eval_env
    _register(c, "autouser")
    style_id = _make_style(c)
    task = _make_task(c, style_id)

    resp = c.get(f"/v1/writing-tasks/{task['task_id']}/evaluation")
    assert resp.status_code == 200
    assert resp.json()["genre"] == "散文"


def test_auto_evaluation_pushes_system_message(eval_env):
    c, _SLS = eval_env
    _register(c, "notifyuser")
    style_id = _make_style(c)
    _make_task(c, style_id)

    inbox = c.get("/v1/messages").json()
    assert any("鉴评" in item["title"] for item in inbox["items"])


def test_generation_response_carries_evaluation_summary(eval_env):
    c, _SLS = eval_env
    _register(c, "summaryuser")
    style_id = _make_style(c)
    task = _make_task(c, style_id)

    assert task.get("evaluation") is not None
    assert task["evaluation"]["grade"] in {"S", "A", "B", "C", "D"}
