"""API tests via FastAPI TestClient with a fake backend (FakeLlm + in-memory mem0, keyless)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.deps import Backend, get_backend
from api.main import _RATE_LIMIT_PER_MINUTE, app
from core.llm_fakes import FakeLlmClient
from core.memory.mem0_adapter import MemoryRecord
from core.memory.world_state import Base, Character, WorldState


class _FakeMem0:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._records: list[MemoryRecord] = []
        self._n = 0

    def add(self, text: str, metadata: dict | None = None) -> str:
        self._n += 1
        rid = f"{self.session_id}-{self._n}"
        self._records.append(MemoryRecord(id=rid, text=text, metadata=metadata or {}))
        return rid

    def search(self, query: str, top_k: int = 5) -> list[MemoryRecord]:
        return self._records[-top_k:]

    def list_all(self) -> list[MemoryRecord]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()


class _MemoryProvider:
    def __init__(self) -> None:
        self._by_session: dict[str, _FakeMem0] = {}

    def __call__(self, session_id: str) -> _FakeMem0:
        return self._by_session.setdefault(session_id, _FakeMem0(session_id))


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> Iterator[None]:
    # Rate-limit state is process-global; clear it so tests don't leak hits into each other.
    from api.main import reset_rate_limit

    reset_rate_limit()
    yield


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, sessionmaker]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    backend = Backend(session_factory=factory, llm=FakeLlmClient(), memory_for=_MemoryProvider())
    app.dependency_overrides[get_backend] = lambda: backend
    yield TestClient(app), factory
    app.dependency_overrides.clear()


def _create(tc: TestClient, name: str = "Minha história") -> str:
    resp = tc.post("/sessions", json={"name": name, "brief": "um começo"})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_and_list_sessions(client) -> None:
    tc, _ = client
    sid = _create(tc)
    listing = tc.get("/sessions").json()
    assert any(s["id"] == sid and s["name"] == "Minha história" for s in listing)


def test_create_with_config_persists(client) -> None:
    tc, _ = client
    resp = tc.post("/sessions", json={"name": "H", "config": {"genre": "scifi", "pov": "first_person"}})
    assert resp.status_code == 201
    assert resp.json()["config"]["genre"] == "scifi"
    sid = resp.json()["id"]
    got = tc.get(f"/sessions/{sid}").json()
    assert got["config"]["genre"] == "scifi"
    assert got["config"]["pov"] == "first_person"


def test_create_defaults_config_when_omitted(client) -> None:
    tc, _ = client
    sid = _create(tc)
    cfg = tc.get(f"/sessions/{sid}").json()["config"]
    assert cfg["genre"] == "fantasy"  # default
    assert cfg["target_length"] == "medium"


def test_patch_config_updates(client) -> None:
    tc, _ = client
    sid = _create(tc)
    resp = tc.patch(f"/sessions/{sid}/config", json={"genre": "horror", "tone": "gothic"})
    assert resp.status_code == 200
    assert resp.json()["config"]["genre"] == "horror"
    got = tc.get(f"/sessions/{sid}").json()["config"]
    assert got["genre"] == "horror"
    assert got["tone"] == "gothic"


def test_run_turns_increment_and_persist(client) -> None:
    tc, _ = client
    sid = _create(tc)

    r1 = tc.post(f"/sessions/{sid}/turn", json={"text": "Aria entra no castelo."}).json()
    assert r1["turn_number"] == 1
    assert r1["narrator_text"].strip() != ""

    r2 = tc.post(f"/sessions/{sid}/turn", json={"text": "Aria encontra Vex."}).json()
    assert r2["turn_number"] == 2

    session = tc.get(f"/sessions/{sid}").json()
    assert session["last_turn"] == 2
    assert len(session["turns"]) == 2
    assert "memory_state" in session


def test_turn_context_is_retrievable(client) -> None:
    tc, _ = client
    sid = _create(tc)
    tc.post(f"/sessions/{sid}/turn", json={"text": "Aria chega."})
    ctx = tc.get(f"/sessions/{sid}/turns/1/context").json()
    assert "raw_memories" in ctx and "turn" in ctx


def test_state_reflects_world_state(client) -> None:
    tc, factory = client
    sid = _create(tc)
    with factory() as db:
        WorldState(db).add(
            Character(session_id=sid, name="Aria", traits=["leal"], first_appeared_turn=1, last_seen_turn=1)
        )
        db.commit()
    state = tc.get(f"/sessions/{sid}/state").json()
    assert [c["name"] for c in state["characters"]] == ["Aria"]


def test_state_exposes_next_reflection_and_raw_count(client) -> None:
    # audit 0.1: the UI needs a non-empty pre-reflection signal + when consolidation runs.
    tc, _ = client
    sid = _create(tc)
    tc.post(f"/sessions/{sid}/turn", json={"text": "Aria chega ao castelo de Aldrath."})
    tc.post(f"/sessions/{sid}/turn", json={"text": "Aria observa a corte."})
    state = tc.get(f"/sessions/{sid}/state").json()
    assert state["raw_memory_count"] == 2  # one raw memory stored per turn
    assert state["next_reflection_at"] == 4  # after turn 2, next consolidation is turn 4


def test_state_next_reflection_before_any_turn(client) -> None:
    tc, _ = client
    sid = _create(tc)
    state = tc.get(f"/sessions/{sid}/state").json()
    assert state["raw_memory_count"] == 0
    assert state["next_reflection_at"] == 2  # first consolidation lands on turn 2


def test_raw_memories_ordered_by_turn(client) -> None:
    tc, _ = client
    sid = _create(tc)
    tc.post(f"/sessions/{sid}/turn", json={"text": "primeiro turno"})
    tc.post(f"/sessions/{sid}/turn", json={"text": "segundo turno"})
    rows = tc.get(f"/sessions/{sid}/raw-memories").json()
    assert [r["turn"] for r in rows] == [1, 2]
    assert "primeiro turno" in rows[0]["text"]
    assert rows[0]["type"] == "story_turn"


def test_compare_turn_returns_two_answers(client) -> None:
    tc, _ = client
    sid = _create(tc)
    tc.post(f"/sessions/{sid}/turn", json={"text": "Aria confronta Vex."})
    cmp = tc.post(f"/sessions/{sid}/compare-turn").json()
    assert cmp["no_memory"]["narrator"].strip() != ""
    assert cmp["mem0_only"]["narrator"].strip() != ""
    assert cmp["no_memory"]["retrieved"] is None
    assert cmp["mem0_only"]["retrieved"] is not None


def test_delete_session(client) -> None:
    tc, _ = client
    sid = _create(tc)
    assert tc.delete(f"/sessions/{sid}").status_code == 204
    assert tc.get(f"/sessions/{sid}").status_code == 404


def test_turn_on_missing_session_404(client) -> None:
    tc, _ = client
    assert tc.post("/sessions/nope/turn", json={"text": "x"}).status_code == 404


def test_health_is_structured(client) -> None:
    tc, _ = client
    resp = tc.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db_ready"] is True
    assert body["mem0_ready"] is True
    assert "backend_llm" in body


def test_cors_allows_configured_origin(client) -> None:
    tc, _ = client
    resp = tc.options(
        "/sessions",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_rejects_unknown_origin(client) -> None:
    tc, _ = client
    resp = tc.options(
        "/sessions",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Starlette's CORSMiddleware rejects a disallowed preflight (400, no allow-origin header).
    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers


def test_rate_limit_triggers_after_the_limit(client) -> None:
    tc, _ = client
    codes = [tc.get("/sessions").status_code for _ in range(_RATE_LIMIT_PER_MINUTE + 1)]
    assert codes[:_RATE_LIMIT_PER_MINUTE] == [200] * _RATE_LIMIT_PER_MINUTE
    assert codes[_RATE_LIMIT_PER_MINUTE] == 429  # the (limit+1)th request is throttled


def test_delete_rolls_back_when_mem0_clear_fails(tmp_path: Path) -> None:
    # F1.4: if mem0.clear() raises, the DB delete must roll back and the client get 500.
    engine = create_engine(f"sqlite:///{tmp_path / 'api_fail.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    class _FailProvider:
        def __call__(self, session_id: str) -> _FakeMem0:
            mem = _FakeMem0(session_id)

            def boom() -> None:
                raise RuntimeError("mem0 down")

            mem.clear = boom  # type: ignore[method-assign]
            return mem

    backend = Backend(session_factory=factory, llm=FakeLlmClient(), memory_for=_FailProvider())
    app.dependency_overrides[get_backend] = lambda: backend
    try:
        tc = TestClient(app)
        sid = tc.post("/sessions", json={"name": "x"}).json()["id"]
        assert tc.delete(f"/sessions/{sid}").status_code == 500
        assert tc.get(f"/sessions/{sid}").status_code == 200  # NOT deleted
    finally:
        app.dependency_overrides.clear()
