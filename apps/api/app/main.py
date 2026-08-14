from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.generation_policy import GenerationMode
from app.core.auth_service import (
    bind_email,
    bind_phone,
    change_password,
    clear_session_cookie,
    current_user_from_request,
    register_user,
    send_email_bind_code,
    send_phone_bind_code,
    set_session_cookie,
)
from app.core import points_service
from app.core.points_service import (
    ARTICLE_GENERATION,
    OPTIMIZE_PROMPT,
    PARAGRAPH_REWRITE,
    STYLE_ANALYSIS,
    charge,
    get_quota_view,
    list_usage,
    parse_target_length_chars,
    resolve_tier,
    validate_and_price,
)
from app.core.model_gateway import ModelGateway
from app.core.mvp_service import (
    DEMO_USER_ID,
    confirm_style_profile,
    create_free_writing,
    create_material,
    create_style_analysis_job,
    create_writing,
    delete_style_profile,
    generate_docx_bytes,
    get_style_analysis_job,
    get_user_document,
    list_materials,
    list_saved_documents,
    list_style_profiles,
    preview_rewrite_paragraph,
    revise_document,
    save_document,
    set_default_style_profile,
    update_style_profile,
    unsave_document,
    update_paragraph_content,
)
from app.core import message_service
from app.core import evaluation_service
from app.core.prompt_composer import WritingTaskInput, compose_prompt
from app.core import prompt_template_service
from app.core.prompt_template_service import DEFAULT_OPTIMIZE_PROMPT
from app.core.constants import SYSTEM_FREE_WRITE_STYLE_ID
from app.core.task_service import InMemoryWritingTaskService

# 自由写作去掉前端文体/字数选择后，用于积分预估的默认字数
DEFAULT_FREE_WRITE_TARGET_CHARS = 1200
from app.core.text_parser import extract_upload_text
from app.database import get_db, init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(
    title="Personal Writing Agent API",
    version="0.2.0",
    description="MVP1 API for demo-user style library writing workflow.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3002", "http://127.0.0.1:3002", "http://localhost:3220", "http://127.0.0.1:3220"],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}):(\d+)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
task_service = InMemoryWritingTaskService()

from app.admin_routes import router as admin_router

app.include_router(admin_router)


class WritingTaskPayload(BaseModel):
    genre: str = Field(..., examples=["散文", "故事", "小说", "剧本", "诗歌", "杂文", "随笔"])
    task_type: str = Field("新写", examples=["新写", "改写", "润色", "审校"])
    title: str
    brief: str
    target_length: str = "1200字"
    target_reader: str = "普通读者"
    must_include: str = ""
    must_avoid: str = ""
    eval_focus: str = ""
    style_intensity: str = Field("balanced", examples=["light", "balanced", "close"])

    def to_domain(self) -> WritingTaskInput:
        return WritingTaskInput(
            genre=self.genre,
            task_type=self.task_type,
            title=self.title,
            brief=self.brief,
            target_length=self.target_length,
            target_reader=self.target_reader,
            must_include=self.must_include,
            must_avoid=self.must_avoid,
            eval_focus=self.eval_focus,
            style_intensity=self.style_intensity,
        )


class ComposePromptRequest(BaseModel):
    writer_id: str = DEMO_USER_ID
    task: WritingTaskPayload
    style_profile: dict[str, Any]
    requested_mode: GenerationMode = GenerationMode.STYLE_PROMPT_ONLY
    rag_snippets: list[str] = Field(default_factory=list)


class CreateWritingTaskRequest(BaseModel):
    writer_id: str = DEMO_USER_ID
    style_profile_id: str | None = None
    style_profile: dict[str, Any] | None = None
    requested_mode: GenerationMode = GenerationMode.STYLE_PROMPT_ONLY
    rag_snippets: list[str] = Field(default_factory=list)
    task: WritingTaskPayload


class OptimizePromptRequest(BaseModel):
    prompt: str


class CreateStyleAnalysisJobRequest(BaseModel):
    material_ids: list[str]


class ConfirmStyleProfileRequest(BaseModel):
    job_id: str
    name: str
    profile: dict[str, Any] | None = None


class UpdateStyleProfileRequest(BaseModel):
    name: str
    description: str | None = None
    profile: dict[str, Any] | None = None
    is_recommended: bool | None = None


class RewriteParagraphRequest(BaseModel):
    instruction: str


class UpdateParagraphRequest(BaseModel):
    content: str


class ReviseDocumentRequest(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=4000)


class RegisterRequest(BaseModel):
    username: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class PhoneCodeRequest(BaseModel):
    phone_number: str


class BindPhoneRequest(BaseModel):
    phone_number: str
    code: str


class EmailCodeRequest(BaseModel):
    email: str


class BindEmailRequest(BaseModel):
    email: str
    code: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


class PasswordResetSendCodeRequest(BaseModel):
    phone_number: str


class PasswordResetConfirmRequest(BaseModel):
    phone_number: str
    code: str
    new_password: str


def require_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    return current_user_from_request(db, request)


def optional_current_user(request: Request, db: Session = Depends(get_db)) -> models.User | None:
    try:
        return current_user_from_request(db, request)
    except HTTPException:
        return None


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}



@app.get("/v1/model-status")
def model_status() -> dict[str, Any]:
    gateway = ModelGateway()
    return {
        "mode": gateway.mode,
        "has_api_key": bool(gateway.api_key),
        "base_url": gateway.base_url,
        "model_name": gateway.model_name,
        "timeout_seconds": gateway.timeout,
        "fallback_behavior": "disabled" if gateway.mode == "qwen" else "enabled_on_missing_key_or_call_failure",
    }

@app.post("/v1/auth/register")
def register(request: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = register_user(
        db,
        username=request.username,
        password=request.password,
        confirm_password=request.confirm_password,
    )
    set_session_cookie(response, user)
    return {"user": user_to_dict(user)}


@app.post("/v1/auth/login")
def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.core.auth_service import authenticate_user

    user = authenticate_user(db, username=request.username, password=request.password)
    set_session_cookie(response, user)
    return {"user": user_to_dict(user)}


@app.post("/v1/auth/logout")
def logout(response: Response) -> dict[str, str]:
    clear_session_cookie(response)
    return {"status": "ok"}


@app.get("/v1/me")
def current_user(user: models.User = Depends(require_current_user)) -> dict[str, Any]:
    return user_to_dict(user)


@app.post("/v1/account/phone/send-code")
def send_phone_code(
    request: PhoneCodeRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return send_phone_bind_code(db, user=user, phone_number=request.phone_number)


@app.post("/v1/account/phone/bind")
def bind_account_phone(
    request: BindPhoneRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    updated = bind_phone(db, user=user, phone_number=request.phone_number, code=request.code)
    return {"user": user_to_dict(updated)}


@app.post("/v1/account/email/send-code")
def send_email_code(
    request: EmailCodeRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return send_email_bind_code(db, user=user, email=request.email)


@app.post("/v1/account/email/bind")
def bind_account_email(
    request: BindEmailRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    updated = bind_email(db, user=user, email=request.email, code=request.code)
    return {"user": user_to_dict(updated)}


@app.post("/v1/account/password/change")
def change_account_password(
    request: ChangePasswordRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    updated = change_password(
        db,
        user=user,
        old_password=request.old_password,
        new_password=request.new_password,
        confirm_password=request.confirm_password,
    )
    return {"user": user_to_dict(updated)}


@app.get("/v1/account/quota")
def account_quota(
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return get_quota_view(db, user)


@app.get("/v1/account/usage")
def account_usage(
    page: int = 1,
    page_size: int = 20,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return list_usage(db, user, page=max(1, page), page_size=min(100, max(1, page_size)))


@app.post("/v1/auth/password-reset/send-code", status_code=501)
def password_reset_send_code(_: PasswordResetSendCodeRequest) -> dict[str, str]:
    return {"status": "not_implemented", "message": "Password reset by phone is reserved."}


@app.post("/v1/auth/password-reset/confirm", status_code=501)
def password_reset_confirm(_: PasswordResetConfirmRequest) -> dict[str, str]:
    return {"status": "not_implemented", "message": "Password reset by phone is reserved."}


@app.post("/v1/organizations/register-intent", status_code=501)
def organization_register_intent() -> dict[str, str]:
    return {"status": "not_implemented", "message": "Organization registration is reserved for MVP2."}


@app.post("/v1/materials/upload")
async def upload_materials(
    genre: str = Form("散文"),
    title: str = Form(""),
    files: list[UploadFile] = File(...),
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    created = []
    for file in files:
        data = await file.read()
        content = extract_upload_text(file.filename or "upload.txt", data)
        material = create_material(
            db,
            user_id=user.id,
            title=title if len(files) == 1 else "",
            genre=genre,
            source_type="upload",
            source_filename=file.filename,
            content=content,
        )
        created.append(material_to_dict(material, include_paragraphs=True))
    return {"user_id": user.id, "materials": created}


@app.get("/v1/materials")
def get_materials(
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"user_id": user.id, "materials": [material_to_dict(item) for item in list_materials(db, user_id=user.id)]}


@app.post("/v1/style-analysis-jobs")
def create_style_job(
    request: CreateStyleAnalysisJobRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    # 风格分析按固定积分扣费（当前为本地启发式，无模型调用，真实成本为 0）
    points = validate_and_price(db, user, STYLE_ANALYSIS)
    job = create_style_analysis_job(db, user_id=user.id, material_ids=request.material_ids)
    charge(db, user, STYLE_ANALYSIS, points)
    return style_job_to_dict(job)


@app.get("/v1/style-analysis-jobs/{job_id}")
def get_style_job(
    job_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return style_job_to_dict(get_style_analysis_job(db, user_id=user.id, job_id=job_id))


@app.post("/v1/style-profiles/confirm")
def confirm_style(
    request: ConfirmStyleProfileRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    style = confirm_style_profile(
        db,
        user_id=user.id,
        job_id=request.job_id,
        name=request.name,
        profile=request.profile,
    )
    return style_profile_to_dict(style)


@app.get("/v1/style-profiles")
def get_style_profiles(
    user: models.User | None = Depends(optional_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    items = list_style_profiles(db, user_id=user.id if user else None)
    return {
        "user_id": user.id if user else None,
        "styles": [style_profile_to_dict(item) for item in items],
    }


@app.delete("/v1/style-profiles/{style_profile_id}")
def delete_style(
    style_profile_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    style = delete_style_profile(db, user_id=user.id, style_profile_id=style_profile_id)
    return {"id": style.id, "user_id": style.user_id, "status": style.status}


@app.patch("/v1/style-profiles/{style_profile_id}")
def update_style(
    request: UpdateStyleProfileRequest,
    style_profile_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    style = update_style_profile(
        db,
        user_id=user.id,
        style_profile_id=style_profile_id,
        name=request.name,
        description=request.description,
        profile=request.profile,
        is_recommended=request.is_recommended,
        is_admin=user.is_admin,
    )
    return style_profile_to_dict(style)


@app.post("/v1/style-profiles/{style_profile_id}/set-default")
def set_default_style(
    style_profile_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    style = set_default_style_profile(db, user_id=user.id, style_profile_id=style_profile_id)
    return style_profile_to_dict(style)


@app.post("/v1/prompt/compose")
def compose_prompt_endpoint(request: ComposePromptRequest) -> dict[str, Any]:
    prompt = compose_prompt(
        task=request.task.to_domain(),
        style_profile=request.style_profile,
        requested_mode=request.requested_mode,
        rag_snippets=request.rag_snippets,
    )
    return {
        "mode": prompt.mode,
        "rag_enabled": prompt.rag_enabled,
        "prompt_version": prompt.prompt_version,
        "policy_reason": prompt.policy_reason,
        "messages": [
            {"role": "system", "content": prompt.system_prompt},
            {"role": "user", "content": prompt.user_prompt},
        ],
    }


@app.post("/v1/optimize-prompt")
def optimize_prompt(
    request: OptimizePromptRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """优化用户提示词：用后台可配置的 system prompt + 用户原文调用大模型，返回扩展后的需求文本。

    固定扣 1 积分；模型失败时回退返回原文，不阻断用户后续生成。
    """
    source = (request.prompt or "").strip()
    if not source:
        raise HTTPException(status_code=400, detail="请输入要优化的提示词。")
    points = validate_and_price(db, user, OPTIMIZE_PROMPT)
    template = prompt_template_service.get_active_prompt_template(db, "optimize_prompt")
    system_prompt = template.system_prompt if template else DEFAULT_OPTIMIZE_PROMPT
    model_result = ModelGateway().generate(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": source},
        ],
        purpose="optimize_prompt",
        fallback=source,
    )
    charge(
        db,
        user,
        OPTIMIZE_PROMPT,
        points,
        input_tokens=model_result.input_token_count,
        output_tokens=model_result.output_token_count,
        model_name=model_result.model_name,
    )
    return {"optimized_prompt": model_result.content}


@app.post("/v1/writing-tasks")
def create_writing_task(
    request: CreateWritingTaskRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if request.style_profile_id:
        target_chars = parse_target_length_chars(request.task.target_length)
        points = validate_and_price(db, user, ARTICLE_GENERATION, target_chars=target_chars)
        created = create_writing(
            db,
            user_id=user.id,
            style_profile_id=request.style_profile_id,
            task_input=request.task.to_domain(),
            requested_mode=request.requested_mode,
            rag_snippets=request.rag_snippets,
        )
        charge(
            db,
            user,
            ARTICLE_GENERATION,
            points,
            document_id=created.document.id,
            input_tokens=created.task.input_token_count,
            output_tokens=created.task.output_token_count,
            model_name=created.task.model_name,
        )
        body = writing_task_to_dict(created.task, document=created.document)
        auto = _run_auto_evaluation(db, user=user, task=created.task, document=created.document)
        if auto is not None:
            body["evaluation"] = auto
        return body

    if request.style_profile_id == "":
        # 自由写作（无风格生成）：不绑定用户风格档案，走通用写作要求。
        # 前端已去掉字数选择，传入 "按需求" 时按默认字数预估积分。
        parsed_chars = parse_target_length_chars(request.task.target_length)
        target_chars = parsed_chars or DEFAULT_FREE_WRITE_TARGET_CHARS
        points = validate_and_price(db, user, ARTICLE_GENERATION, target_chars=target_chars)
        created = create_free_writing(
            db,
            user_id=user.id,
            task_input=request.task.to_domain(),
            requested_mode=request.requested_mode,
            rag_snippets=request.rag_snippets,
        )
        charge(
            db,
            user,
            ARTICLE_GENERATION,
            points,
            document_id=created.document.id,
            input_tokens=created.task.input_token_count,
            output_tokens=created.task.output_token_count,
            model_name=created.task.model_name,
        )
        # 自由写作暂不鉴评
        return writing_task_to_dict(created.task, document=created.document)

    if request.style_profile:
        created_legacy = task_service.create_task(
            writer_id=request.writer_id,
            task=request.task.to_domain(),
            style_profile=request.style_profile,
            requested_mode=request.requested_mode,
            rag_snippets=request.rag_snippets,
        )
        return {
            "task_id": created_legacy.task_id,
            "writer_id": created_legacy.writer_id,
            "status": created_legacy.status,
            "effective_mode": created_legacy.effective_mode,
            "rag_enabled": created_legacy.rag_enabled,
            "prompt_version": created_legacy.prompt_version,
            "policy_reason": created_legacy.policy_reason,
            "created_at": created_legacy.created_at,
        }

    raise HTTPException(status_code=400, detail="style_profile_id is required")


@app.get("/v1/writing-tasks/{task_id}")
def get_writing_task(
    task_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = db.get(models.WritingTask, task_id)
    if task:
        if task.user_id != user.id:
            raise HTTPException(status_code=404, detail="writing task not found")
        document = db.get(models.Document, task.document_id) if task.document_id else None
        return writing_task_to_dict(task, document=document)

    legacy = task_service.get_task(task_id)
    if legacy is None:
        raise HTTPException(status_code=404, detail="writing task not found")
    return {
        "task_id": legacy.task_id,
        "writer_id": legacy.writer_id,
        "status": legacy.status,
        "effective_mode": legacy.effective_mode,
        "rag_enabled": legacy.rag_enabled,
        "prompt_version": legacy.prompt_version,
        "policy_reason": legacy.policy_reason,
        "created_at": legacy.created_at,
    }


# ---------------------------------------------------------------------------
# 文章鉴评（首版仅散文）
# ---------------------------------------------------------------------------

def _run_auto_evaluation(
    db: Session,
    *,
    user: models.User,
    task: models.WritingTask,
    document: models.Document,
) -> dict[str, Any] | None:
    """散文生成完成后自动鉴评并推送系统通知。失败不影响主流程。"""
    # 自由写作（无风格生成）暂不鉴评：无风格基准，鉴评量规无法判定风格契合。
    if task.style_profile_id == SYSTEM_FREE_WRITE_STYLE_ID:
        return None
    if not evaluation_service.is_supported_genre(document.genre):
        return None
    try:
        style = db.get(models.StyleProfile, task.style_profile_id) if task.style_profile_id else None
        evaluation = evaluation_service.evaluate_document(
            db,
            user_id=user.id,
            document=document,
            style=style,
            writing_task=task,
            trigger="auto",
        )
        message_service.create_system_message(
            db,
            user.id,
            title="文章鉴评已生成",
            body=(
                f"《{document.title}》鉴评完成：{evaluation.grade} 级"
                f"（{evaluation.overall_score:.1f} 分）。"
                "打开文章可查看逐维点评与修改建议。AI 鉴评仅供参考。"
            ),
        )
        return evaluation_service.evaluation_summary(evaluation)
    except Exception:  # noqa: BLE001 - 鉴评是增值能力，不能拖垮生成主流程
        db.rollback()
        return None


def _owned_writing_task(db: Session, task_id: str, user: models.User) -> models.WritingTask:
    task = db.get(models.WritingTask, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="writing task not found")
    return task


@app.post("/v1/writing-tasks/{task_id}/evaluate")
def evaluate_writing_task(
    task_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = _owned_writing_task(db, task_id, user)
    document = db.get(models.Document, task.document_id) if task.document_id else None
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    if document.style_profile_id == SYSTEM_FREE_WRITE_STYLE_ID:
        raise HTTPException(
            status_code=422,
            detail="自由写作文章暂不支持鉴评（无风格基准）。",
        )
    if not evaluation_service.is_supported_genre(document.genre):
        raise HTTPException(
            status_code=422,
            detail=f"当前仅支持散文鉴评，该文章文体为「{document.genre}」，其他文体的评分量规仍在打磨中。",
        )
    style = db.get(models.StyleProfile, task.style_profile_id) if task.style_profile_id else None
    evaluation = evaluation_service.evaluate_document(
        db,
        user_id=user.id,
        document=document,
        style=style,
        writing_task=task,
        trigger="manual",
    )
    return evaluation_service.evaluation_to_dict(evaluation)


@app.get("/v1/writing-tasks/{task_id}/evaluation")
def get_writing_task_evaluation(
    task_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = _owned_writing_task(db, task_id, user)
    evaluation = evaluation_service.latest_evaluation(db, user_id=user.id, writing_task_id=task.id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    return evaluation_service.evaluation_to_dict(evaluation)


@app.get("/v1/documents/{document_id}/evaluation")
def get_document_evaluation(
    document_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    document = db.get(models.Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="document not found")
    evaluation = evaluation_service.latest_evaluation(db, user_id=user.id, document_id=document.id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    return evaluation_service.evaluation_to_dict(evaluation)


@app.post("/v1/documents/{document_id}/evaluate")
def evaluate_document_endpoint(
    document_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    document = db.get(models.Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="document not found")
    if not evaluation_service.is_supported_genre(document.genre):
        raise HTTPException(
            status_code=422,
            detail=f"当前仅支持散文鉴评，该文章文体为「{document.genre}」，其他文体的评分量规仍在打磨中。",
        )
    task = db.scalar(
        select(models.WritingTask)
        .where(models.WritingTask.document_id == document.id, models.WritingTask.user_id == user.id)
        .order_by(models.WritingTask.created_at.desc())
    )
    style = db.get(models.StyleProfile, document.style_profile_id) if document.style_profile_id else None
    evaluation = evaluation_service.evaluate_document(
        db,
        user_id=user.id,
        document=document,
        style=style,
        writing_task=task,
        trigger="manual",
    )
    return evaluation_service.evaluation_to_dict(evaluation)


@app.post("/v1/documents/{document_id}/paragraphs/{paragraph_id}/rewrite")
def rewrite_document_paragraph(
    document_id: str,
    paragraph_id: str,
    request: RewriteParagraphRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tier = resolve_tier(db, user)
    if tier and not tier.can_rewrite:
        raise HTTPException(status_code=403, detail="当前等级不支持段落重写，请升级会员。")
    points = validate_and_price(db, user, PARAGRAPH_REWRITE)
    result = preview_rewrite_paragraph(
        db,
        user_id=user.id,
        document_id=document_id,
        paragraph_id=paragraph_id,
        instruction=request.instruction,
    )
    charge(
        db,
        user,
        PARAGRAPH_REWRITE,
        points,
        document_id=document_id,
        input_tokens=result["input_token_count"],
        output_tokens=result["output_token_count"],
        model_name=result["model_name"],
    )
    return {"rewritten_content": result["content"]}


@app.put("/v1/documents/{document_id}/paragraphs/{paragraph_id}")
def update_paragraph(
    document_id: str,
    paragraph_id: str,
    request: UpdateParagraphRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    document = update_paragraph_content(
        db,
        user_id=user.id,
        document_id=document_id,
        paragraph_id=paragraph_id,
        content=request.content,
    )
    return document_to_dict(document)


@app.post("/v1/documents/{document_id}/revise")
def revise_document_endpoint(
    document_id: str,
    request: ReviseDocumentRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """无风格自由写作文章的「继续修改」：按用户修改意见重生成并覆盖当前文档。

    积分按原文 target_length 预估（与生成新文章一致）；不鉴评。
    """
    document = get_user_document(db, user_id=user.id, document_id=document_id)
    task = db.scalar(
        select(models.WritingTask)
        .where(models.WritingTask.document_id == document.id, models.WritingTask.user_id == user.id)
        .order_by(models.WritingTask.created_at.desc())
    )
    target_length = (task.requirements.get("target_length") if task else None) or f"约{len(document.content)}字"
    parsed_chars = parse_target_length_chars(target_length)
    target_chars = parsed_chars or (
        DEFAULT_FREE_WRITE_TARGET_CHARS if document.style_profile_id == SYSTEM_FREE_WRITE_STYLE_ID else max(len(document.content), 600)
    )
    points = validate_and_price(db, user, ARTICLE_GENERATION, target_chars=target_chars)
    updated, model_result = revise_document(
        db, user_id=user.id, document_id=document_id, instruction=request.instruction.strip()
    )
    charge(
        db,
        user,
        ARTICLE_GENERATION,
        points,
        document_id=updated.id,
        input_tokens=model_result.input_token_count,
        output_tokens=model_result.output_token_count,
        model_name=model_result.model_name,
    )
    return document_to_dict(updated)


@app.get("/v1/documents/saved")
def get_saved_documents(
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    documents = list_saved_documents(db, user_id=user.id)
    return {"user_id": user.id, "documents": [document_to_dict(item) for item in documents]}


@app.get("/v1/documents/{document_id}")
def get_document(
    document_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    document = get_user_document(db, user_id=user.id, document_id=document_id)
    return document_to_dict(document)


@app.post("/v1/documents/{document_id}/save")
def save_document_endpoint(
    document_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    document = save_document(db, user_id=user.id, document_id=document_id)
    return document_to_dict(document)


@app.post("/v1/documents/{document_id}/unsave")
def unsave_document_endpoint(
    document_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    document = unsave_document(db, user_id=user.id, document_id=document_id)
    return document_to_dict(document)


@app.get("/v1/documents/{document_id}/download/docx")
def download_document_docx(
    document_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    tier = resolve_tier(db, user)
    if tier and not tier.can_download:
        raise HTTPException(status_code=403, detail="当前等级不支持下载，请升级会员。")
    document = get_user_document(db, user_id=user.id, document_id=document_id)
    data = generate_docx_bytes(document)
    filename = f"{document.title}.docx".replace(" ", "_").replace("/", "_")
    encoded_filename = quote(filename, safe="")
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )


# ---------------------------------------------------------------------------
# 消息中心（用户侧）
# ---------------------------------------------------------------------------

@app.get("/v1/messages")
def list_my_messages(
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return message_service.list_user_inbox(
        db, user.id, unread_only=unread_only, page=max(1, page), page_size=min(100, max(1, page_size))
    )


@app.get("/v1/messages/unread-count")
def my_unread_count(
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"unread_count": message_service.get_unread_count(db, user.id)}


@app.post("/v1/messages/{message_id}/read")
def read_message(
    message_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    marked = message_service.mark_read(db, message_id, user.id)
    return {"status": "ok", "marked": marked}


@app.post("/v1/messages/read-all")
def read_all_messages(
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    marked = message_service.mark_all_read(db, user.id)
    return {"status": "ok", "marked": marked}


def user_to_dict(user: models.User) -> dict[str, Any]:
    return {
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "mode": user.mode,
        "tier_code": user.tier_id,
        "points_balance": user.points_balance,
        "is_admin": bool(user.is_admin),
        "phone_number": user.phone_number,
        "phone_verified": user.phone_verified_at is not None,
        "email": user.email,
        "email_verified": user.email_verified_at is not None,
        "created_at": user.created_at.isoformat(),
    }


def material_to_dict(material: models.Material, *, include_paragraphs: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": material.id,
        "title": material.title,
        "genre": material.genre,
        "source_filename": material.source_filename,
        "char_count": material.char_count,
        "paragraph_count": material.paragraph_count,
        "created_at": material.created_at.isoformat(),
    }
    if include_paragraphs:
        body["paragraphs"] = [
            {"id": item.id, "position": item.position, "content": item.content, "char_count": item.char_count}
            for item in material.paragraphs
        ]
    return body


def style_job_to_dict(job: models.StyleAnalysisJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "user_id": job.user_id,
        "material_ids": job.material_ids,
        "status": job.status,
        "draft_profile": job.draft_profile,
        "created_at": job.created_at.isoformat(),
    }


def style_profile_to_dict(style: models.StyleProfile) -> dict[str, Any]:
    return {
        "id": style.id,
        "user_id": style.user_id,
        "name": style.name,
        "description": style.description,
        "status": style.status,
        "profile": style.profile,
        "is_default": style.is_default,
        "is_recommended": style.is_recommended,
        "created_at": style.created_at.isoformat(),
    }


def writing_task_to_dict(task: models.WritingTask, *, document: models.Document | None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "task_id": task.id,
        "writer_id": task.user_id,
        "status": task.status,
        "style_profile_id": task.style_profile_id,
        "document_id": task.document_id,
        "effective_mode": task.effective_mode,
        "rag_enabled": task.rag_enabled,
        "prompt_version": task.prompt_version,
        "model_provider": task.model_provider,
        "model_name": task.model_name,
        "input_token_count": task.input_token_count,
        "output_token_count": task.output_token_count,
        "created_at": task.created_at.isoformat(),
    }
    if document:
        body["document"] = document_to_dict(document)
    return body


def document_to_dict(document: models.Document) -> dict[str, Any]:
    paragraphs = sorted(document.paragraphs, key=lambda item: item.position)
    return {
        "id": document.id,
        "title": document.title,
        "genre": document.genre,
        "style_profile_id": document.style_profile_id,
        "status": document.status,
        "is_saved": document.is_saved,
        "saved_at": document.saved_at.isoformat() if document.saved_at else None,
        "content": document.content,
        "paragraphs": [
            {
                "id": item.id,
                "position": item.position,
                "content": item.content,
                "rewrite_count": item.rewrite_count,
            }
            for item in paragraphs
        ],
        "updated_at": document.updated_at.isoformat(),
    }



