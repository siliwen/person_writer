"""消息中心服务层：撰写定向发送、收件箱、未读统计、撤回、系统自动消息。

数据模型：
- Message：一条消息（管理员手动或系统自动），含接收范围 target_type(all/tier/specific)。
- MessageDelivery：每条消息对每个接收人的送达记录，支撑未读计数与已读率。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.models import new_id, utc_now


# ---------------------------------------------------------------------------
# 接收人解析
# ---------------------------------------------------------------------------

def resolve_recipient_ids(
    db: Session,
    target_type: str,
    target_tiers: list[str] | None = None,
    target_user_ids: list[str] | None = None,
    *,
    exclude_user_id: str | None = None,
) -> set[str]:
    """根据 target_type 解析出应接收该消息的用户 id 集合。"""
    recipients: set[str] = set()
    if target_type == "all":
        rows = db.scalars(select(models.User)).all()
        recipients = {u.id for u in rows}
    elif target_type == "tier":
        tiers = target_tiers or []
        if tiers:
            rows = db.scalars(select(models.User).where(models.User.tier_id.in_(tiers))).all()
            recipients = {u.id for u in rows}
    elif target_type == "specific":
        ids = target_user_ids or []
        if ids:
            rows = db.scalars(select(models.User).where(models.User.id.in_(ids))).all()
            recipients = {u.id for u in rows}
    if exclude_user_id:
        recipients.discard(exclude_user_id)
    return recipients


def preview_recipients(
    db: Session,
    target_type: str,
    target_tiers: list[str] | None = None,
    target_user_ids: list[str] | None = None,
    *,
    exclude_user_id: str | None = None,
) -> int:
    return len(resolve_recipient_ids(db, target_type, target_tiers, target_user_ids, exclude_user_id=exclude_user_id))


# ---------------------------------------------------------------------------
# 创建 / 发送
# ---------------------------------------------------------------------------

def create_message(
    db: Session,
    sender_id: str,
    *,
    title: str,
    body: str,
    category: str = "announcement",
    target_type: str = "all",
    target_tiers: list[str] | None = None,
    target_user_ids: list[str] | None = None,
    channels: list[str] | None = None,
    pinned: bool = False,
    important: bool = False,
    scheduled_at: datetime | None = None,
    is_automated: bool = False,
    exclude_self: bool = True,
) -> models.Message:
    """创建一条消息并按接收范围批量生成送达记录。立即提交。

    exclude_self=True（默认）时，发送者本人不计入接收人（避免管理员广播给自己）。
    系统自动消息以接收人自身作为占位 sender，必须传 exclude_self=False 才能正确送达。
    """
    recipient_ids = resolve_recipient_ids(
        db,
        target_type,
        target_tiers,
        target_user_ids,
        exclude_user_id=sender_id if exclude_self else None,
    )
    now = utc_now()
    scheduled = bool(scheduled_at and scheduled_at > now)
    msg = models.Message(
        id=new_id("msg"),
        sender_id=sender_id,
        title=title,
        body=body,
        category=category,
        target_type=target_type,
        target_tiers=list(target_tiers or []),
        target_user_ids=list(target_user_ids or []),
        channels=list(channels or ["in_app"]),
        status="scheduled" if scheduled else "sent",
        pinned=bool(pinned),
        important=bool(important),
        is_automated=bool(is_automated),
        scheduled_at=scheduled_at,
        sent_at=None if scheduled else now,
        recipient_count=len(recipient_ids),
        created_at=now,
        updated_at=now,
    )
    db.add(msg)
    for uid in recipient_ids:
        db.add(
            models.MessageDelivery(
                id=new_id("mdl"),
                message_id=msg.id,
                user_id=uid,
                is_read=False,
                read_at=None,
            )
        )
    db.commit()
    db.refresh(msg)
    return msg


def _add_system_message(
    db: Session,
    user_id: str,
    *,
    title: str,
    body: str,
    category: str = "system",
) -> models.Message:
    """底层：添加一条系统消息（不提交），供 charge 等在同一事务内复用。"""
    return create_message(
        db,
        sender_id=user_id,  # 系统消息无真实发送人，用接收人自身占位（sender_id 仅展示用）
        title=title,
        body=body,
        category=category,
        target_type="specific",
        target_user_ids=[user_id],
        channels=["in_app"],
        is_automated=True,
        exclude_self=False,
    )


def create_system_message(
    db: Session,
    user_id: str,
    *,
    title: str,
    body: str,
    category: str = "system",
) -> models.Message:
    """对外便捷函数：创建一条系统自动消息并立即提交。"""
    return _add_system_message(db, user_id, title=title, body=body, category=category)


def recall_message(db: Session, message_id: str) -> models.Message:
    msg = db.get(models.Message, message_id)
    if not msg:
        raise KeyError(message_id)
    if msg.status == "recalled":
        return msg
    msg.status = "recalled"
    msg.updated_at = utc_now()
    db.commit()
    db.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# 管理员查询
# ---------------------------------------------------------------------------

def list_admin_messages(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    stmt = select(models.Message).where(models.Message.sender_id.is_not(None))
    if category:
        stmt = stmt.where(models.Message.category == category)
    if status:
        stmt = stmt.where(models.Message.status == status)
    total = len(db.scalars(stmt).all())
    rows = db.scalars(
        stmt.order_by(
            models.Message.pinned.desc(),
            models.Message.created_at.desc(),
        )
        .offset((max(1, page) - 1) * page_size)
        .limit(page_size)
    ).all()
    items = []
    for m in rows:
        read_count = (
            db.scalar(
                select(func.count())
                .select_from(models.MessageDelivery)
                .where(models.MessageDelivery.message_id == m.id, models.MessageDelivery.is_read == True)  # noqa: E712
            )
            or 0
        )
        d = message_to_dict(m)
        d["read_count"] = int(read_count)
        items.append(d)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def get_admin_message(db: Session, message_id: str) -> dict[str, Any]:
    msg = db.get(models.Message, message_id)
    if not msg:
        raise KeyError(message_id)
    read_count = (
        db.scalar(
            select(func.count())
            .select_from(models.MessageDelivery)
            .where(models.MessageDelivery.message_id == msg.id, models.MessageDelivery.is_read == True)  # noqa: E712
        )
        or 0
    )
    d = message_to_dict(msg)
    d["read_count"] = int(read_count)
    return d


# ---------------------------------------------------------------------------
# 用户侧收件箱 / 未读
# ---------------------------------------------------------------------------

def list_user_inbox(
    db: Session,
    user_id: str,
    *,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    base = (
        select(models.Message, models.MessageDelivery.is_read, models.MessageDelivery.read_at)
        .join(models.MessageDelivery, models.MessageDelivery.message_id == models.Message.id)
        .where(models.MessageDelivery.user_id == user_id, models.Message.status != "recalled")
    )
    if unread_only:
        base = base.where(models.MessageDelivery.is_read == False)  # noqa: E712
    total = len(db.execute(base).all())
    ordered = base.order_by(
        models.Message.pinned.desc(),
        models.Message.sent_at.isnot(None).desc(),
        models.Message.sent_at.desc(),
        models.Message.created_at.desc(),
    ).offset((max(1, page) - 1) * page_size).limit(page_size)
    rows = db.execute(ordered).all()
    items = [
        message_inbox_item(m, is_read, read_at) for (m, is_read, read_at) in rows
    ]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def get_unread_count(db: Session, user_id: str) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(models.MessageDelivery)
            .join(models.Message, models.Message.id == models.MessageDelivery.message_id)
            .where(
                models.MessageDelivery.user_id == user_id,
                models.MessageDelivery.is_read == False,  # noqa: E712
                models.Message.status != "recalled",
            )
        )
        or 0
    )


def mark_read(db: Session, message_id: str, user_id: str) -> bool:
    delivery = db.scalars(
        select(models.MessageDelivery).where(
            models.MessageDelivery.message_id == message_id,
            models.MessageDelivery.user_id == user_id,
        )
    ).first()
    if not delivery:
        return False
    if not delivery.is_read:
        delivery.is_read = True
        delivery.read_at = utc_now()
        db.commit()
    return True


def mark_all_read(db: Session, user_id: str) -> int:
    deliveries = db.scalars(
        select(models.MessageDelivery).where(
            models.MessageDelivery.user_id == user_id,
            models.MessageDelivery.is_read == False,  # noqa: E712
        )
    ).all()
    now = utc_now()
    for d in deliveries:
        d.is_read = True
        d.read_at = now
    db.commit()
    return len(deliveries)


# ---------------------------------------------------------------------------
# 序列化
# ---------------------------------------------------------------------------

def message_to_dict(m: models.Message) -> dict[str, Any]:
    return {
        "id": m.id,
        "sender_id": m.sender_id,
        "title": m.title,
        "body": m.body,
        "category": m.category,
        "target_type": m.target_type,
        "target_tiers": m.target_tiers,
        "target_user_ids": m.target_user_ids,
        "channels": m.channels,
        "status": m.status,
        "pinned": m.pinned,
        "important": m.important,
        "is_automated": m.is_automated,
        "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else None,
        "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        "recipient_count": m.recipient_count,
        "created_at": m.created_at.isoformat(),
        "updated_at": m.updated_at.isoformat(),
    }


def message_inbox_item(m: models.Message, is_read: bool, read_at: datetime | None) -> dict[str, Any]:
    return {
        "id": m.id,
        "sender_id": m.sender_id,
        "title": m.title,
        "body": m.body,
        "category": m.category,
        "target_type": m.target_type,
        "pinned": m.pinned,
        "important": m.important,
        "is_automated": m.is_automated,
        "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        "created_at": m.created_at.isoformat(),
        "is_read": bool(is_read),
        "read_at": read_at.isoformat() if read_at else None,
    }


# ---------------------------------------------------------------------------
# 消息模板
# ---------------------------------------------------------------------------

def list_templates(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(select(models.MessageTemplate).order_by(models.MessageTemplate.created_at.desc())).all()
    return [template_to_dict(t) for t in rows]


def create_template(db: Session, *, name: str, title: str, body: str, category: str = "announcement", channel: str = "in_app") -> models.MessageTemplate:
    now = utc_now()
    t = models.MessageTemplate(
        id=new_id("tpl"),
        name=name,
        title=title,
        body=body,
        category=category,
        channel=channel,
        created_at=now,
        updated_at=now,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def update_template(db: Session, template_id: str, *, name: str | None = None, title: str | None = None, body: str | None = None, category: str | None = None, channel: str | None = None) -> models.MessageTemplate:
    t = db.get(models.MessageTemplate, template_id)
    if not t:
        raise KeyError(template_id)
    if name is not None:
        t.name = name
    if title is not None:
        t.title = title
    if body is not None:
        t.body = body
    if category is not None:
        t.category = category
    if channel is not None:
        t.channel = channel
    t.updated_at = utc_now()
    db.commit()
    db.refresh(t)
    return t


def delete_template(db: Session, template_id: str) -> None:
    t = db.get(models.MessageTemplate, template_id)
    if not t:
        raise KeyError(template_id)
    db.delete(t)
    db.commit()


def template_to_dict(t: models.MessageTemplate) -> dict[str, Any]:
    return {
        "id": t.id,
        "name": t.name,
        "title": t.title,
        "body": t.body,
        "category": t.category,
        "channel": t.channel,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }
