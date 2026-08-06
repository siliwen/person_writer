from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
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
