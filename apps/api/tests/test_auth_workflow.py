from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_user_can_register_login_get_current_user_and_logout() -> None:
    client = TestClient(app)

    register_response = client.post(
        "/v1/auth/register",
        json={"username": "Writer_01", "password": "writer123", "confirm_password": "writer123"},
    )

    assert register_response.status_code == 200
    registered = register_response.json()["user"]
    assert registered["username"] == "Writer_01"
    assert registered["mode"] == "user"
    assert "password" not in registered
    assert client.cookies.get("pw_session")

    me_response = client.get("/v1/me")
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "Writer_01"

    logout_response = client.post("/v1/auth/logout")
    assert logout_response.status_code == 200
    assert client.cookies.get("pw_session") is None
    assert client.get("/v1/me").status_code == 401

    login_response = client.post("/v1/auth/login", json={"username": "writer_01", "password": "writer123"})
    assert login_response.status_code == 200
    assert login_response.json()["user"]["username"] == "Writer_01"
    assert client.get("/v1/me").status_code == 200


def test_registration_validates_username_password_and_uniqueness() -> None:
    client = TestClient(app)

    assert client.post(
        "/v1/auth/register",
        json={"username": "abc", "password": "writer123", "confirm_password": "writer123"},
    ).status_code == 422
    assert client.post(
        "/v1/auth/register",
        json={"username": "中文用户01", "password": "writer123", "confirm_password": "writer123"},
    ).status_code == 422
    assert client.post(
        "/v1/auth/register",
        json={"username": "Writer_02", "password": "onlyletters", "confirm_password": "onlyletters"},
    ).status_code == 422
    assert client.post(
        "/v1/auth/register",
        json={"username": "Writer_02", "password": "writer123", "confirm_password": "writer124"},
    ).status_code == 400

    first = client.post(
        "/v1/auth/register",
        json={"username": "Writer_02", "password": "writer123", "confirm_password": "writer123"},
    )
    assert first.status_code == 200
    duplicate = client.post(
        "/v1/auth/register",
        json={"username": "writer_02", "password": "writer123", "confirm_password": "writer123"},
    )
    assert duplicate.status_code == 409


def test_business_endpoints_require_login() -> None:
    client = TestClient(app)

    assert client.get("/v1/materials").status_code == 401
    assert client.get("/v1/style-profiles").status_code == 401
    assert client.post("/v1/style-analysis-jobs", json={"material_ids": []}).status_code == 401
    assert client.post(
        "/v1/writing-tasks",
        json={"style_profile_id": "missing", "task": {"genre": "散文", "title": "题目", "brief": "要求"}},
    ).status_code == 401


def test_user_assets_are_isolated_between_logged_in_users() -> None:
    first = TestClient(app)
    second = TestClient(app)

    first.post(
        "/v1/auth/register",
        json={"username": "Writer_03", "password": "writer123", "confirm_password": "writer123"},
    )
    second.post(
        "/v1/auth/register",
        json={"username": "Writer_04", "password": "writer123", "confirm_password": "writer123"},
    )

    upload = first.post(
        "/v1/materials/upload",
        data={"genre": "散文"},
        files=[("files", ("source.txt", "第一段。\n\n第二段。".encode("utf-8"), "text/plain"))],
    )
    assert upload.status_code == 200
    material_id = upload.json()["materials"][0]["id"]
    assert len(first.get("/v1/materials").json()["materials"]) == 1
    assert second.get("/v1/materials").json()["materials"] == []

    cross_user_job = second.post("/v1/style-analysis-jobs", json={"material_ids": [material_id]})
    assert cross_user_job.status_code == 404


def test_user_can_bind_mainland_phone_with_debug_verification_code() -> None:
    client = TestClient(app)
    client.post(
        "/v1/auth/register",
        json={"username": "Writer_05", "password": "writer123", "confirm_password": "writer123"},
    )

    invalid = client.post("/v1/account/phone/send-code", json={"phone_number": "12345"})
    assert invalid.status_code == 422

    send_response = client.post("/v1/account/phone/send-code", json={"phone_number": "13800138000"})
    assert send_response.status_code == 200
    debug_code = send_response.json()["debug_code"]
    assert len(debug_code) == 6

    repeat = client.post("/v1/account/phone/send-code", json={"phone_number": "13800138000"})
    assert repeat.status_code == 429

    bind_response = client.post(
        "/v1/account/phone/bind",
        json={"phone_number": "13800138000", "code": debug_code},
    )
    assert bind_response.status_code == 200
    assert bind_response.json()["user"]["phone_number"] == "13800138000"

    other = TestClient(app)
    other.post(
        "/v1/auth/register",
        json={"username": "Writer_06", "password": "writer123", "confirm_password": "writer123"},
    )
    other_code = other.post("/v1/account/phone/send-code", json={"phone_number": "13800138000"})
    assert other_code.status_code == 409


def test_password_reset_endpoints_are_reserved() -> None:
    client = TestClient(app)

    send = client.post("/v1/auth/password-reset/send-code", json={"phone_number": "13800138000"})
    confirm = client.post(
        "/v1/auth/password-reset/confirm",
        json={"phone_number": "13800138000", "code": "123456", "new_password": "writer123"},
    )

    assert send.status_code == 501
    assert confirm.status_code == 501
