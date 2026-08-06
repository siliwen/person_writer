from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.core.generation_policy import GenerationMode
from app.core.auth_service import (
    bind_phone,
    clear_session_cookie,
    current_user_from_request,
    register_user,
    send_phone_bind_code,
    set_session_cookie,
)
from app.core.model_gateway import ModelGateway
from app.core.mvp_service import (
    DEMO_USER_ID,
    confirm_style_profile,
    create_material,
    create_style_analysis_job,
    create_writing,
    delete_style_profile,
    get_style_analysis_job,
    list_materials,
    list_style_profiles,
    rewrite_paragraph,
)
from app.core.prompt_composer import WritingTaskInput, compose_prompt
from app.core.task_service import InMemoryWritingTaskService
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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3002", "http://127.0.0.1:3002"],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}):(3000|3002)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
task_service = InMemoryWritingTaskService()


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


class CreateStyleAnalysisJobRequest(BaseModel):
    material_ids: list[str]


class ConfirmStyleProfileRequest(BaseModel):
    job_id: str
    name: str
    profile: dict[str, Any] | None = None


class RewriteParagraphRequest(BaseModel):
    instruction: str


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


class PasswordResetSendCodeRequest(BaseModel):
    phone_number: str


class PasswordResetConfirmRequest(BaseModel):
    phone_number: str
    code: str
    new_password: str


def require_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    return current_user_from_request(db, request)


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
    job = create_style_analysis_job(db, user_id=user.id, material_ids=request.material_ids)
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
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"user_id": user.id, "styles": [style_profile_to_dict(item) for item in list_style_profiles(db, user_id=user.id)]}


@app.delete("/v1/style-profiles/{style_profile_id}")
def delete_style(
    style_profile_id: str,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    style = delete_style_profile(db, user_id=user.id, style_profile_id=style_profile_id)
    return {"id": style.id, "user_id": style.user_id, "status": style.status}


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


@app.post("/v1/writing-tasks")
def create_writing_task(
    request: CreateWritingTaskRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if request.style_profile_id:
        created = create_writing(
            db,
            user_id=user.id,
            style_profile_id=request.style_profile_id,
            task_input=request.task.to_domain(),
            requested_mode=request.requested_mode,
            rag_snippets=request.rag_snippets,
        )
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


@app.post("/v1/documents/{document_id}/paragraphs/{paragraph_id}/rewrite")
def rewrite_document_paragraph(
    document_id: str,
    paragraph_id: str,
    request: RewriteParagraphRequest,
    user: models.User = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    document = rewrite_paragraph(
        db,
        user_id=user.id,
        document_id=document_id,
        paragraph_id=paragraph_id,
        instruction=request.instruction,
    )
    db.refresh(document, attribute_names=["paragraphs"])
    return document_to_dict(document)


def user_to_dict(user: models.User) -> dict[str, Any]:
    return {
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "mode": user.mode,
        "phone_number": user.phone_number,
        "phone_verified": user.phone_verified_at is not None,
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
        "status": style.status,
        "profile": style.profile,
        "is_default": style.is_default,
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



