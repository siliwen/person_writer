from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.constants import SYSTEM_FREE_WRITE_STYLE_ID


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
    _seed_admin_user()
    _seed_system_styles()
    _seed_prompt_templates()


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
        "description": "VARCHAR(255)",
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
    {"id": "op_optimize_prompt", "op_type": "optimize_prompt", "points": 1, "description": "优化提示词（将简短想法扩展为完整写作需求）"},
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


def _seed_admin_user() -> None:
    """默认超管引导：仅当配置了 ADMIN_USERNAME + ADMIN_PASSWORD 且库内尚无超管时创建。

    读取顺序：环境变量 ADMIN_USERNAME/ADMIN_PASSWORD → 其次 .env.local（与 model_gateway 同款解析）。
    不读取 DATABASE_URL，避免改变本地/线上库路径行为。
    已有超管（或已存在该用户名）则跳过，绝不覆盖。
    """
    from sqlalchemy import func, select

    from app import models
    from app.core.auth_service import (
        hash_password,
        normalize_username,
        validate_password,
        validate_username,
    )
    from app.core.points_service import assign_default_tier

    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    if not username or not password:
        try:
            from app.core.model_gateway import _load_env_file

            envf = _load_env_file()
            username = username or envf.get("ADMIN_USERNAME")
            password = password or envf.get("ADMIN_PASSWORD")
        except Exception:
            pass
    if not username or not password:
        return  # 未配置：保留现有行为（本地开发用 make_admin.py 提权）

    with SessionLocal() as db:
        admin_count = db.scalar(
            select(func.count()).select_from(models.User).where(models.User.is_admin.is_(True))
        )
        if admin_count:
            return  # 已有超管，不重复创建

        existing = db.scalar(
            select(models.User).where(models.User.username_normalized == normalize_username(username))
        )
        if existing:
            if not existing.is_admin:
                existing.is_admin = True
                db.commit()
                print(f"[init_db] 已将现有账号设为超管：{username}")
            return

        try:
            valid_username = validate_username(username)
            validate_password(password)
        except Exception as exc:  # noqa: BLE001
            detail = getattr(exc, "detail", None) or str(exc)
            print(f"[init_db] 跳过默认超管创建（账号/密码不符合规则）：{detail}")
            return

        user = models.User(
            id=models.new_id("user"),
            username=valid_username,
            username_normalized=normalize_username(valid_username),
            display_name=valid_username,
            password_hash=hash_password(password),
            mode="user",
            is_admin=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assign_default_tier(db, user)
        print(f"[init_db] 已创建默认超管账号：{username}（请用该账号登录后台）")


def _seed_system_styles() -> None:
    """确保存在一个系统占位风格档案，供自由写作（无风格生成）文档挂载。

    这样 documents.style_profile_id 仍满足 NOT NULL，无需对既有表做 DROP NOT NULL 重建；
    鉴评逻辑据此识别「无风格」文章并跳过。系统风格不设为推荐，也不会出现在普通用户的风格库。
    """
    from sqlalchemy import select

    from app import models

    with SessionLocal() as db:
        existing = db.get(models.StyleProfile, SYSTEM_FREE_WRITE_STYLE_ID)
        if existing is not None:
            return
        # StyleProfile.user_id 为外键，需要一个已存在的用户；优先取首个管理员，否则取任意用户。
        owner = db.scalar(
            select(models.User).where(models.User.is_admin.is_(True)).order_by(models.User.created_at).limit(1)
        )
        if owner is None:
            owner = db.scalar(select(models.User).order_by(models.User.created_at).limit(1))
        if owner is None:
            return  # 尚无任何用户，跳过（首次空库启动时下次启动再补）
        style = models.StyleProfile(
            id=SYSTEM_FREE_WRITE_STYLE_ID,
            user_id=owner.id,
            name="自由写作(系统)",
            status="active",
            profile={
                "note": "系统占位风格，用于自由写作（无风格生成）文档挂载，不代表任何用户真实文风。",
                "voice": "通用写作语气",
                "tone": "中性克制",
            },
            is_recommended=False,
            is_default=False,
        )
        db.add(style)
        db.commit()
        print(f"[init_db] 已创建系统占位风格：{SYSTEM_FREE_WRITE_STYLE_ID}")


def _seed_prompt_templates() -> None:
    """确保存在一个启用的 optimize_prompt 提示词模板（后台可编辑，无则写入兜底内容）。"""
    from app.core import prompt_template_service

    with SessionLocal() as db:
        prompt_template_service.ensure_default_optimize_template(db)

