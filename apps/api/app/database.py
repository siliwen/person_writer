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
        _ensure_sqlite_document_library_columns()
        _ensure_sqlite_user_membership_columns()
        _ensure_sqlite_style_columns()
        _ensure_sqlite_writing_task_columns()
    _seed_membership_data()


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
        "email": "VARCHAR(255)",
        "email_verified_at": "DATETIME",
        "updated_at": "DATETIME",
    }
    with engine.begin() as connection:
        for name, definition in required_columns.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {definition}"))


def _ensure_sqlite_document_library_columns() -> None:
    inspector = inspect(engine)
    if "documents" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("documents")}
    required_columns = {
        "is_saved": "BOOLEAN DEFAULT 0",
        "saved_at": "DATETIME",
    }
    with engine.begin() as connection:
        for name, definition in required_columns.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE documents ADD COLUMN {name} {definition}"))


def _ensure_sqlite_user_membership_columns() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    required_columns = {
        "tier_id": "VARCHAR(32)",
        "points_balance": "INTEGER NOT NULL DEFAULT 0",
        "quota_period_start": "DATETIME",
        "quota_period_end": "DATETIME",
        "is_admin": "BOOLEAN DEFAULT 0",
    }
    with engine.begin() as connection:
        for name, definition in required_columns.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {definition}"))


def _ensure_sqlite_style_columns() -> None:
    inspector = inspect(engine)
    if "style_profiles" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("style_profiles")}
    required_columns = {
        "is_recommended": "BOOLEAN DEFAULT 0",
    }
    with engine.begin() as connection:
        for name, definition in required_columns.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE style_profiles ADD COLUMN {name} {definition}"))


def _ensure_sqlite_writing_task_columns() -> None:
    """写作任务补 requirements 快照列——文章鉴评的『指令遵循』维度依赖原始写作要求。"""
    inspector = inspect(engine)
    if "writing_tasks" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("writing_tasks")}
    required_columns = {
        "requirements": "JSON",
    }
    with engine.begin() as connection:
        for name, definition in required_columns.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE writing_tasks ADD COLUMN {name} {definition}"))
                connection.execute(text("UPDATE writing_tasks SET requirements = '{}' WHERE requirements IS NULL"))


# 初始（默认）配置——仅在库为空时写入，管理员可在管理后台随时修改，代码不写死业务逻辑。
DEFAULT_TIERS = [
    {"code": "free", "name": "免费版", "monthly_points": 10, "price_monthly": 0,
     "style_limit": 2, "material_limit": 3, "can_download": False, "can_rewrite": False,
     "max_article_length": 2000, "sort_order": 0},
    {"code": "basic", "name": "基础版", "monthly_points": 60, "price_monthly": 1900,
     "style_limit": 10, "material_limit": 20, "can_download": True, "can_rewrite": True,
     "max_article_length": 4000, "sort_order": 1},
    {"code": "pro", "name": "专业版", "monthly_points": 200, "price_monthly": 4900,
     "style_limit": 30, "material_limit": 100, "can_download": True, "can_rewrite": True,
     "max_article_length": 8000, "sort_order": 2},
    {"code": "team", "name": "团队版", "monthly_points": 1000, "price_monthly": 19900,
     "style_limit": 0, "material_limit": 0, "can_download": True, "can_rewrite": True,
     "max_article_length": 10000, "sort_order": 3},
]

DEFAULT_BRACKETS = [
    {"id": "bracket_1000", "label": "1000字", "min_length": 1, "max_length": 1000, "points": 3, "sort_order": 0},
    {"id": "bracket_2000", "label": "2000字", "min_length": 1001, "max_length": 2000, "points": 5, "sort_order": 1},
    {"id": "bracket_3000", "label": "3000字", "min_length": 2001, "max_length": 3000, "points": 8, "sort_order": 2},
    {"id": "bracket_4000", "label": "4000字", "min_length": 3001, "max_length": 4000, "points": 11, "sort_order": 3},
    {"id": "bracket_5000", "label": "5000字", "min_length": 4001, "max_length": 5000, "points": 14, "sort_order": 4},
    {"id": "bracket_8000", "label": "8000字", "min_length": 5001, "max_length": 8000, "points": 22, "sort_order": 5},
    {"id": "bracket_10000", "label": "10000字", "min_length": 8001, "max_length": 10000, "points": 29, "sort_order": 6},
    {"id": "bracket_over", "label": "10000字以上", "min_length": 10001, "max_length": None, "points": 29, "sort_order": 7},
]

DEFAULT_OPERATION_COSTS = [
    {"id": "op_style_analysis", "op_type": "style_analysis", "points": 2, "description": "风格分析（上传作品诊断六维风格）"},
    {"id": "op_paragraph_rewrite", "op_type": "paragraph_rewrite", "points": 1, "description": "段落重写"},
    # 首版暂免费（points=0），预留开关：改为 >0 即可开始计费
    {"id": "op_article_evaluate", "op_type": "article_evaluate", "points": 0, "description": "文章鉴评（按文体量规评分点评）"},
]

DEFAULT_MODEL_PRICING = [
    {"id": "price_qwen3_7_plus", "model": "qwen3.7-plus", "input_price_per_m": 1.6, "output_price_per_m": 6.4,
     "currency": "CNY", "note": "标准价（限时8折）"},
]


def _seed_membership_data(session_factory=SessionLocal) -> None:
    from datetime import timedelta

    from sqlalchemy import select

    from app import models

    with session_factory() as db:
        for tier in DEFAULT_TIERS:
            obj = db.get(models.MembershipTier, tier["code"])
            if obj is None:
                obj = models.MembershipTier(code=tier["code"])
                db.add(obj)
            obj.name = tier["name"]
            obj.monthly_points = tier["monthly_points"]
            obj.price_monthly = tier["price_monthly"]
            obj.style_limit = tier["style_limit"]
            obj.material_limit = tier["material_limit"]
            obj.can_download = tier["can_download"]
            obj.can_rewrite = tier["can_rewrite"]
            obj.max_article_length = tier["max_article_length"]
            obj.sort_order = tier["sort_order"]
            obj.is_active = True

        for bracket in DEFAULT_BRACKETS:
            obj = db.get(models.ArticleLengthBracket, bracket["id"])
            if obj is None:
                obj = models.ArticleLengthBracket(id=bracket["id"])
                db.add(obj)
            obj.label = bracket["label"]
            obj.min_length = bracket["min_length"]
            obj.max_length = bracket["max_length"]
            obj.points = bracket["points"]
            obj.sort_order = bracket["sort_order"]
            obj.is_active = True

        for cost in DEFAULT_OPERATION_COSTS:
            obj = db.get(models.OperationCost, cost["id"])
            if obj is None:
                obj = models.OperationCost(id=cost["id"])
                db.add(obj)
            obj.op_type = cost["op_type"]
            obj.points = cost["points"]
            obj.description = cost["description"]
            obj.is_active = True

        for price in DEFAULT_MODEL_PRICING:
            obj = db.get(models.ModelPricing, price["id"])
            if obj is None:
                obj = models.ModelPricing(id=price["id"])
                db.add(obj)
            obj.model = price["model"]
            obj.input_price_per_m = price["input_price_per_m"]
            obj.output_price_per_m = price["output_price_per_m"]
            obj.currency = price["currency"]
            obj.note = price["note"]
            obj.is_active = True

        # 给历史遗留（无等级）用户分配免费版与初始额度
        free = db.get(models.MembershipTier, "free")
        if free:
            orphan_users = db.scalars(
                select(models.User).where(models.User.tier_id.is_(None))
            ).all()
            now = models.utc_now()
            for user in orphan_users:
                user.tier_id = "free"
                user.points_balance = free.monthly_points
                user.quota_period_start = now
                user.quota_period_end = now + timedelta(days=30)

        db.commit()
