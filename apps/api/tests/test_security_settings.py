"""Tests for the security settings endpoints:

- POST /v1/account/password/change  (change password)
- POST /v1/account/email/send-code   (request email bind code, test mode -> debug_code)
- POST /v1/account/email/bind        (bind email with code)

All tests use the ``client`` fixture from ``conftest.py`` which provides an
isolated in-memory database and a logged-in session cookie.
"""

from __future__ import annotations

import pytest


def register_and_login(client, username: str, password: str) -> dict:
    """Register a user and keep the session cookie on the client."""
    r = client.post(
        "/v1/auth/register",
        json={"username": username, "password": password, "confirm_password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["user"]


# --------------------------------------------------------------------------- #
# Password change
# --------------------------------------------------------------------------- #


def test_change_password_success(client):
    register_and_login(client, "alice1", "Password123")
    r = client.post(
        "/v1/account/password/change",
        json={
            "old_password": "Password123",
            "new_password": "NewPassword456",
            "confirm_password": "NewPassword456",
        },
    )
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "alice1"

    # New password logs in; old password is rejected.
    assert client.post("/v1/auth/login", json={"username": "alice1", "password": "NewPassword456"}).status_code == 200
    assert client.post("/v1/auth/login", json={"username": "alice1", "password": "Password123"}).status_code == 401


def test_change_password_wrong_old(client):
    register_and_login(client, "bob123", "Password123")
    r = client.post(
        "/v1/account/password/change",
        json={
            "old_password": "WrongPassword1",
            "new_password": "NewPassword456",
            "confirm_password": "NewPassword456",
        },
    )
    assert r.status_code == 401


def test_change_password_mismatch_confirm(client):
    register_and_login(client, "carol1", "Password123")
    r = client.post(
        "/v1/account/password/change",
        json={
            "old_password": "Password123",
            "new_password": "NewPassword456",
            "confirm_password": "DifferentPass789",
        },
    )
    assert r.status_code == 400


def test_change_password_weak_too_short(client):
    register_and_login(client, "dave12", "Password123")
    r = client.post(
        "/v1/account/password/change",
        json={
            "old_password": "Password123",
            "new_password": "short1",
            "confirm_password": "short1",
        },
    )
    assert r.status_code == 422


def test_change_password_weak_no_digit(client):
    register_and_login(client, "erin12", "Password123")
    r = client.post(
        "/v1/account/password/change",
        json={
            "old_password": "Password123",
            "new_password": "NoDigitsHere",
            "confirm_password": "NoDigitsHere",
        },
    )
    assert r.status_code == 422


def test_change_password_same_as_current(client):
    register_and_login(client, "frank1", "Password123")
    r = client.post(
        "/v1/account/password/change",
        json={
            "old_password": "Password123",
            "new_password": "Password123",
            "confirm_password": "Password123",
        },
    )
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Email binding
# --------------------------------------------------------------------------- #


def test_send_email_code_success(client):
    register_and_login(client, "grace1", "Password123")
    r = client.post("/v1/account/email/send-code", json={"email": "grace@example.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "grace@example.com"
    assert "debug_code" in body
    assert len(body["debug_code"]) == 6


def test_send_email_code_invalid_format(client):
    register_and_login(client, "heidi1", "Password123")
    r = client.post("/v1/account/email/send-code", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_bind_email_success(client):
    register_and_login(client, "ivan12", "Password123")
    send = client.post("/v1/account/email/send-code", json={"email": "ivan@example.com"})
    code = send.json()["debug_code"]
    r = client.post(
        "/v1/account/email/bind",
        json={"email": "ivan@example.com", "code": code},
    )
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "ivan@example.com"
    assert r.json()["user"]["email_verified"] is True

    me = client.get("/v1/me")
    assert me.status_code == 200
    assert me.json()["email"] == "ivan@example.com"
    assert me.json()["email_verified"] is True


def test_bind_email_wrong_code(client):
    register_and_login(client, "judy12", "Password123")
    client.post("/v1/account/email/send-code", json={"email": "judy@example.com"})
    r = client.post(
        "/v1/account/email/bind",
        json={"email": "judy@example.com", "code": "000000"},
    )
    assert r.status_code == 400


def test_bind_email_duplicate(client):
    # User A binds an email.
    register_and_login(client, "usera1", "Password123")
    send_a = client.post("/v1/account/email/send-code", json={"email": "shared@example.com"})
    client.post(
        "/v1/account/email/bind",
        json={"email": "shared@example.com", "code": send_a.json()["debug_code"]},
    )
    # User B tries to send a code for the same email -> 409.
    register_and_login(client, "userb1", "Password456")
    r = client.post("/v1/account/email/send-code", json={"email": "shared@example.com"})
    assert r.status_code == 409


def test_bind_email_idempotent(client):
    register_and_login(client, "kent12", "Password123")
    s1 = client.post("/v1/account/email/send-code", json={"email": "kent@example.com"})
    r1 = client.post(
        "/v1/account/email/bind",
        json={"email": "kent@example.com", "code": s1.json()["debug_code"]},
    )
    assert r1.status_code == 200

    # Re-sending / re-binding the same (owned) email is allowed.
    s2 = client.post("/v1/account/email/send-code", json={"email": "kent@example.com"})
    assert s2.status_code == 200
    r2 = client.post(
        "/v1/account/email/bind",
        json={"email": "kent@example.com", "code": s2.json()["debug_code"]},
    )
    assert r2.status_code == 200
    assert r2.json()["user"]["email"] == "kent@example.com"


# --------------------------------------------------------------------------- #
# Auth guard
# --------------------------------------------------------------------------- #


def test_security_endpoints_require_login(client):
    r1 = client.post(
        "/v1/account/password/change",
        json={"old_password": "x", "new_password": "y", "confirm_password": "y"},
    )
    assert r1.status_code == 401
    r2 = client.post("/v1/account/email/send-code", json={"email": "x@example.com"})
    assert r2.status_code == 401
    r3 = client.post("/v1/account/email/bind", json={"email": "x@example.com", "code": "123456"})
    assert r3.status_code == 401
