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
  GET    /sessions/{id}/state                   world_state (+ raw_memory_count, next_reflection_at)
  GET    /sessions/{id}/raw-memories            raw mem0 memories (pre-reflection state), by turn
  PATCH  /sessions/{id}/config                  update narrative controls (genre/pov/tone/...)
  POST   /sessions/{id}/turn-streamed           run a turn, streaming progress as SSE events
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text

from api.deps import Backend, get_backend
from core.memory.reflection import LlmReflection
from core.memory.retrieval_policy import RetrievalPolicy
from core.session_config import SessionConfig
from core.memory.world_state import (
    Character,
    Location,
    Relation,
    Session,
    StoryBeat,
    Turn,
    WorldState,
)
from core.story_loop import (
    DEFAULT_REFLECT_EVERY,
    StoryLoop,
    load_prompt_template,
    render_prompt,
)

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

# Simple in-memory per-IP rate limit (no extra dependency). Sliding 60s window; the
# (limit+1)th request in a window is rejected with 429. /health is exempt so external
# health checks are never throttled. State is process-local — fine for single-instance dev.
_RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
_RATE_WINDOW_SECONDS = 60.0
_rate_hits: dict[str, list[float]] = defaultdict(list)


def reset_rate_limit() -> None:
    """Clear the in-memory rate-limit window (used to isolate tests)."""
    _rate_hits.clear()


@app.middleware("http")
async def rate_limit(request: Request, call_next: Any) -> Any:
    if request.url.path == "/health":
        return await call_next(request)
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    hits = _rate_hits[client_ip]
    hits[:] = [t for t in hits if t > now - _RATE_WINDOW_SECONDS]
    if len(hits) >= _RATE_LIMIT_PER_MINUTE:
        return JSONResponse(
            status_code=429, content={"detail": "rate limit exceeded — try again shortly"}
        )
    hits.append(now)
    return await call_next(request)


def _db_ready(backend: Backend) -> bool:
    try:
        with backend.session_factory() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - health must report, never raise
        return False


def _mem0_ready(backend: Backend) -> bool:
    try:
        return backend.memory_for("__health__") is not None
    except Exception:  # noqa: BLE001
        return False


@app.get("/health")
def health(backend: Backend = Depends(get_backend)) -> dict[str, Any]:
    """Structured readiness: LLM backend name + mem0/DB reachability (always 200)."""
    db_ok = _db_ready(backend)
    mem0_ok = _mem0_ready(backend)
    return {
        "status": "ok" if (db_ok and mem0_ok) else "degraded",
        "backend_llm": os.environ.get("LLM_BACKEND", "fake"),
        "mem0_ready": mem0_ok,
        "db_ready": db_ok,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_reflection_at(last_turn: int) -> int:
    """Turn number at which the next automatic consolidation will fire (audit 0.1 UX)."""
    return (last_turn // DEFAULT_REFLECT_EVERY + 1) * DEFAULT_REFLECT_EVERY


class CreateSession(BaseModel):
    name: str
    brief: str = ""
    config: SessionConfig = Field(default_factory=SessionConfig)


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
            {"id": c.id, "name": c.name, "traits": c.traits,
             "first_appeared_turn": c.first_appeared_turn, "last_seen_turn": c.last_seen_turn}
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
        db.add(
            Session(
                id=session_id,
                name=body.name,
                brief=body.brief,
                created_at=_now(),
                last_turn=0,
                config=body.config.model_dump(),
            )
        )
        db.commit()
    return {"id": session_id, "name": body.name, "last_turn": 0, "config": body.config.model_dump()}


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
            "config": session.config or SessionConfig().model_dump(),
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


@app.patch("/sessions/{session_id}/config")
def update_config(
    session_id: str, body: SessionConfig, backend: Backend = Depends(get_backend)
) -> dict[str, Any]:
    with backend.session_factory() as db:
        session = _get_session(db, session_id)
        session.config = body.model_dump()
        db.commit()
        return {"id": session_id, "config": session.config}


@app.post("/sessions/{session_id}/turn")
def run_turn(session_id: str, body: TurnInput, backend: Backend = Depends(get_backend)) -> dict[str, Any]:
    with backend.session_factory() as db:
        session = _get_session(db, session_id)
        config = SessionConfig(**session.config) if session.config else SessionConfig()
        memory = backend.memory_for(session_id)
        world = WorldState(db)
        loop = StoryLoop(
            session_id,
            memory=memory,
            llm=backend.llm,
            retrieval_policy=RetrievalPolicy(memory, world),
            reflection=LlmReflection(backend.llm, world, memory),
            start_turn=session.last_turn,
            config=config,
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


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/sessions/{session_id}/turn-streamed")
def run_turn_streamed(
    session_id: str, body: TurnInput, backend: Backend = Depends(get_backend)
) -> StreamingResponse:
    """Same turn as POST /turn, but streams stage progress as SSE (audit 4.1).

    Events, in order: retrieval_start, retrieval_done, llm_start, llm_done,
    reflection_check, turn_stored. An LLM failure emits `error` instead and stores
    nothing (no partial turn). The non-streamed /turn stays the canonical path.
    """

    def events() -> Iterator[str]:
        with backend.session_factory() as db:
            session = db.get(Session, session_id)
            if session is None:
                yield _sse("error", {"message": f"session {session_id!r} not found"})
                return
            config = SessionConfig(**session.config) if session.config else SessionConfig()
            memory = backend.memory_for(session_id)
            world = WorldState(db)
            turn_number = session.last_turn + 1
            try:
                yield _sse("retrieval_start", {"turn": turn_number})
                bundle = RetrievalPolicy(memory, world).build_context(
                    session_id, turn_number, body.text
                )
                yield _sse(
                    "retrieval_done",
                    {
                        "active_characters": bundle.active_characters,
                        "raw_memory_count": len(bundle.raw_memories),
                    },
                )
                yield _sse("llm_start", {})
                prompt = render_prompt(load_prompt_template(), bundle, body.text, config)
                response = backend.llm.generate(
                    system=prompt, messages=[{"role": "user", "content": body.text}]
                )
                narrator_text = response.content
                yield _sse("llm_done", {"narrator_text": narrator_text, "cost_usd": response.cost_usd})
            except Exception as exc:  # noqa: BLE001 - surface as SSE error, never crash the stream
                yield _sse("error", {"message": str(exc)})
                return

            # Persist only after a successful generation (no partial turns on error).
            memory.add(
                f"Turn {turn_number}\nPlayer: {body.text}\nNarrator: {narrator_text}",
                metadata={"turn": turn_number, "type": "story_turn"},
            )
            yield _sse("reflection_check", {"next_reflection_at": _next_reflection_at(turn_number)})
            if turn_number % DEFAULT_REFLECT_EVERY == 0:
                try:
                    LlmReflection(backend.llm, world, memory).consolidate(
                        session_id, since_turn=turn_number - DEFAULT_REFLECT_EVERY
                    )
                except Exception:  # noqa: BLE001 - a reflection failure must not lose the turn
                    pass
            retrieved_context = {**bundle.model_dump(), "turn": turn_number}
            db.add(
                Turn(
                    session_id=session_id,
                    turn_number=turn_number,
                    user_input=body.text,
                    narrator_text=narrator_text,
                    retrieved_context=retrieved_context,
                    created_at=_now(),
                )
            )
            session.last_turn = turn_number
            db.commit()
            yield _sse(
                "turn_stored",
                {
                    "turn_number": turn_number,
                    "narrator_text": narrator_text,
                    "retrieved_context": retrieved_context,
                    "cost_usd": response.cost_usd,
                },
            )

    return StreamingResponse(events(), media_type="text/event-stream")


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
        session = _get_session(db, session_id)
        config = SessionConfig(**session.config) if session.config else SessionConfig()
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
            system=render_prompt(template, None, user_input, config),
            messages=[{"role": "user", "content": user_input}],
        ).content

        # mem0_only: real retrieved context (not persisted)
        bundle = RetrievalPolicy(memory, world).build_context(session_id, last.turn_number, user_input)
        mem_text = backend.llm.generate(
            system=render_prompt(template, bundle, user_input, config),
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
        session = _get_session(db, session_id)
        last_turn = session.last_turn
        state = _memory_state(WorldState(db), session_id)
    # Surface the raw mem0 memories (populated every turn) and the next consolidation
    # turn so the UI can show a non-empty "pre-reflection" state instead of empty tabs.
    state["raw_memory_count"] = len(backend.memory_for(session_id).list_all())
    state["next_reflection_at"] = _next_reflection_at(last_turn)
    return state


@app.get("/sessions/{session_id}/raw-memories")
def raw_memories(session_id: str, backend: Backend = Depends(get_backend)) -> list[dict[str, Any]]:
    """Raw mem0 memories for the session, ordered by turn — the pre-reflection state."""
    with backend.session_factory() as db:
        _get_session(db, session_id)
    records = backend.memory_for(session_id).list_all()
    ordered = sorted(records, key=lambda r: r.metadata.get("turn", 0))
    return [
        {"id": r.id, "text": r.text, "turn": r.metadata.get("turn"),
         "type": r.metadata.get("type")}
        for r in ordered
    ]
