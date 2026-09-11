"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("site_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("base_url", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "urls",
        sa.Column("url_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.site_id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("url_category", sa.String(length=64), nullable=False, server_default="other"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_urls_site_id", "urls", ["site_id"])

    op.create_table(
        "psi_runs",
        sa.Column("run_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("url_id", sa.Integer(), sa.ForeignKey("urls.url_id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("strategy", sa.String(length=16), nullable=False, server_default="mobile"),
        sa.Column("raw_storage_key", sa.String(length=1024), nullable=True),
        sa.Column("category_scores", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("core_web_vitals", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("normalized_audits", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("run_status", sa.String(length=16), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_psi_runs_url_id", "psi_runs", ["url_id"])
    op.create_index("ix_psi_runs_run_timestamp", "psi_runs", ["run_timestamp"])

    op.create_table(
        "stabilized_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("url_id", sa.Integer(), sa.ForeignKey("urls.url_id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_count", sa.Integer(), nullable=False),
        sa.Column("median_metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("variability_metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stabilized_metrics_url_id", "stabilized_metrics", ["url_id"])

    op.create_table(
        "llm_recommendations",
        sa.Column("recommendation_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("url_id", sa.Integer(), sa.ForeignKey("urls.url_id", ondelete="CASCADE"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("root_cause_groups", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("priority_rank", sa.String(length=8), nullable=False, server_default="P3"),
        sa.Column("source_run_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("validation_status", sa.String(length=16), nullable=False, server_default="needs_review"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_llm_recommendations_url_id", "llm_recommendations", ["url_id"])
    op.create_index("ix_llm_recommendations_generated_at", "llm_recommendations", ["generated_at"])


def downgrade() -> None:
    op.drop_table("llm_recommendations")
    op.drop_table("stabilized_metrics")
    op.drop_table("psi_runs")
    op.drop_table("urls")
    op.drop_table("sites")
