from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    username_normalized: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="demo")
    phone_number: Mapped[str | None] = mapped_column(String(11), unique=True, index=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 会员等级与积分（配置驱动，等级定义见 membership_tiers 表，不写死在代码里）
    tier_id: Mapped[str | None] = mapped_column(ForeignKey("membership_tiers.code"), index=True, nullable=True)
    points_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quota_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quota_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PhoneVerificationCode(Base):
    __tablename__ = "phone_verification_codes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(11), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    genre: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paragraph_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    paragraphs: Mapped[list[MaterialParagraph]] = relationship(
        back_populates="material", cascade="all, delete-orphan", order_by="MaterialParagraph.position"
    )


class MaterialParagraph(Base):
    __tablename__ = "material_paragraphs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"), index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    material: Mapped[Material] = relationship(back_populates="paragraphs")


class StyleAnalysisJob(Base):
    __tablename__ = "style_analysis_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    material_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    draft_profile: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class StyleProfile(Base):
    __tablename__ = "style_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    source_job_id: Mapped[str | None] = mapped_column(ForeignKey("style_analysis_jobs.id"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    profile: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    style_profile_id: Mapped[str] = mapped_column(ForeignKey("style_profiles.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    genre: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    is_saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    paragraphs: Mapped[list[DocumentParagraph]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentParagraph.position"
    )


class DocumentParagraph(Base):
    __tablename__ = "document_paragraphs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rewrite_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[Document] = relationship(back_populates="paragraphs")


class WritingTask(Base):
    __tablename__ = "writing_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    style_profile_id: Mapped[str | None] = mapped_column(ForeignKey("style_profiles.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    genre: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    effective_mode: Mapped[str] = mapped_column(String(48), nullable=False)
    rag_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    # 原始写作要求快照（target_length / must_include / must_avoid 等），鉴评的「指令遵循」维度据此判定
    requirements: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False, default="mock")
    model_name: Mapped[str] = mapped_column(String(120), nullable=False, default="mock-writer")
    input_token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ModelUsageLog(Base):
    __tablename__ = "model_usage_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    input_token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class MembershipTier(Base):
    """会员等级配置表——所有等级与权益均入库，代码只读取不写死。"""

    __tablename__ = "membership_tiers"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)  # free / basic / pro / team
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    monthly_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_monthly: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 月费，单位：分
    style_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    material_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    can_download: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_rewrite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_article_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0 = 不限
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ArticleLengthBracket(Base):
    """文章长度档位→积分映射表（长文折扣，非严格线性）。"""

    __tablename__ = "article_length_brackets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    min_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_length: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = 无上限
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class OperationCost(Base):
    """固定操作积分表（风格分析、段落重写等不随长度变化的操作）。"""

    __tablename__ = "operation_costs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    op_type: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ModelPricing(Base):
    """模型单价表——内部真实成本核算用（¥/百万 tokens），不写死。"""

    __tablename__ = "model_pricing"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    input_price_per_m: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    output_price_per_m: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(String(255))


class UsageRecord(Base):
    """积分消耗流水——管理后台查每个会员的积分消耗用。"""

    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    op_type: Mapped[str] = mapped_column(String(48), nullable=False)
    points_consumed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    document_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_cny: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AdminAuditLog(Base):
    """管理后台操作审计日志——所有写操作自动留痕，只追加、不可改删。"""

    __tablename__ = "admin_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    actor_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)  # create/update/delete/adjust/set_tier/ban...
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)  # tier/user/bracket/opcost/price/...
    target_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ArticleEvaluation(Base):
    """文章鉴评报告——对生成结果按文体量规 + 用户风格档案打分点评。

    report 为结构化 JSON：overall / dimensions / suggestions / style_deviations /
    ai_tell_flags / features / disclaimer。同一篇文章可多次鉴评，取最新一条展示。
    """

    __tablename__ = "article_evaluations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True, nullable=False)
    writing_task_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    genre: Mapped[str] = mapped_column(String(32), nullable=False)
    # 同一篇文章的第几次鉴评（从 1 起）。created_at 精度到秒，同秒多次鉴评靠它稳定排序。
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    overall_score: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, default=0)
    grade: Mapped[str] = mapped_column(String(8), nullable=False, default="C")
    report: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")  # auto/manual
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False, default="mock")
    model_name: Mapped[str] = mapped_column(String(120), nullable=False, default="mock-evaluate")
    input_token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Message(Base):
    """站内信（管理员手动撰写或系统自动触发）。接收范围由 target_type 决定。"""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="announcement")  # system/announcement/direct
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, default="all")  # all/tier/specific
    target_tiers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    target_user_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    channels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)  # ["in_app"] 预留 email
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="sent")  # draft/sent/scheduled/recalled
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    important: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_automated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class MessageDelivery(Base):
    """每条消息的实际送达记录，用于未读计数与已读率。"""

    __tablename__ = "message_deliveries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class MessageTemplate(Base):
    """消息模板（运营复用）。"""

    __tablename__ = "message_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="announcement")
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="in_app")  # 预留
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PromptTemplate(Base):
    """可后台配置的系统提示词模板（如「优化提示词」）。

    purpose 为业务唯一用途标识；同一 purpose 下至多一个 is_active=1 的模板
    （由 prompt_template_service 在 set-active 时保证）。迁移 PostgreSQL 时，
    Boolean / Text / partial unique index 语义一致，无需 schema 改造。
    """

    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# 同一 purpose 下仅允许一个启用模板（partial unique index，SQLite/PG 均支持）。
Index(
    "ux_prompt_templates_purpose_active",
    PromptTemplate.purpose,
    unique=True,
    sqlite_where=(PromptTemplate.is_active == True),  # type: ignore[arg-type]
    postgresql_where=(PromptTemplate.is_active == True),  # type: ignore[arg-type]
)


class UserConsent(Base):
    """用户协议 / 隐私政策同意记录——注册时强校验并留痕，作为已告知用户的证据。

    agreement_type 取值：terms（用户协议）/ privacy（隐私政策）。
    每次注册写入两条（各一份）；协议重大更新后用户重新确认时再追加记录，可追溯版本。
    """

    __tablename__ = "user_consents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    agreement_type: Mapped[str] = mapped_column(String(32), nullable=False)  # terms / privacy
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1.0")
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


Index("ix_user_consents_user_agreement", UserConsent.user_id, UserConsent.agreement_type)

