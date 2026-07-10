"""SQLAlchemy 2.0 world-state models + basic CRUD.

Backend is SQLite in dev, Postgres in prod (Sprint 5), so schemas use only portable
types — `traits`/`tags` are generic `JSON` (no provider-specific column types),
valence/importance are plain integers. The higher-level domain helpers (record_turn_entities, top_facts,
active_characters) arrive with reflection/retrieval in S2.2/S2.3.
"""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    traits: Mapped[list[str]] = mapped_column(JSON, default=list)
    first_appeared_turn: Mapped[int] = mapped_column(Integer)
    last_seen_turn: Mapped[int] = mapped_column(Integer)


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    first_visited_turn: Mapped[int] = mapped_column(Integer)


class Relation(Base):
    __tablename__ = "relations"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    a_character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"))
    b_character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"))
    kind: Mapped[str] = mapped_column(String(64))
    valence: Mapped[int] = mapped_column(Integer, default=0)
    since_turn: Mapped[int] = mapped_column(Integer)


class StoryBeat(Base):
    __tablename__ = "story_beats"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(Text)
    turn: Mapped[int] = mapped_column(Integer)
    importance: Mapped[int] = mapped_column(Integer, default=1)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)


_Entity = TypeVar("_Entity", Character, Location, Relation, StoryBeat)


class WorldState:
    """Session-bound CRUD over the four world-state entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entity: _Entity) -> _Entity:
        self._session.add(entity)
        self._session.flush()  # assign the primary key without committing
        return entity

    def get(self, model: type[_Entity], entity_id: int) -> _Entity | None:
        return self._session.get(model, entity_id)

    def list(self, model: type[_Entity], session_id: str) -> list[_Entity]:
        stmt = select(model).where(model.session_id == session_id).order_by(model.id)
        return list(self._session.scalars(stmt))

    def delete(self, entity: _Entity) -> None:
        self._session.delete(entity)
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()

    def active_characters(self, session_id: str, min_last_seen_turn: int) -> list[Character]:
        """Characters seen at or after a turn threshold (most-recently-seen first)."""
        stmt = (
            select(Character)
            .where(
                Character.session_id == session_id,
                Character.last_seen_turn >= min_last_seen_turn,
            )
            .order_by(Character.last_seen_turn.desc(), Character.id)
        )
        return list(self._session.scalars(stmt))

    def top_beats(self, session_id: str, k: int = 3) -> list[StoryBeat]:
        """Highest-importance, most-recent story beats for the session."""
        stmt = (
            select(StoryBeat)
            .where(StoryBeat.session_id == session_id)
            .order_by(StoryBeat.importance.desc(), StoryBeat.turn.desc())
            .limit(k)
        )
        return list(self._session.scalars(stmt))
