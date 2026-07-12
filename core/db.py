"""Database engine/session helpers. SQLite in dev, Postgres in prod (Sprint 5)."""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./storyteller.db"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_database_url())


def get_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False so returned ORM objects stay usable after commit.
    return sessionmaker(engine, expire_on_commit=False)
