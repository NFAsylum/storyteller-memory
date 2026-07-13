"""session.config column (narrative controls — T2.1)

Revision ID: 0003_session_config
Revises: 0002_sessions_turns
Create Date: 2026-07-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_session_config"
down_revision = "0002_sessions_turns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("sessions", "config")
