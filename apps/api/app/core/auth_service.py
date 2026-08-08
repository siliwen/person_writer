from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.mvp_service import new_id


SESSION_COOKIE_NAME = "pw_session"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{6,32}$")
MAINLAND_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def auth_secret() -> str:
    return os.getenv("AUTH_SECRET", "dev-only-personal-writing-agent-secret")


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> str:
    normalized = username.strip()
    if not USERNAME_RE.fullmatch(normalized):
        raise HTTPException(status_code=422, detail="用户名必须为 6-32 位英文字母、数字或下划线。")
    return normalized


def validate_password(password: str) -> str:
    if not 8 <= len(password) <= 64:
        raise HTTPException(status_code=422, detail="密码必须为 8-64 位。")
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        raise HTTPException(status_code=422, detail="密码必须至少包含 1 个字母和 1 个数字。")
    return password


def validate_mainland_phone(phone_number: str) -> str:
    normalized = phone_number.strip()
    if not MAINLAND_PHONE_RE.fullmatch(normalized):
        raise HTTPException(status_code=422, detail="请输入有效的中国大陆手机号。")
    return normalized


def hash_password(password: str, *, salt: str | None = None) -> str:
    resolved_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), resolved_salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256$120000${resolved_salt}${digest.hex()}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


def register_user(db: Session, *, username: str, password: str, confirm_password: str) -> models.User:
    normalized_username = validate_username(username)
    validate_password(password)
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致。")
    username_key = normalize_username(normalized_username)
    existing = db.scalar(select(models.User).where(models.User.username_normalized == username_key))
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在，请换一个用户名。")
    user = models.User(
        id=new_id("user"),
        username=normalized_username,
        username_normalized=username_key,
        display_name=normalized_username,
        password_hash=hash_password(password),
        mode="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, username: str, password: str) -> models.User:
    user = db.scalar(select(models.User).where(models.User.username_normalized == normalize_username(username)))
    if not user or user.mode != "user" or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误。")
    return user


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def sign_session(user_id: str, *, now: datetime | None = None) -> str:
    issued_at = int((now or datetime.now(UTC)).timestamp())
    payload = {"sub": user_id, "iat": issued_at, "exp": issued_at + SESSION_MAX_AGE_SECONDS}
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(auth_secret().encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_b64url_encode(signature)}"


def verify_session_token(token: str) -> str:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="登录已失效。") from None
    expected_signature = hmac.new(auth_secret().encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_encode(expected_signature), signature):
        raise HTTPException(status_code=401, detail="登录已失效。")
    try:
        payload = json.loads(_b64url_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="登录已失效。") from None
    if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录。")
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=401, detail="登录已失效。")
    return user_id


def set_session_cookie(response: Response, user: models.User) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        sign_session(user.id),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def current_user_from_request(db: Session, request: Request) -> models.User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="请先登录。")
    user_id = verify_session_token(token)
    user = db.get(models.User, user_id)
    if not user or user.mode != "user":
        raise HTTPException(status_code=401, detail="请先登录。")
    return user


def hash_code(code: str) -> str:
    return hmac.new(auth_secret().encode("utf-8"), code.encode("utf-8"), hashlib.sha256).hexdigest()


def send_phone_bind_code(db: Session, *, user: models.User, phone_number: str) -> dict[str, Any]:
    normalized_phone = validate_mainland_phone(phone_number)
    existing_phone_user = db.scalar(
        select(models.User).where(models.User.phone_number == normalized_phone, models.User.id != user.id)
    )
    if existing_phone_user:
        raise HTTPException(status_code=409, detail="这个手机号已经绑定其他账号。")
    now = datetime.now(UTC).replace(microsecond=0)
    recent = db.scalar(
        select(models.PhoneVerificationCode)
        .where(
            models.PhoneVerificationCode.user_id == user.id,
            models.PhoneVerificationCode.phone_number == normalized_phone,
            models.PhoneVerificationCode.purpose == "bind_phone",
            models.PhoneVerificationCode.created_at >= now - timedelta(seconds=60),
            models.PhoneVerificationCode.consumed_at.is_(None),
        )
        .order_by(models.PhoneVerificationCode.created_at.desc())
    )
    if recent:
        raise HTTPException(status_code=429, detail="验证码发送太频繁，请稍后再试。")
    code = f"{secrets.randbelow(1_000_000):06d}"
    record = models.PhoneVerificationCode(
        id=new_id("phone_code"),
        user_id=user.id,
        phone_number=normalized_phone,
        purpose="bind_phone",
        code_hash=hash_code(code),
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    db.add(record)
    db.commit()
    return {"phone_number": normalized_phone, "expires_in_seconds": 600, "debug_code": code}


def bind_phone(db: Session, *, user: models.User, phone_number: str, code: str) -> models.User:
    normalized_phone = validate_mainland_phone(phone_number)
    existing_phone_user = db.scalar(
        select(models.User).where(models.User.phone_number == normalized_phone, models.User.id != user.id)
    )
    if existing_phone_user:
        raise HTTPException(status_code=409, detail="这个手机号已经绑定其他账号。")
    now = datetime.now(UTC).replace(microsecond=0)
    record = db.scalar(
        select(models.PhoneVerificationCode)
        .where(
            models.PhoneVerificationCode.user_id == user.id,
            models.PhoneVerificationCode.phone_number == normalized_phone,
            models.PhoneVerificationCode.purpose == "bind_phone",
            models.PhoneVerificationCode.consumed_at.is_(None),
            models.PhoneVerificationCode.expires_at >= now,
        )
        .order_by(models.PhoneVerificationCode.created_at.desc())
    )
    if not record or not hmac.compare_digest(record.code_hash, hash_code(code.strip())):
        raise HTTPException(status_code=400, detail="验证码错误或已过期。")
    record.consumed_at = now
    user.phone_number = normalized_phone
    user.phone_verified_at = now
    user.updated_at = now
    db.commit()
    db.refresh(user)
    return user


def validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_RE.fullmatch(normalized):
        raise HTTPException(status_code=422, detail="请输入有效的邮箱地址。")
    return normalized


def send_email_bind_code(db: Session, *, user: models.User, email: str) -> dict[str, Any]:
    normalized_email = validate_email(email)
    existing_email_user = db.scalar(
        select(models.User).where(models.User.email == normalized_email, models.User.id != user.id)
    )
    if existing_email_user:
        raise HTTPException(status_code=409, detail="这个邮箱已经绑定其他账号。")
    now = datetime.now(UTC).replace(microsecond=0)
    recent = db.scalar(
        select(models.EmailVerificationCode)
        .where(
            models.EmailVerificationCode.user_id == user.id,
            models.EmailVerificationCode.email == normalized_email,
            models.EmailVerificationCode.purpose == "bind_email",
            models.EmailVerificationCode.created_at >= now - timedelta(seconds=60),
            models.EmailVerificationCode.consumed_at.is_(None),
        )
        .order_by(models.EmailVerificationCode.created_at.desc())
    )
    if recent:
        raise HTTPException(status_code=429, detail="验证码发送太频繁，请稍后再试。")
    code = f"{secrets.randbelow(1_000_000):06d}"
    record = models.EmailVerificationCode(
        id=new_id("email_code"),
        user_id=user.id,
        email=normalized_email,
        purpose="bind_email",
        code_hash=hash_code(code),
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    db.add(record)
    db.commit()
    return {"email": normalized_email, "expires_in_seconds": 600, "debug_code": code}


def bind_email(db: Session, *, user: models.User, email: str, code: str) -> models.User:
    normalized_email = validate_email(email)
    existing_email_user = db.scalar(
        select(models.User).where(models.User.email == normalized_email, models.User.id != user.id)
    )
    if existing_email_user:
        raise HTTPException(status_code=409, detail="这个邮箱已经绑定其他账号。")
    now = datetime.now(UTC).replace(microsecond=0)
    record = db.scalar(
        select(models.EmailVerificationCode)
        .where(
            models.EmailVerificationCode.user_id == user.id,
            models.EmailVerificationCode.email == normalized_email,
            models.EmailVerificationCode.purpose == "bind_email",
            models.EmailVerificationCode.consumed_at.is_(None),
            models.EmailVerificationCode.expires_at >= now,
        )
        .order_by(models.EmailVerificationCode.created_at.desc())
    )
    if not record or not hmac.compare_digest(record.code_hash, hash_code(code.strip())):
        raise HTTPException(status_code=400, detail="验证码错误或已过期。")
    record.consumed_at = now
    user.email = normalized_email
    user.email_verified_at = now
    user.updated_at = now
    db.commit()
    db.refresh(user)
    return user


def change_password(
    db: Session,
    *,
    user: models.User,
    old_password: str,
    new_password: str,
    confirm_password: str,
) -> models.User:
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(status_code=401, detail="原密码不正确。")
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="两次输入的新密码不一致。")
    validate_password(new_password)
    if verify_password(new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同。")
    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.now(UTC).replace(microsecond=0)
    db.commit()
    db.refresh(user)
    return user
