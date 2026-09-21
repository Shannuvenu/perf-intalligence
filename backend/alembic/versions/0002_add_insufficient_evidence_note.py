"""add insufficient_evidence_note to llm_recommendations

Revision ID: 0002_insufficient_evidence_note
Revises: 0001_initial_schema
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0002_insufficient_evidence_note"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "llm_recommendations",
        sa.Column("insufficient_evidence_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("llm_recommendations", "insufficient_evidence_note")