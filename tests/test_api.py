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
from core.memory.world_state import Base, Character, Location, Relation, StoryBeat, WorldState


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

    def delete(self, memory_id: str) -> None:
        self._records = [r for r in self._records if r.id != memory_id]

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


def test_story_starters_endpoint(client) -> None:
    tc, _ = client
    full = tc.get("/story-starters").json()
    assert "fantasy" in full["by_genre"] and "scifi" in full["by_genre"]
    one = tc.get("/story-starters", params={"genre": "scifi"}).json()
    assert one["genre"] == "scifi"
    assert len(one["starters"]) >= 3


def test_create_with_protagonist_persists(client) -> None:
    tc, _ = client
    resp = tc.post(
        "/sessions",
        json={"name": "H", "config": {"protagonist": {"role": "protagonist", "character_name": "Aria"}}},
    )
    sid = resp.json()["id"]
    cfg = tc.get(f"/sessions/{sid}").json()["config"]
    assert cfg["protagonist"]["role"] == "protagonist"
    assert cfg["protagonist"]["character_name"] == "Aria"


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


def test_patch_and_delete_character(client) -> None:
    tc, factory = client
    sid = _create(tc)
    with factory() as db:
        c = WorldState(db).add(
            Character(session_id=sid, name="Vex", traits=["cruel"], first_appeared_turn=1, last_seen_turn=1)
        )
        db.commit()
        cid = c.id

    r = tc.patch(
        f"/sessions/{sid}/state/characters/{cid}",
        json={"name": "Vexa", "traits": ["leal"], "first_appeared_turn": 1, "last_seen_turn": 3},
    )
    assert r.status_code == 200 and r.json()["name"] == "Vexa"
    assert tc.get(f"/sessions/{sid}/state").json()["characters"][0]["traits"] == ["leal"]

    assert tc.delete(f"/sessions/{sid}/state/characters/{cid}").status_code == 204
    assert tc.get(f"/sessions/{sid}/state").json()["characters"] == []


def test_delete_location_relation_and_beat(client) -> None:
    tc, factory = client
    sid = _create(tc)
    with factory() as db:
        w = WorldState(db)
        loc = w.add(Location(session_id=sid, name="Aldrath", description="", first_visited_turn=1))
        a = w.add(Character(session_id=sid, name="Aria", traits=[], first_appeared_turn=1, last_seen_turn=1))
        b = w.add(Character(session_id=sid, name="Vex", traits=[], first_appeared_turn=1, last_seen_turn=1))
        rel = w.add(Relation(session_id=sid, a_character_id=a.id, b_character_id=b.id, kind="enemy", valence=-2, since_turn=1))
        beat = w.add(StoryBeat(session_id=sid, summary="Aria vs Vex", turn=1, importance=5, tags=[]))
        db.commit()
        loc_id, rel_id, beat_id = loc.id, rel.id, beat.id

    assert tc.delete(f"/sessions/{sid}/state/locations/{loc_id}").status_code == 204
    assert tc.delete(f"/sessions/{sid}/state/relations/{rel_id}").status_code == 204
    assert tc.delete(f"/sessions/{sid}/state/story-beats/{beat_id}").status_code == 204
    state = tc.get(f"/sessions/{sid}/state").json()
    assert state["locations"] == [] and state["relations"] == [] and state["story_beats"] == []


def test_crud_404_for_foreign_or_missing_entity(client) -> None:
    tc, factory = client
    sid = _create(tc)
    other = _create(tc)
    with factory() as db:
        c = WorldState(db).add(
            Character(session_id=other, name="X", traits=[], first_appeared_turn=1, last_seen_turn=1)
        )
        db.commit()
        cid = c.id
    assert tc.delete(f"/sessions/{sid}/state/characters/{cid}").status_code == 404  # foreign session
    assert (
        tc.patch(
            f"/sessions/{sid}/state/characters/999999",
            json={"name": "n", "traits": [], "first_appeared_turn": 1, "last_seen_turn": 1},
        ).status_code
        == 404
    )


def test_deleted_beat_absent_from_next_turn_context(client) -> None:
    # audit 5.3 DoD: a deleted fact must not reach the next turn's context.
    tc, factory = client
    sid = _create(tc)
    with factory() as db:
        beat = WorldState(db).add(
            StoryBeat(session_id=sid, summary="A traição de Vex", turn=1, importance=9, tags=[])
        )
        db.commit()
        beat_id = beat.id

    ctx1 = tc.post(f"/sessions/{sid}/turn", json={"text": "Aria avança."}).json()["retrieved_context"]
    assert "A traição de Vex" in ctx1["structured_facts"]

    tc.delete(f"/sessions/{sid}/state/story-beats/{beat_id}")
    ctx2 = tc.post(f"/sessions/{sid}/turn", json={"text": "Aria continua."}).json()["retrieved_context"]
    assert "A traição de Vex" not in ctx2["structured_facts"]


def test_edit_turn_updates_input_and_renarrates(client) -> None:
    tc, _ = client
    sid = _create(tc)
    tc.post(f"/sessions/{sid}/turn", json={"text": "Aria entra."})
    r = tc.patch(f"/sessions/{sid}/turns/1", json={"text": "Aria recua."})
    assert r.status_code == 200
    assert r.json()["user_input"] == "Aria recua."
    assert r.json()["narrator_text"].strip() != ""
    assert tc.get(f"/sessions/{sid}").json()["turns"][0]["user_input"] == "Aria recua."


def test_regenerate_turn_keeps_input(client) -> None:
    tc, _ = client
    sid = _create(tc)
    tc.post(f"/sessions/{sid}/turn", json={"text": "Aria entra."})
    r = tc.post(f"/sessions/{sid}/turns/1/regenerate")
    assert r.status_code == 200
    assert r.json()["narrator_text"].strip() != ""
    assert tc.get(f"/sessions/{sid}").json()["turns"][0]["user_input"] == "Aria entra."


def test_delete_turn_removes_it_and_its_memory(client) -> None:
    tc, _ = client
    sid = _create(tc)
    tc.post(f"/sessions/{sid}/turn", json={"text": "turno 1"})
    tc.post(f"/sessions/{sid}/turn", json={"text": "turno 2"})
    assert tc.delete(f"/sessions/{sid}/turns/2").status_code == 204
    session = tc.get(f"/sessions/{sid}").json()
    assert [t["turn_number"] for t in session["turns"]] == [1]
    assert session["last_turn"] == 1  # head stepped back
    rows = tc.get(f"/sessions/{sid}/raw-memories").json()
    assert [r["turn"] for r in rows] == [1]  # mem0 entry for turn 2 gone


def test_edit_missing_turn_404(client) -> None:
    tc, _ = client
    sid = _create(tc)
    assert tc.patch(f"/sessions/{sid}/turns/99", json={"text": "x"}).status_code == 404


def test_export_formats(client) -> None:
    tc, _ = client
    sid = _create(tc, name="Saga")
    tc.post(f"/sessions/{sid}/turn", json={"text": "Aria entra no castelo."})

    md = tc.get(f"/sessions/{sid}/export", params={"format": "markdown"})
    assert md.status_code == 200
    assert "text/markdown" in md.headers["content-type"]
    assert "attachment" in md.headers["content-disposition"]
    assert "# Saga" in md.text and "Aria entra no castelo." in md.text

    txt = tc.get(f"/sessions/{sid}/export", params={"format": "txt"}).text
    assert txt.strip() != "" and "**Você:**" not in txt  # prose only, no chat labels

    data = tc.get(f"/sessions/{sid}/export", params={"format": "json"}).json()
    assert data["name"] == "Saga" and len(data["turns"]) == 1 and "memory_state" in data


def test_export_unknown_format_400(client) -> None:
    tc, _ = client
    sid = _create(tc)
    assert tc.get(f"/sessions/{sid}/export", params={"format": "pdf"}).status_code == 400


def test_fork_creates_independent_copy(client) -> None:
    tc, factory = client
    sid = _create(tc, name="Original")
    tc.post(f"/sessions/{sid}/turn", json={"text": "turno 1"})
    tc.post(f"/sessions/{sid}/turn", json={"text": "turno 2"})
    with factory() as db:
        WorldState(db).add(
            Character(session_id=sid, name="Aria", traits=["leal"], first_appeared_turn=1, last_seen_turn=2)
        )
        db.commit()

    forked = tc.post(f"/sessions/{sid}/fork", params={"from_turn": 1})
    assert forked.status_code == 201
    fid = forked.json()["id"]
    assert forked.json()["name"] == "Original — fork"

    # fork has only turn 1 + the character (first_appeared_turn 1)
    fsession = tc.get(f"/sessions/{fid}").json()
    assert [t["turn_number"] for t in fsession["turns"]] == [1]
    assert [c["name"] for c in fsession["memory_state"]["characters"]] == ["Aria"]

    # editing the fork does not touch the original
    tc.patch(f"/sessions/{fid}/turns/1", json={"text": "turno 1 alterado"})
    assert tc.get(f"/sessions/{sid}").json()["turns"][0]["user_input"] == "turno 1"


def _sse_events(text: str) -> list[str]:
    return [ln[len("event: ") :] for ln in text.splitlines() if ln.startswith("event: ")]


def test_turn_streamed_emits_events_in_order(client) -> None:
    tc, _ = client
    sid = _create(tc)
    resp = tc.post(f"/sessions/{sid}/turn-streamed", json={"text": "Aria entra."})
    assert resp.status_code == 200
    assert _sse_events(resp.text) == [
        "retrieval_start",
        "retrieval_done",
        "llm_start",
        "llm_done",
        "reflection_check",
        "turn_stored",
    ]
    assert tc.get(f"/sessions/{sid}").json()["last_turn"] == 1  # turn persisted


def test_turn_streamed_errors_without_storing(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'sse_fail.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    class _FailingLlm:
        def generate(self, system, messages, tools=None):
            raise RuntimeError("llm down")

    backend = Backend(session_factory=factory, llm=_FailingLlm(), memory_for=_MemoryProvider())
    app.dependency_overrides[get_backend] = lambda: backend
    try:
        tc = TestClient(app)
        sid = tc.post("/sessions", json={"name": "x"}).json()["id"]
        resp = tc.post(f"/sessions/{sid}/turn-streamed", json={"text": "boom"})
        events = _sse_events(resp.text)
        assert "error" in events
        assert "turn_stored" not in events
        assert tc.get(f"/sessions/{sid}").json()["last_turn"] == 0  # nothing stored
    finally:
        app.dependency_overrides.clear()


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
