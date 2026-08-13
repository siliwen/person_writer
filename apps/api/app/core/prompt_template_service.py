"""提示词模板服务：超管后台可配置的系统提示词（如「优化提示词」）。

设计要点：
- 同一 purpose 下最多一个启用（is_active=1）模板，由应用层在 set-active 时保证。
- 后台未配置启用模板时，调用方应使用本模块的 DEFAULT_* 兜底常量，保证服务不中断。
- 模板仅存 system_prompt；user_prompt 由调用方现场拼装（用户原文等）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.constants import PURPOSE_OPTIMIZE_PROMPT


# 兜底提示词：与数据库模板结构一致，仅在后台未配置启用模板时使用。
DEFAULT_OPTIMIZE_PROMPT = """你是墨小小写作助手的「需求优化器」。用户会给你一句简短的写作想法，你需要把它扩展成一段清晰、完整、可直接用于文章生成的写作需求描述。

要求：
1. 保留用户原始意图和主题，不要跑题或篡改核心意思。
2. 补全写作要素：明确文体、建议字数、内容基调、必须包含的元素、必须避免的元素。
3. 若用户已写明文体或字数，沿用其设定；未写明则根据主题合理推测（默认散文、约1200字）。
4. 输出为中文，一段连贯的自然语言，不使用 Markdown 标题、列表符号或编号。
5. 不要解释你的工作过程，不要替用户写文章正文，只优化"要写什么"的需求。"""

DEFAULT_FREE_WRITE_PROMPT = """你是通用写作助手。请严格按用户要求的文体、主题和长度写作。
- 避免 AI 常见套话、空泛抒情和宏大口号。
- 使用自然段组织内容，保持可编辑性。
- 只输出正文，不要解释 prompt、不要列提纲。"""


class PromptTemplateError(Exception):
    """模板相关业务异常。"""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def list_prompt_templates(db: Session, *, purpose: str | None = None) -> list[models.PromptTemplate]:
    stmt = select(models.PromptTemplate)
    if purpose:
        stmt = stmt.where(models.PromptTemplate.purpose == purpose)
    return list(db.scalars(stmt.order_by(models.PromptTemplate.created_at.desc())).all())


def get_prompt_template(db: Session, template_id: str) -> models.PromptTemplate:
    template = db.get(models.PromptTemplate, template_id)
    if template is None:
        raise PromptTemplateError("提示词模板不存在。", status_code=404)
    return template


def create_prompt_template(
    db: Session,
    *,
    name: str,
    purpose: str,
    system_prompt: str,
    is_active: bool = True,
) -> models.PromptTemplate:
    template = models.PromptTemplate(
        id=models.new_id("pt"),
        name=name.strip(),
        purpose=purpose,
        system_prompt=system_prompt,
        is_active=bool(is_active),
    )
    # 启用模板需保证「同 purpose 下仅一个 active」：先停用其他（flush 持久化），
    # 再插入新启用行，避免 partial unique index 在同一事务内冲突。
    if template.is_active:
        _deactivate_others(db, purpose=purpose, except_id=None)
        db.flush()
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_prompt_template(
    db: Session,
    template_id: str,
    *,
    name: str | None = None,
    system_prompt: str | None = None,
    is_active: bool | None = None,
) -> models.PromptTemplate:
    template = get_prompt_template(db, template_id)
    if name is not None:
        template.name = name.strip()
    if system_prompt is not None:
        template.system_prompt = system_prompt
    if is_active is not None:
        new_active = bool(is_active)
        if new_active and not template.is_active:
            # 从非启用变为启用：先停用同 purpose 其他模板，再置自身为启用。
            _deactivate_others(db, purpose=template.purpose, except_id=template.id)
            db.flush()
        template.is_active = new_active
    template.updated_at = models.utc_now()
    db.commit()
    db.refresh(template)
    return template


def delete_prompt_template(db: Session, template_id: str) -> None:
    template = get_prompt_template(db, template_id)
    db.delete(template)
    db.commit()


def set_active_prompt_template(db: Session, template_id: str) -> models.PromptTemplate:
    """将指定模板设为启用，并停用同 purpose 下的其他模板。"""
    template = get_prompt_template(db, template_id)
    # 先停用其他（flush 持久化），再启用自身，避免 partial unique index 冲突。
    _deactivate_others(db, purpose=template.purpose, except_id=template.id)
    db.flush()
    template.is_active = True
    template.updated_at = models.utc_now()
    db.commit()
    db.refresh(template)
    return template


def get_active_prompt_template(db: Session, purpose: str) -> models.PromptTemplate | None:
    return db.scalar(
        select(models.PromptTemplate).where(
            models.PromptTemplate.purpose == purpose,
            models.PromptTemplate.is_active.is_(True),
        )
    )


def _deactivate_others(db: Session, *, purpose: str, except_id: str) -> None:
    others = db.scalars(
        select(models.PromptTemplate).where(
            models.PromptTemplate.purpose == purpose,
            models.PromptTemplate.id != except_id,
            models.PromptTemplate.is_active.is_(True),
        )
    ).all()
    for other in others:
        other.is_active = False
        other.updated_at = models.utc_now()


def to_dict(template: models.PromptTemplate) -> dict[str, Any]:
    return {
        "id": template.id,
        "name": template.name,
        "purpose": template.purpose,
        "system_prompt": template.system_prompt,
        "is_active": bool(template.is_active),
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


def ensure_default_optimize_template(db: Session) -> None:
    """初始化时确保存在一个启用的 optimize_prompt 模板（无则写入兜底内容）。"""
    existing = get_active_prompt_template(db, PURPOSE_OPTIMIZE_PROMPT)
    if existing is not None:
        return
    any_optimize = db.scalar(
        select(models.PromptTemplate).where(models.PromptTemplate.purpose == PURPOSE_OPTIMIZE_PROMPT)
    )
    if any_optimize is not None:
        # 有模板但未启用：启用最早的一条，避免重复创建。
        any_optimize.is_active = True
        any_optimize.updated_at = models.utc_now()
        db.commit()
        return
    create_prompt_template(
        db,
        name="优化提示词",
        purpose=PURPOSE_OPTIMIZE_PROMPT,
        system_prompt=DEFAULT_OPTIMIZE_PROMPT,
        is_active=True,
    )
