from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.core import message_service
from app.core import prompt_template_service
from app.core.auth_service import current_user_from_request
from app.database import get_db
from app.models import new_id, utc_now


def require_admin(request: Request, db: Session = Depends(get_db)) -> models.User:
    user = current_user_from_request(db, request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限。")
    return user


router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin)])


def log_admin_action(
    db: Session,
    actor: models.User,
    action: str,
    target_type: str,
    target_id: str | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    """写一条管理后台操作审计（只追加）。"""
    db.add(
        models.AdminAuditLog(
            id=new_id("audit"),
            actor_id=actor.id,
            actor_name=actor.username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            reason=reason,
        )
    )


# ---------- 请求体 ----------
class TierPayload(BaseModel):
    code: str
    name: str
    monthly_points: int = 0
    price_monthly: int = 0
    style_limit: int = 0
    material_limit: int = 0
    can_download: bool = False
    can_rewrite: bool = False
    max_article_length: int = 0
    sort_order: int = 0
    is_active: bool = True


class BracketPayload(BaseModel):
    id: str | None = None
    label: str
    min_length: int = 0
    max_length: int | None = None
    points: int = 0
    sort_order: int = 0
    is_active: bool = True


class OperationCostPayload(BaseModel):
    id: str | None = None
    op_type: str
    points: int = 0
    description: str | None = None
    is_active: bool = True


class ModelPricingPayload(BaseModel):
    id: str | None = None
    model: str
    input_price_per_m: float = 0
    output_price_per_m: float = 0
    currency: str = "CNY"
    is_active: bool = True
    note: str | None = None


# PATCH 专用请求体：全部字段可选，配合 _apply_fields(partial=True) 实现真正的局部更新。
class TierUpdatePayload(TierPayload):
    code: str | None = None  # type: ignore[assignment]
    name: str | None = None  # type: ignore[assignment]


class BracketUpdatePayload(BracketPayload):
    label: str | None = None  # type: ignore[assignment]


class OperationCostUpdatePayload(OperationCostPayload):
    op_type: str | None = None  # type: ignore[assignment]


class ModelPricingUpdatePayload(ModelPricingPayload):
    model: str | None = None  # type: ignore[assignment]


class AdjustPointsPayload(BaseModel):
    delta: int
    reason: str | None = None


class SetTierPayload(BaseModel):
    tier_code: str
    grant_monthly_points: bool = False
    reason: str | None = None


# ---------- 会员等级 ----------
@router.get("/tiers")
def list_tiers(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(models.MembershipTier).order_by(models.MembershipTier.sort_order)).all()
    return {"items": [_tier_dict(r) for r in rows]}


@router.post("/tiers")
def create_tier(
    payload: TierPayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if db.get(models.MembershipTier, payload.code):
        raise HTTPException(status_code=409, detail="该等级 code 已存在。")
    tier = models.MembershipTier(code=payload.code)
    db.add(tier)
    _apply_tier(tier, payload)
    log_admin_action(db, admin, "create", "tier", tier.code, after=_tier_dict(tier))
    db.commit()
    db.refresh(tier)
    return _tier_dict(tier)


@router.patch("/tiers/{code}")
def update_tier(
    code: str,
    payload: TierUpdatePayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tier = db.get(models.MembershipTier, code)
    if not tier:
        raise HTTPException(status_code=404, detail="等级不存在。")
    before = _tier_dict(tier)
    _apply_tier(tier, payload, partial=True)
    log_admin_action(db, admin, "update", "tier", code, before=before, after=_tier_dict(tier))
    db.commit()
    db.refresh(tier)
    return _tier_dict(tier)


@router.delete("/tiers/{code}")
def delete_tier(
    code: str,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if code == "free":
        raise HTTPException(status_code=400, detail="免费版不可删除。")
    tier = db.get(models.MembershipTier, code)
    if not tier:
        raise HTTPException(status_code=404, detail="等级不存在。")
    referenced = db.scalar(select(models.User).where(models.User.tier_id == code).limit(1))
    if referenced:
        raise HTTPException(status_code=409, detail="仍有会员属于该等级，无法删除。")
    log_admin_action(db, admin, "delete", "tier", code, before=_tier_dict(tier))
    db.delete(tier)
    db.commit()
    return {"status": "ok"}


# ---------- 文章长度档位 ----------
@router.get("/article-length-brackets")
def list_brackets(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(models.ArticleLengthBracket).order_by(models.ArticleLengthBracket.min_length)).all()
    return {"items": [_bracket_dict(r) for r in rows]}


@router.post("/article-length-brackets")
def create_bracket(
    payload: BracketPayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    bracket_id = payload.id or new_id("bracket")
    if db.get(models.ArticleLengthBracket, bracket_id):
        raise HTTPException(status_code=409, detail="该档位 id 已存在。")
    bracket = models.ArticleLengthBracket(id=bracket_id)
    db.add(bracket)
    _apply_bracket(bracket, payload)
    log_admin_action(db, admin, "create", "bracket", bracket.id, after=_bracket_dict(bracket))
    db.commit()
    db.refresh(bracket)
    return _bracket_dict(bracket)


@router.patch("/article-length-brackets/{bracket_id}")
def update_bracket(
    bracket_id: str,
    payload: BracketUpdatePayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    bracket = db.get(models.ArticleLengthBracket, bracket_id)
    if not bracket:
        raise HTTPException(status_code=404, detail="档位不存在。")
    before = _bracket_dict(bracket)
    _apply_bracket(bracket, payload, partial=True)
    log_admin_action(db, admin, "update", "bracket", bracket_id, before=before, after=_bracket_dict(bracket))
    db.commit()
    db.refresh(bracket)
    return _bracket_dict(bracket)


@router.delete("/article-length-brackets/{bracket_id}")
def delete_bracket(
    bracket_id: str,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    bracket = db.get(models.ArticleLengthBracket, bracket_id)
    if not bracket:
        raise HTTPException(status_code=404, detail="档位不存在。")
    log_admin_action(db, admin, "delete", "bracket", bracket_id, before=_bracket_dict(bracket))
    db.delete(bracket)
    db.commit()
    return {"status": "ok"}


# ---------- 固定操作积分 ----------
@router.get("/operation-costs")
def list_operation_costs(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(models.OperationCost)).all()
    return {"items": [_opcost_dict(r) for r in rows]}


@router.post("/operation-costs")
def create_operation_cost(
    payload: OperationCostPayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cost_id = payload.id or new_id("opcost")
    if db.get(models.OperationCost, cost_id):
        raise HTTPException(status_code=409, detail="该操作积分 id 已存在。")
    cost = models.OperationCost(id=cost_id)
    db.add(cost)
    _apply_opcost(cost, payload)
    log_admin_action(db, admin, "create", "opcost", cost.id, after=_opcost_dict(cost))
    db.commit()
    db.refresh(cost)
    return _opcost_dict(cost)


@router.patch("/operation-costs/{cost_id}")
def update_operation_cost(
    cost_id: str,
    payload: OperationCostUpdatePayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cost = db.get(models.OperationCost, cost_id)
    if not cost:
        raise HTTPException(status_code=404, detail="操作积分不存在。")
    before = _opcost_dict(cost)
    _apply_opcost(cost, payload, partial=True)
    log_admin_action(db, admin, "update", "opcost", cost_id, before=before, after=_opcost_dict(cost))
    db.commit()
    db.refresh(cost)
    return _opcost_dict(cost)


@router.delete("/operation-costs/{cost_id}")
def delete_operation_cost(
    cost_id: str,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    cost = db.get(models.OperationCost, cost_id)
    if not cost:
        raise HTTPException(status_code=404, detail="操作积分不存在。")
    log_admin_action(db, admin, "delete", "opcost", cost_id, before=_opcost_dict(cost))
    db.delete(cost)
    db.commit()
    return {"status": "ok"}


# ---------- 模型单价 ----------
@router.get("/model-pricing")
def list_model_pricing(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(models.ModelPricing)).all()
    return {"items": [_price_dict(r) for r in rows]}


@router.post("/model-pricing")
def create_model_pricing(
    payload: ModelPricingPayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    price_id = payload.id or new_id("price")
    if db.get(models.ModelPricing, price_id):
        raise HTTPException(status_code=409, detail="该单价 id 已存在。")
    price = models.ModelPricing(id=price_id)
    db.add(price)
    _apply_price(price, payload)
    log_admin_action(db, admin, "create", "price", price.id, after=_price_dict(price))
    db.commit()
    db.refresh(price)
    return _price_dict(price)


@router.patch("/model-pricing/{price_id}")
def update_model_pricing(
    price_id: str,
    payload: ModelPricingUpdatePayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    price = db.get(models.ModelPricing, price_id)
    if not price:
        raise HTTPException(status_code=404, detail="单价不存在。")
    before = _price_dict(price)
    _apply_price(price, payload, partial=True)
    log_admin_action(db, admin, "update", "price", price_id, before=before, after=_price_dict(price))
    db.commit()
    db.refresh(price)
    return _price_dict(price)


@router.delete("/model-pricing/{price_id}")
def delete_model_pricing(
    price_id: str,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    price = db.get(models.ModelPricing, price_id)
    if not price:
        raise HTTPException(status_code=404, detail="单价不存在。")
    log_admin_action(db, admin, "delete", "price", price_id, before=_price_dict(price))
    db.delete(price)
    db.commit()
    return {"status": "ok"}


# ---------- 会员账号与积分管理 ----------
@router.get("/users")
def list_users(
    page: int = 1,
    page_size: int = 50,
    q: str | None = None,
    tier: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(models.User)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (models.User.username.ilike(like))
            | (models.User.display_name.ilike(like))
            | (models.User.email.ilike(like))
        )
    if tier:
        stmt = stmt.where(models.User.tier_id == tier)
    total = len(db.scalars(stmt).all())
    stmt = stmt.order_by(models.User.created_at.desc()).offset((max(1, page) - 1) * page_size).limit(page_size)
    rows = db.scalars(stmt).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_user_summary(r) for r in rows],
    }


@router.get("/users/{user_id}")
def get_user(user_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")
    return _user_summary(user)


@router.post("/users/{user_id}/points")
def adjust_user_points(
    user_id: str,
    payload: AdjustPointsPayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")
    before = {"points_balance": user.points_balance}
    user.points_balance = max(0, user.points_balance + payload.delta)
    # UsageRecord 约定：points_consumed 为正表示扣减、为负表示补发。
    # payload.delta 是「余额变化量」（正=加分），因此写入时取反，
    # 避免管理员补发被仪表盘统计成「本月消耗」。
    record = models.UsageRecord(
        id=new_id("usage"),
        user_id=user.id,
        op_type="admin_adjust",
        points_consumed=-payload.delta,
        model_name=payload.reason,
        cost_cny=0,
    )
    db.add(record)
    log_admin_action(
        db, admin, "adjust_points", "user", user.id,
        before=before, after={"points_balance": user.points_balance}, reason=payload.reason,
    )
    db.commit()
    db.refresh(user)
    return _user_summary(user)


@router.post("/users/{user_id}/set-tier")
def set_user_tier(
    user_id: str,
    payload: SetTierPayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")
    tier = db.get(models.MembershipTier, payload.tier_code)
    if not tier:
        raise HTTPException(status_code=404, detail="目标等级不存在。")
    before = {"tier_id": user.tier_id, "points_balance": user.points_balance}
    user.tier_id = tier.code
    if payload.grant_monthly_points:
        user.points_balance = tier.monthly_points
    log_admin_action(
        db, admin, "set_tier", "user", user.id,
        before=before,
        after={"tier_id": user.tier_id, "points_balance": user.points_balance},
        reason=payload.reason,
    )
    db.commit()
    db.refresh(user)
    return _user_summary(user)


@router.get("/usage")
def list_all_usage(
    user_id: str | None = None,
    op_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(models.UsageRecord)
    if user_id:
        stmt = stmt.where(models.UsageRecord.user_id == user_id)
    if op_type:
        stmt = stmt.where(models.UsageRecord.op_type == op_type)
    stmt = stmt.order_by(models.UsageRecord.created_at.desc())
    total = len(db.scalars(stmt).all())
    rows = db.scalars(stmt.offset((max(1, page) - 1) * page_size).limit(page_size)).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "op_type": r.op_type,
                "points_consumed": r.points_consumed,
                "document_id": r.document_id,
                "model_name": r.model_name,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_cny": float(r.cost_cny),
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


# ---------- 仪表盘聚合指标 ----------
@router.get("/metrics/overview")
def metrics_overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    now = utc_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_users = db.scalar(select(func.count()).select_from(models.User)) or 0
    new_users_today = (
        db.scalar(
            select(func.count()).select_from(models.User).where(models.User.created_at >= today_start)
        )
        or 0
    )
    active_today = (
        db.scalar(
            select(func.count(models.UsageRecord.user_id.distinct())).where(
                models.UsageRecord.created_at >= today_start
            )
        )
        or 0
    )
    total_documents = db.scalar(select(func.count()).select_from(models.Document)) or 0

    points_consumed_month = (
        db.scalar(
            select(func.coalesce(func.sum(models.UsageRecord.points_consumed), 0)).where(
                models.UsageRecord.created_at >= month_start,
                models.UsageRecord.points_consumed > 0,
            )
        )
        or 0
    )
    cost_month_cny = float(
        db.scalar(
            select(func.coalesce(func.sum(models.UsageRecord.cost_cny), 0.0)).where(
                models.UsageRecord.created_at >= month_start
            )
        )
        or 0.0
    )

    # 预估 MRR：非免费版用户对应等级的月费之和（无订单表，仅估算）
    tiers = db.scalars(select(models.MembershipTier)).all()
    tier_price = {t.code: t.price_monthly for t in tiers}
    users_for_mrr = db.scalars(select(models.User.tier_id)).all()
    mrr_estimate_cny = sum(tier_price.get(t, 0) for t in users_for_mrr if t and t != "free")

    dist_rows = db.query(models.User.tier_id, func.count()).group_by(models.User.tier_id).all()
    tier_name = {t.code: t.name for t in tiers}
    tier_distribution = [
        {"code": code or "none", "name": tier_name.get(code or "", code or "未设置"), "count": cnt}
        for code, cnt in dist_rows
    ]

    return {
        "total_users": total_users,
        "new_users_today": new_users_today,
        "active_today": active_today,
        "total_documents": total_documents,
        "points_consumed_month": int(points_consumed_month),
        "cost_month_cny": round(cost_month_cny, 4),
        "mrr_estimate_cny": mrr_estimate_cny,
        "tier_distribution": tier_distribution,
    }


# ---------- 操作审计日志 ----------
@router.get("/audit-logs")
def list_audit_logs(
    page: int = 1,
    page_size: int = 50,
    target_type: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(models.AdminAuditLog)
    if target_type:
        stmt = stmt.where(models.AdminAuditLog.target_type == target_type)
    stmt = stmt.order_by(models.AdminAuditLog.created_at.desc())
    total = len(db.scalars(stmt).all())
    rows = db.scalars(stmt.offset((max(1, page) - 1) * page_size).limit(page_size)).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "actor_id": r.actor_id,
                "actor_name": r.actor_name,
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "before": r.before,
                "after": r.after,
                "reason": r.reason,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


# ---------- 推荐风格管理 ----------
@router.get("/style-profiles")
def list_admin_style_profiles(
    recommended_only: bool = False,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # 推荐风格管理页只应列出当前管理员自己创建的风格
    stmt = select(models.StyleProfile).where(
        models.StyleProfile.status == "active",
        models.StyleProfile.user_id == admin.id,
    )
    if recommended_only:
        stmt = stmt.where(models.StyleProfile.is_recommended == True)
    rows = db.scalars(
        stmt.order_by(
            models.StyleProfile.is_recommended.desc(),
            models.StyleProfile.created_at.desc(),
        )
    ).all()
    return {"items": [_style_admin_dict(r) for r in rows]}


class StyleRecommendPayload(BaseModel):
    is_recommended: bool


@router.patch("/style-profiles/{style_profile_id}/recommend")
def set_style_recommended(
    style_profile_id: str,
    payload: StyleRecommendPayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    style = db.get(models.StyleProfile, style_profile_id)
    if not style or style.status != "active":
        raise HTTPException(status_code=404, detail="风格不存在。")
    if style.user_id != admin.id:
        raise HTTPException(status_code=403, detail="只能操作自己创建的风格。")
    before = {"is_recommended": style.is_recommended}
    style.is_recommended = payload.is_recommended
    style.updated_at = utc_now()
    log_admin_action(
        db,
        admin,
        "set_recommended" if payload.is_recommended else "unset_recommended",
        "style_profile",
        style.id,
        before=before,
        after={"is_recommended": style.is_recommended},
    )
    db.commit()
    db.refresh(style)
    return _style_admin_dict(style)


# ---------- 消息中心 ----------
class MessageCreatePayload(BaseModel):
    title: str
    body: str
    category: str = "announcement"  # system / announcement / direct
    target_type: str  # all / tier / specific
    target_tiers: list[str] = Field(default_factory=list)
    target_user_ids: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=lambda: ["in_app"])  # 预留 email
    pinned: bool = False
    important: bool = False
    scheduled_at: str | None = None  # ISO 时间，未来时间则定时发送


class MessageTemplatePayload(BaseModel):
    name: str
    title: str
    body: str
    category: str = "announcement"
    channel: str = "in_app"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.get("/messages/recipients-preview")
def preview_message_recipients(
    target_type: str = "all",
    target_tiers: list[str] = Query(default_factory=list),
    target_user_ids: list[str] = Query(default_factory=list),
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """发送前预估送达人数，防止误发全员。"""
    count = message_service.preview_recipients(
        db, target_type, target_tiers, target_user_ids, exclude_user_id=admin.id
    )
    return {"recipient_count": count}


@router.get("/messages")
def list_messages(
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return message_service.list_admin_messages(db, page=page, page_size=page_size, category=category, status=status)


@router.post("/messages")
def create_message_endpoint(
    payload: MessageCreatePayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="标题不能为空。")
    if not payload.body.strip():
        raise HTTPException(status_code=400, detail="正文不能为空。")
    if payload.target_type not in ("all", "tier", "specific"):
        raise HTTPException(status_code=400, detail="target_type 必须是 all / tier / specific 之一。")
    if payload.target_type == "tier" and not payload.target_tiers:
        raise HTTPException(status_code=400, detail="按等级发送需指定 target_tiers。")
    if payload.target_type == "specific" and not payload.target_user_ids:
        raise HTTPException(status_code=400, detail="指定用户发送需指定 target_user_ids。")
    scheduled_at = _parse_dt(payload.scheduled_at)
    msg = message_service.create_message(
        db,
        admin.id,
        title=payload.title,
        body=payload.body,
        category=payload.category,
        target_type=payload.target_type,
        target_tiers=payload.target_tiers,
        target_user_ids=payload.target_user_ids,
        channels=payload.channels,
        pinned=payload.pinned,
        important=payload.important,
        scheduled_at=scheduled_at,
    )
    log_admin_action(
        db,
        admin,
        "send_message" if msg.status == "sent" else "schedule_message",
        "message",
        msg.id,
        after={"title": msg.title, "target_type": msg.target_type, "recipient_count": msg.recipient_count},
    )
    return message_service.message_to_dict(msg)


@router.get("/messages/{message_id}")
def get_message_detail(message_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return message_service.get_admin_message(db, message_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="消息不存在。")


@router.post("/messages/{message_id}/recall")
def recall_message_endpoint(
    message_id: str,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        msg = message_service.recall_message(db, message_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="消息不存在。")
    log_admin_action(db, admin, "recall_message", "message", msg.id, after={"status": msg.status})
    return message_service.message_to_dict(msg)


@router.get("/message-templates")
def list_message_templates(db: Session = Depends(get_db)) -> dict[str, Any]:
    items = message_service.list_templates(db)
    return {"total": len(items), "items": items}


@router.post("/message-templates")
def create_message_template(
    payload: MessageTemplatePayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    t = message_service.create_template(
        db, name=payload.name, title=payload.title, body=payload.body, category=payload.category, channel=payload.channel
    )
    log_admin_action(db, admin, "create", "message_template", t.id, after=message_service.template_to_dict(t))
    return message_service.template_to_dict(t)


@router.patch("/message-templates/{template_id}")
def update_message_template(
    template_id: str,
    payload: MessageTemplatePayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        t = message_service.update_template(
            db,
            template_id,
            name=payload.name,
            title=payload.title,
            body=payload.body,
            category=payload.category,
            channel=payload.channel,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="模板不存在。")
    log_admin_action(db, admin, "update", "message_template", t.id, after=message_service.template_to_dict(t))
    return message_service.template_to_dict(t)


@router.delete("/message-templates/{template_id}")
def delete_message_template(
    template_id: str,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        message_service.delete_template(db, template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="模板不存在。")
    log_admin_action(db, admin, "delete", "message_template", template_id)
    return {"status": "ok"}


# ---------- 序列化辅助 ----------
def _tier_dict(t: models.MembershipTier) -> dict[str, Any]:
    return {
        "code": t.code,
        "name": t.name,
        "monthly_points": t.monthly_points,
        "price_monthly": t.price_monthly,
        "style_limit": t.style_limit,
        "material_limit": t.material_limit,
        "can_download": t.can_download,
        "can_rewrite": t.can_rewrite,
        "max_article_length": t.max_article_length,
        "sort_order": t.sort_order,
        "is_active": t.is_active,
    }


def _bracket_dict(b: models.ArticleLengthBracket) -> dict[str, Any]:
    return {
        "id": b.id,
        "label": b.label,
        "min_length": b.min_length,
        "max_length": b.max_length,
        "points": b.points,
        "sort_order": b.sort_order,
        "is_active": b.is_active,
    }


def _opcost_dict(c: models.OperationCost) -> dict[str, Any]:
    return {
        "id": c.id,
        "op_type": c.op_type,
        "points": c.points,
        "description": c.description,
        "is_active": c.is_active,
    }


def _price_dict(p: models.ModelPricing) -> dict[str, Any]:
    return {
        "id": p.id,
        "model": p.model,
        "input_price_per_m": float(p.input_price_per_m),
        "output_price_per_m": float(p.output_price_per_m),
        "currency": p.currency,
        "is_active": p.is_active,
        "note": p.note,
    }


def _user_summary(u: models.User) -> dict[str, Any]:
    return {
        "user_id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "tier_code": u.tier_id,
        "points_balance": u.points_balance,
        "quota_period_end": u.quota_period_end.isoformat() if u.quota_period_end else None,
        "is_admin": bool(u.is_admin),
        "created_at": u.created_at.isoformat(),
    }


def _style_admin_dict(s: models.StyleProfile) -> dict[str, Any]:
    return {
        "id": s.id,
        "user_id": s.user_id,
        "name": s.name,
        "description": s.description,
        "status": s.status,
        "is_recommended": s.is_recommended,
        "created_at": s.created_at.isoformat(),
    }


def _apply_fields(obj: Any, payload: BaseModel, keys: tuple[str, ...], *, partial: bool) -> None:
    """把 payload 写入 ORM 对象。

    partial=True（PATCH）时只写请求体里**显式出现**的字段。
    否则未传字段会被 pydantic 的默认值覆盖，导致「只想改名称，结果字数区间被清零」这类静默数据丢失。
    """
    provided = payload.model_fields_set if partial else set(keys)
    for key in keys:
        if key in provided:
            setattr(obj, key, getattr(payload, key))


_TIER_FIELDS = (
    "name",
    "monthly_points",
    "price_monthly",
    "style_limit",
    "material_limit",
    "can_download",
    "can_rewrite",
    "max_article_length",
    "sort_order",
    "is_active",
)
_BRACKET_FIELDS = ("label", "min_length", "max_length", "points", "sort_order", "is_active")
_OPCOST_FIELDS = ("op_type", "points", "description", "is_active")
_PRICE_FIELDS = ("model", "input_price_per_m", "output_price_per_m", "currency", "is_active", "note")


def _apply_tier(tier: models.MembershipTier, p: TierPayload, *, partial: bool = False) -> None:
    _apply_fields(tier, p, _TIER_FIELDS, partial=partial)


def _apply_bracket(b: models.ArticleLengthBracket, p: BracketPayload, *, partial: bool = False) -> None:
    _apply_fields(b, p, _BRACKET_FIELDS, partial=partial)


def _apply_opcost(c: models.OperationCost, p: OperationCostPayload, *, partial: bool = False) -> None:
    _apply_fields(c, p, _OPCOST_FIELDS, partial=partial)


def _apply_price(p: models.ModelPricing, payload: ModelPricingPayload, *, partial: bool = False) -> None:
    _apply_fields(p, payload, _PRICE_FIELDS, partial=partial)


# ---------- 提示词模板（后台可编辑全部用途的 system prompt） ----------
class PromptTemplateUpdatePayload(BaseModel):
    system_prompt: str


@router.get("/prompt-templates")
def list_prompt_templates(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = prompt_template_service.list_prompt_templates(db)
    return {"items": [_prompt_template_dict(r) for r in rows]}


@router.get("/prompt-templates/{template_id}")
def get_prompt_template_endpoint(
    template_id: str,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        template = prompt_template_service.get_prompt_template(db, template_id)
    except prompt_template_service.PromptTemplateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return _prompt_template_dict(template)


@router.patch("/prompt-templates/{template_id}")
def update_prompt_template_endpoint(
    template_id: str,
    payload: PromptTemplateUpdatePayload,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # 每个用途只有一条固定模板：仅允许编辑 system_prompt，name/purpose/is_active 锁定。
    try:
        before = _prompt_template_dict(prompt_template_service.get_prompt_template(db, template_id))
        template = prompt_template_service.update_prompt_template(
            db,
            template_id,
            system_prompt=payload.system_prompt,
        )
    except prompt_template_service.PromptTemplateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    log_admin_action(
        db, admin, "update", "prompt_template", template_id, before=before, after=_prompt_template_dict(template)
    )
    return _prompt_template_dict(template)


@router.post("/prompt-templates/{template_id}/reset")
def reset_prompt_template_endpoint(
    template_id: str,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        before = _prompt_template_dict(prompt_template_service.get_prompt_template(db, template_id))
        template = prompt_template_service.reset_admin_prompt_template(db, template_id)
    except prompt_template_service.PromptTemplateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    log_admin_action(
        db, admin, "reset", "prompt_template", template_id, before=before, after=_prompt_template_dict(template)
    )
    return _prompt_template_dict(template)


def _prompt_template_dict(t: models.PromptTemplate) -> dict[str, Any]:
    return {
        "id": t.id,
        "name": t.name,
        "purpose": t.purpose,
        "system_prompt": t.system_prompt,
        "is_active": bool(t.is_active),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
