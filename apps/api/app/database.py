from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./personal_writing_agent_mvp1.db"


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def build_engine(url: str | None = None):
    resolved_url = url or database_url()
    connect_args = {}
    engine_kwargs = {}
    if resolved_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if resolved_url.endswith(":memory:"):
            engine_kwargs["poolclass"] = StaticPool
    return create_engine(resolved_url, connect_args=connect_args, **engine_kwargs)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(*, drop_existing: bool = False) -> None:
    from app import models  # noqa: F401

    if drop_existing:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    if engine.url.get_backend_name() == "sqlite":
        _ensure_sqlite_auth_columns()


def _ensure_sqlite_auth_columns() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    required_columns = {
        "username": "VARCHAR(32)",
        "username_normalized": "VARCHAR(32)",
        "password_hash": "VARCHAR(255)",
        "phone_number": "VARCHAR(11)",
        "phone_verified_at": "DATETIME",
        "updated_at": "DATETIME",
    }
    with engine.begin() as connection:
        for name, definition in required_columns.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {definition}"))
