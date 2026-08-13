from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models

# 文章生成按选定长度档预收固定积分；其余操作按 operation_costs 表的积分扣。
ARTICLE_GENERATION = "article_generation"
STYLE_ANALYSIS = "style_analysis"
PARAGRAPH_REWRITE = "paragraph_rewrite"
OPTIMIZE_PROMPT = "optimize_prompt"

QUOTA_PERIOD_DAYS = 30

# 积分余额低于该阈值时，自动给普通用户推送一条系统提醒（站内信）。
LOW_POINTS_THRESHOLD = 3


def parse_target_length_chars(target: str | None) -> int:
    """从「1200字」「2000」等形式中解析出目标字数（整数）。"""
    if not target:
        return 0
    match = re.search(r"(\d+)", target)
    if not match:
        return 0
    return int(match.group(1))


def resolve_tier(db: Session, user: models.User) -> models.MembershipTier | None:
    """解析用户当前等级（从 DB 读取，无等级时回退免费版）。"""
    if user.tier_id:
        tier = db.get(models.MembershipTier, user.tier_id)
        if tier:
            return tier
    return db.get(models.MembershipTier, "free")


def ensure_quota_period(db: Session, user: models.User) -> models.User:
    """懒重置月度积分：过期则把剩余积分重置为该等级月额度，并顺延周期。"""
    now = datetime.now(UTC).replace(microsecond=0)
    quota_end = user.quota_period_end
    if quota_end is not None and quota_end.tzinfo is None:
        # SQLite 读回的 DateTime(timezone=True) 为 naive，补回 UTC 后再比较
        quota_end = quota_end.replace(tzinfo=UTC)
    if quota_end is None or quota_end <= now:
        tier = resolve_tier(db, user)
        monthly = tier.monthly_points if tier else 0
        user.points_balance = monthly
        user.quota_period_start = now
        user.quota_period_end = now + timedelta(days=QUOTA_PERIOD_DAYS)
        user.updated_at = now
        db.commit()
        db.refresh(user)
    return user


def compute_article_points(db: Session, chars: int) -> int:
    """按长度档位查积分（长文折扣，非严格线性）。"""
    brackets = (
        db.scalars(
            select(models.ArticleLengthBracket)
            .where(models.ArticleLengthBracket.is_active.is_(True))
            .order_by(models.ArticleLengthBracket.min_length.asc())
        )
        .all()
    )
    if not brackets:
        return 0
    for bracket in brackets:
        upper = bracket.max_length
        if bracket.min_length <= chars and (upper is None or upper >= chars):
            return bracket.points
    # 超出所有档位上限 → 取最大档位的积分（封顶）
    if chars < brackets[0].min_length:
        return brackets[0].points
    return brackets[-1].points


def get_operation_points(db: Session, op_type: str) -> int:
    cost = db.scalar(
        select(models.OperationCost).where(
            models.OperationCost.op_type == op_type,
            models.OperationCost.is_active.is_(True),
        )
    )
    return cost.points if cost else 0


def validate_and_price(db: Session, user: models.User, op_type: str, *, target_chars: int | None = None) -> int:
    """校验等级长度限制与积分余额，返回本次应扣积分（不在此扣减）。不足抛 402，超长抛 403。"""
    ensure_quota_period(db, user)
    tier = resolve_tier(db, user)

    if target_chars is not None and tier and tier.max_article_length and tier.max_article_length > 0:
        if target_chars > tier.max_article_length:
            raise HTTPException(
                status_code=403,
                detail=f"当前等级单篇文章最大长度为 {tier.max_article_length} 字，请缩短或升级会员。",
            )

    if op_type == ARTICLE_GENERATION:
        points = compute_article_points(db, target_chars or 0)
    else:
        points = get_operation_points(db, op_type)

    if user.points_balance < points:
        raise HTTPException(
            status_code=402,
            detail=f"积分不足，本次操作需要 {points} 积分，当前剩余 {user.points_balance} 积分。",
        )
    return points


def compute_cost_cny(db: Session, model_name: str | None, input_tokens: int, output_tokens: int) -> float:
    """按 model_pricing 表计算真实成本（¥）。"""
    if not model_name or (input_tokens <= 0 and output_tokens <= 0):
        return 0.0
    pricing = db.scalar(
        select(models.ModelPricing).where(
            models.ModelPricing.model == model_name,
            models.ModelPricing.is_active.is_(True),
        )
    )
    if not pricing:
        return 0.0
    cost = (input_tokens / 1_000_000) * float(pricing.input_price_per_m)
    cost += (output_tokens / 1_000_000) * float(pricing.output_price_per_m)
    return round(cost, 6)


def charge(
    db: Session,
    user: models.User,
    op_type: str,
    points: int,
    *,
    document_id: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    model_name: str | None = None,
) -> models.UsageRecord:
    """扣减积分并写入消耗流水（含真实成本）。调用前应先 validate_and_price。"""
    user.points_balance = max(0, user.points_balance - points)
    user.updated_at = datetime.now(UTC).replace(microsecond=0)
    cost_cny = compute_cost_cny(db, model_name, input_tokens, output_tokens)
    record = models.UsageRecord(
        id=models.new_id("usage"),
        user_id=user.id,
        op_type=op_type,
        points_consumed=points,
        document_id=document_id,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_cny=cost_cny,
    )
    db.add(record)
    # 积分低于阈值时自动推送系统提醒（仅普通用户，避免管理员自提醒刷屏）
    if not user.is_admin and 0 < user.points_balance <= LOW_POINTS_THRESHOLD:
        from app.core import message_service as _ms

        _ms._add_system_message(
            db,
            user.id,
            title="积分即将用尽",
            body=f"您当前剩余积分为 {user.points_balance}，即将不足以继续使用付费功能，请及时充值或升级会员。",
            category="system",
        )
    db.commit()
    db.refresh(record)
    return record


def get_quota_view(db: Session, user: models.User) -> dict:
    """/v1/account/quota 的返回结构。"""
    ensure_quota_period(db, user)
    tier = resolve_tier(db, user)
    brackets = (
        db.scalars(
            select(models.ArticleLengthBracket)
            .where(models.ArticleLengthBracket.is_active.is_(True))
            .order_by(models.ArticleLengthBracket.min_length.asc())
        )
        .all()
    )
    style_points = get_operation_points(db, STYLE_ANALYSIS)
    rewrite_points = get_operation_points(db, PARAGRAPH_REWRITE)
    return {
        "tier": {
            "code": tier.code if tier else "free",
            "name": tier.name if tier else "免费版",
            "monthly_points": tier.monthly_points if tier else 0,
            "price_monthly": tier.price_monthly if tier else 0,
            "style_limit": tier.style_limit if tier else 0,
            "material_limit": tier.material_limit if tier else 0,
            "can_download": tier.can_download if tier else False,
            "can_rewrite": tier.can_rewrite if tier else False,
            "max_article_length": tier.max_article_length if tier else 0,
        },
        "points_balance": user.points_balance,
        "quota_period_end": user.quota_period_end.isoformat() if user.quota_period_end else None,
        "operation_points": {
            "style_analysis": style_points,
            "paragraph_rewrite": rewrite_points,
        },
        "article_length_brackets": [
            {"label": b.label, "min_length": b.min_length, "max_length": b.max_length, "points": b.points}
            for b in brackets
        ],
    }


def list_usage(db: Session, user: models.User, *, page: int = 1, page_size: int = 20) -> dict:
    """当前用户的积分消耗流水（分页）。"""
    total = db.scalar(
        select(func.count())
        .select_from(models.UsageRecord)
        .where(models.UsageRecord.user_id == user.id)
    )
    total = total or 0
    query = (
        select(models.UsageRecord)
        .where(models.UsageRecord.user_id == user.id)
        .order_by(models.UsageRecord.created_at.desc())
    )
    records = db.scalars(query.offset((max(1, page) - 1) * page_size).limit(page_size)).all()
    items = [
        {
            "id": r.id,
            "op_type": r.op_type,
            "points_consumed": r.points_consumed,
            "document_id": r.document_id,
            "model_name": r.model_name,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cost_cny": float(r.cost_cny),
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]
    return {"total": total if total is not None else len(items), "page": page, "page_size": page_size, "items": items}


def assign_default_tier(db: Session, user: models.User) -> models.User:
    """注册时分配默认（免费）等级与初始额度。"""
    if user.tier_id:
        return user
    free = db.get(models.MembershipTier, "free")
    if not free:
        return user
    now = datetime.now(UTC).replace(microsecond=0)
    user.tier_id = free.code
    user.points_balance = free.monthly_points
    user.quota_period_start = now
    user.quota_period_end = now + timedelta(days=QUOTA_PERIOD_DAYS)
    user.updated_at = now
    db.commit()
    db.refresh(user)
    return user
