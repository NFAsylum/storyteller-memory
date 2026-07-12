"""sessions and turns tables (Sprint 5 API)

Revision ID: 0002_sessions_turns
Revises: 0001_initial
Create Date: 2026-07-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_sessions_turns"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("last_turn", sa.Integer(), nullable=False),
    )
    op.create_table(
        "turns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("user_input", sa.Text(), nullable=False),
        sa.Column("narrator_text", sa.Text(), nullable=False),
        sa.Column("retrieved_context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_turns_session_id", "turns", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_turns_session_id", table_name="turns")
    op.drop_table("turns")
    op.drop_table("sessions")
