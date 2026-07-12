"""FastAPI backend for the Storyteller UI. Reuses story_loop / mem0 / world_state / reflection.

Endpoints (Sprint 5):
  GET    /sessions                              list sessions
  POST   /sessions                              create a session
  GET    /sessions/{id}                         session + turns + memory state
  DELETE /sessions/{id}                         delete session (turns, mem0, world_state)
  POST   /sessions/{id}/turn                    run a story turn
  GET    /sessions/{id}/turns/{turn_id}/context context bundle used that turn
  POST   /sessions/{id}/reflect                 force reflection
  POST   /sessions/{id}/compare-turn            re-run last user turn no_memory vs mem0_only
  GET    /sessions/{id}/state                   world_state (chars/locs/rels/beats)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import delete, select

from api.deps import Backend, get_backend
from core.memory.reflection import LlmReflection
from core.memory.retrieval_policy import RetrievalPolicy
from core.memory.world_state import (
    Character,
    Location,
    Relation,
    Session,
    StoryBeat,
    Turn,
    WorldState,
)
from core.story_loop import StoryLoop, load_prompt_template, render_prompt

app = FastAPI(title="Storyteller API")

# Dev default localhost:3000; override in prod via CORS_ORIGINS (comma-separated).
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CreateSession(BaseModel):
    name: str
    brief: str = ""


class TurnInput(BaseModel):
    text: str


def _get_session(db, session_id: str) -> Session:
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"session {session_id!r} not found")
    return session


def _memory_state(world: WorldState, session_id: str) -> dict[str, Any]:
    return {
        "characters": [
            {"name": c.name, "traits": c.traits, "first_appeared_turn": c.first_appeared_turn,
             "last_seen_turn": c.last_seen_turn}
            for c in world.list(Character, session_id)
        ],
        "locations": [
            {"name": loc.name, "description": loc.description, "first_visited_turn": loc.first_visited_turn}
            for loc in world.list(Location, session_id)
        ],
        "relations": [
            {"a_character_id": r.a_character_id, "b_character_id": r.b_character_id,
             "kind": r.kind, "valence": r.valence, "since_turn": r.since_turn}
            for r in world.list(Relation, session_id)
        ],
        "story_beats": [
            {"summary": b.summary, "turn": b.turn, "importance": b.importance, "tags": b.tags}
            for b in world.list(StoryBeat, session_id)
        ],
    }


@app.get("/sessions")
def list_sessions(backend: Backend = Depends(get_backend)) -> list[dict[str, Any]]:
    with backend.session_factory() as db:
        rows = db.scalars(select(Session).order_by(Session.created_at.desc())).all()
        return [
            {"id": s.id, "name": s.name, "last_turn": s.last_turn, "created_at": s.created_at}
            for s in rows
        ]


@app.post("/sessions", status_code=201)
def create_session(body: CreateSession, backend: Backend = Depends(get_backend)) -> dict[str, Any]:
    session_id = uuid.uuid4().hex[:16]
    with backend.session_factory() as db:
        db.add(Session(id=session_id, name=body.name, brief=body.brief, created_at=_now(), last_turn=0))
        db.commit()
    return {"id": session_id, "name": body.name, "last_turn": 0}


@app.get("/sessions/{session_id}")
def get_session(session_id: str, backend: Backend = Depends(get_backend)) -> dict[str, Any]:
    with backend.session_factory() as db:
        session = _get_session(db, session_id)
        turns = db.scalars(
            select(Turn).where(Turn.session_id == session_id).order_by(Turn.turn_number)
        ).all()
        state = _memory_state(WorldState(db), session_id)
        return {
            "id": session.id,
            "name": session.name,
            "brief": session.brief,
            "last_turn": session.last_turn,
            "turns": [
                {"turn_number": t.turn_number, "user_input": t.user_input,
                 "narrator_text": t.narrator_text, "created_at": t.created_at}
                for t in turns
            ],
            "memory_state": state,
        }


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, backend: Backend = Depends(get_backend)) -> Response:
    with backend.session_factory() as db:
        _get_session(db, session_id)
        for model in (Turn, StoryBeat, Relation, Location, Character):
            db.execute(delete(model).where(model.session_id == session_id))
        db.execute(delete(Session).where(Session.id == session_id))
        # Clear the vector store BEFORE committing the DB delete (F1.4): if mem0 fails,
        # roll back so we never leave a "deleted" session with orphaned vectors.
        try:
            backend.memory_for(session_id).clear()
        except Exception as exc:  # noqa: BLE001 - surface any mem0 failure as a clean 500
            db.rollback()
            raise HTTPException(status_code=500, detail=f"failed to clear memory: {exc}") from exc
        db.commit()
    return Response(status_code=204)


@app.post("/sessions/{session_id}/turn")
def run_turn(session_id: str, body: TurnInput, backend: Backend = Depends(get_backend)) -> dict[str, Any]:
    with backend.session_factory() as db:
        session = _get_session(db, session_id)
        memory = backend.memory_for(session_id)
        world = WorldState(db)
        loop = StoryLoop(
            session_id,
            memory=memory,
            llm=backend.llm,
            retrieval_policy=RetrievalPolicy(memory, world),
            reflection=LlmReflection(backend.llm, world, memory),
            start_turn=session.last_turn,
        )
        result = loop.run_turn(body.text)
        turn_number = result.retrieved_context.get("turn", session.last_turn + 1)
        db.add(
            Turn(
                session_id=session_id,
                turn_number=turn_number,
                user_input=body.text,
                narrator_text=result.narrator_text,
                retrieved_context=result.retrieved_context,
                created_at=_now(),
            )
        )
        session.last_turn = turn_number
        db.commit()
        return {
            "turn_number": turn_number,
            "narrator_text": result.narrator_text,
            "retrieved_context": result.retrieved_context,
            "cost_usd": result.cost_usd,
        }


@app.get("/sessions/{session_id}/turns/{turn_number}/context")
def turn_context(session_id: str, turn_number: int, backend: Backend = Depends(get_backend)) -> dict[str, Any]:
    with backend.session_factory() as db:
        turn = db.scalars(
            select(Turn).where(Turn.session_id == session_id, Turn.turn_number == turn_number)
        ).first()
        if turn is None:
            raise HTTPException(status_code=404, detail="turn not found")
        return turn.retrieved_context


@app.post("/sessions/{session_id}/reflect")
def reflect(session_id: str, backend: Backend = Depends(get_backend)) -> dict[str, Any]:
    with backend.session_factory() as db:
        _get_session(db, session_id)
        memory = backend.memory_for(session_id)
        result = LlmReflection(backend.llm, WorldState(db), memory).consolidate(session_id, since_turn=0)
        db.commit()
        return {
            "beats_created": result.beats_created,
            "characters_updated": result.characters_updated,
            "relations_updated": result.relations_updated,
            "cost_usd": result.cost_usd,
        }


@app.post("/sessions/{session_id}/compare-turn")
def compare_turn(session_id: str, backend: Backend = Depends(get_backend)) -> dict[str, Any]:
    with backend.session_factory() as db:
        _get_session(db, session_id)
        last = db.scalars(
            select(Turn).where(Turn.session_id == session_id).order_by(Turn.turn_number.desc())
        ).first()
        if last is None:
            raise HTTPException(status_code=400, detail="no turn to compare yet")
        user_input = last.user_input
        memory = backend.memory_for(session_id)
        world = WorldState(db)
        template = load_prompt_template()

        # no_memory: no context at all
        no_mem_text = backend.llm.generate(
            system=render_prompt(template, None, user_input),
            messages=[{"role": "user", "content": user_input}],
        ).content

        # mem0_only: real retrieved context (not persisted)
        bundle = RetrievalPolicy(memory, world).build_context(session_id, last.turn_number, user_input)
        mem_text = backend.llm.generate(
            system=render_prompt(template, bundle, user_input),
            messages=[{"role": "user", "content": user_input}],
        ).content

    return {
        "user_input": user_input,
        "no_memory": {"narrator": no_mem_text, "retrieved": None},
        "mem0_only": {"narrator": mem_text, "retrieved": bundle.model_dump()},
    }


@app.get("/sessions/{session_id}/state")
def session_state(session_id: str, backend: Backend = Depends(get_backend)) -> dict[str, Any]:
    with backend.session_factory() as db:
        _get_session(db, session_id)
        return _memory_state(WorldState(db), session_id)
