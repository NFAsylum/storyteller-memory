"""Structural end-to-end test (S2.5): 15 turns with the Fake stack, no real LLM.

Exercises the full Sprint-2 data flow — story_loop -> mem0 + world_state, retrieval
feeding the prompt, reflection consolidating every 5 turns — and verifies the DATA
flowed: tables populated, reflection fired 3x (turns 5/10/15), retrieval returned >0
items across the last 10 turns.

Runs on FakeLlmClient by default (no ANTHROPIC_API_KEY). Deterministic: volatile mem0
UUIDs and DB row ids are never printed.

Run: poetry run python scripts/manual_test_sprint2.py
"""

from __future__ import annotations

import os

from sqlalchemy import delete

from core.db import get_engine, get_sessionmaker
from core.llm_client import create_llm_client
from core.memory.mem0_adapter import Mem0Adapter
from core.memory.reflection import FakeReflection
from core.memory.retrieval_policy import RetrievalPolicy
from core.memory.world_state import (
    Base,
    Character,
    Location,
    Relation,
    StoryBeat,
    WorldState,
)
from core.story_loop import StoryLoop

SESSION_ID = "manual-test-sprint2"
BASE_TURNS = [
    "Aria, cavaleira leal ao rei Doran, chega ao castelo de Aldrath.",
    "O conselheiro Vex recebe uma carta selada do reino de Morwyn.",
    "Aria surpreende Vex escondendo a carta na galeria oeste.",
    "O rei Doran convoca Aria para uma audiência secreta.",
    "Aria denuncia Vex, e Vex jura vingança diante da corte.",
]
TURNS = (BASE_TURNS * 3)[:15]
EXPECTED_REFLECTIONS = 3  # turns 5, 10, 15 with reflect_every=5


def _reset_world(session, session_id: str) -> None:
    for model in (StoryBeat, Relation, Location, Character):
        session.execute(delete(model).where(model.session_id == session_id))
    session.commit()


def main() -> int:
    print(f"LLM backend: {os.environ.get('LLM_BACKEND', 'fake')}")

    engine = get_engine()
    Base.metadata.create_all(engine)

    with get_sessionmaker(engine)() as session:
        world = WorldState(session)
        _reset_world(session, SESSION_ID)

        memory = Mem0Adapter(SESSION_ID)
        memory.clear()

        loop = StoryLoop(
            SESSION_ID,
            memory=memory,
            llm=create_llm_client(),
            retrieval_policy=RetrievalPolicy(memory, world),
            reflection=FakeReflection(world, memory),
            reflect_every=5,
        )

        print(f"\nRunning {len(TURNS)} turns...")
        retrieved_counts: list[int] = []
        for i, user_input in enumerate(TURNS, start=1):
            result = loop.run_turn(user_input)
            ctx = result.retrieved_context
            n_mem = len(ctx["raw_memories"])
            n_chars = len(ctx["active_characters"])
            retrieved_counts.append(n_mem + n_chars)
            print(f"turn {i:2d} | retrieved: {n_mem} memories, {n_chars} active_characters")

        characters = sorted(c.name for c in world.list(Character, SESSION_ID))
        beats = sorted(world.list(StoryBeat, SESSION_ID), key=lambda b: b.turn)
        n_locations = len(world.list(Location, SESSION_ID))
        n_relations = len(world.list(Relation, SESSION_ID))

        print("\n===== world_state =====")
        print(f"characters ({len(characters)}): {characters}")
        print(f"story_beats ({len(beats)}):")
        for beat in beats:
            print(f"  turn {beat.turn}: {beat.summary}")

        # last 10 turns each returned at least one retrieved item
        last10_min = min(retrieved_counts[-10:]) if len(retrieved_counts) >= 10 else 0
        checks = {
            "tables populated (characters > 0)": len(characters) > 0,
            f"reflection fired {EXPECTED_REFLECTIONS}x (story_beats == {EXPECTED_REFLECTIONS})": len(beats)
            == EXPECTED_REFLECTIONS,
            "retrieval > 0 across last 10 turns": last10_min > 0,
        }
        print("\n===== checks =====")
        print(f"tables: characters={len(characters)} locations={n_locations} relations={n_relations} story_beats={len(beats)}")
        for label, passed in checks.items():
            print(f"  [{'PASS' if passed else 'FAIL'}] {label}")

        ok = all(checks.values())
        print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
