"""initial world_state schema: characters, locations, relations, story_beats

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        # Portable JSON list so SQLite -> Postgres migrates cleanly (no provider-specific types).
        sa.Column("traits", sa.JSON(), nullable=False),
        sa.Column("first_appeared_turn", sa.Integer(), nullable=False),
        sa.Column("last_seen_turn", sa.Integer(), nullable=False),
    )
    op.create_index("ix_characters_session_id", "characters", ["session_id"])

    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("first_visited_turn", sa.Integer(), nullable=False),
    )
    op.create_index("ix_locations_session_id", "locations", ["session_id"])

    op.create_table(
        "relations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("a_character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("b_character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("valence", sa.Integer(), nullable=False),
        sa.Column("since_turn", sa.Integer(), nullable=False),
    )
    op.create_index("ix_relations_session_id", "relations", ["session_id"])

    op.create_table(
        "story_beats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
    )
    op.create_index("ix_story_beats_session_id", "story_beats", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_story_beats_session_id", table_name="story_beats")
    op.drop_table("story_beats")
    op.drop_index("ix_relations_session_id", table_name="relations")
    op.drop_table("relations")
    op.drop_index("ix_locations_session_id", table_name="locations")
    op.drop_table("locations")
    op.drop_index("ix_characters_session_id", table_name="characters")
    op.drop_table("characters")
