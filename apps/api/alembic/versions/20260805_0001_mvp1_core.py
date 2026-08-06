"""mvp1 core writing workflow tables

Revision ID: 20260805_0001
Revises:
Create Date: 2026-08-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260805_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "materials",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("genre", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_filename", sa.String(length=255)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("paragraph_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_materials_user_id", "materials", ["user_id"])
    op.create_table(
        "material_paragraphs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("material_id", sa.String(length=64), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_material_paragraphs_material_id", "material_paragraphs", ["material_id"])
    op.create_table(
        "style_analysis_jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("material_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=48), nullable=False),
        sa.Column("draft_profile", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_style_analysis_jobs_user_id", "style_analysis_jobs", ["user_id"])
    op.create_table(
        "style_profiles",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_job_id", sa.String(length=64), sa.ForeignKey("style_analysis_jobs.id")),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_style_profiles_user_id", "style_profiles", ["user_id"])
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("style_profile_id", sa.String(length=64), sa.ForeignKey("style_profiles.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("genre", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])
    op.create_index("ix_documents_style_profile_id", "documents", ["style_profile_id"])
    op.create_table(
        "document_paragraphs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("document_id", sa.String(length=64), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("rewrite_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_document_paragraphs_document_id", "document_paragraphs", ["document_id"])
    op.create_table(
        "writing_tasks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("style_profile_id", sa.String(length=64), sa.ForeignKey("style_profiles.id")),
        sa.Column("document_id", sa.String(length=64), sa.ForeignKey("documents.id")),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("genre", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("effective_mode", sa.String(length=48), nullable=False),
        sa.Column("rag_enabled", sa.Boolean(), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("model_provider", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("input_token_count", sa.Integer(), nullable=False),
        sa.Column("output_token_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_writing_tasks_user_id", "writing_tasks", ["user_id"])
    op.create_index("ix_writing_tasks_style_profile_id", "writing_tasks", ["style_profile_id"])
    op.create_index("ix_writing_tasks_document_id", "writing_tasks", ["document_id"])
    op.create_table(
        "model_usage_logs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("model_provider", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("input_token_count", sa.Integer(), nullable=False),
        sa.Column("output_token_count", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_model_usage_logs_user_id", "model_usage_logs", ["user_id"])


def downgrade() -> None:
    op.drop_table("model_usage_logs")
    op.drop_table("writing_tasks")
    op.drop_table("document_paragraphs")
    op.drop_table("documents")
    op.drop_table("style_profiles")
    op.drop_table("style_analysis_jobs")
    op.drop_table("material_paragraphs")
    op.drop_table("materials")
    op.drop_table("users")
