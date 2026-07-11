"""Manual test (S3.2): run 10 turns with the real backend, then LlmReflection over them.

Verifies that story_beats get populated with REAL LLM-written summaries (and that the
model returns valid structured JSON). Uses whatever LLM_BACKEND points to — default in
.env is `local` (llama-server), so it runs with no paid API.

Run: poetry run python scripts/manual_reflection_test.py
"""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv
from sqlalchemy import delete

from core.db import get_engine, get_sessionmaker
from core.llm_client import create_llm_client
from core.memory.mem0_adapter import Mem0Adapter
from core.memory.reflection import LlmReflection
from core.memory.world_state import (
    Base,
    Character,
    Location,
    Relation,
    StoryBeat,
    WorldState,
)
from core.story_loop import StoryLoop

load_dotenv()

SESSION_ID = "manual-reflection-test"
TURNS = [
    "Aria, cavaleira leal ao rei Doran, chega ao castelo de Aldrath ao anoitecer.",
    "O conselheiro Vex recebe em segredo uma carta do reino rival de Morwyn.",
    "Aria surpreende Vex escondendo a carta atrás de um retrato na galeria oeste.",
    "Vex oferece a Aria um anel de safira em troca de seu silêncio.",
    "Aria recusa o suborno e jura levar a verdade ao rei.",
    "Vex contrata o assassino Kellan para silenciar Aria.",
    "Kellan ataca Aria nos jardins, mas ela o desarma e o poupa.",
    "Kellan, tocado pela misericórdia, revela o plano de Vex a Aria.",
    "Aria e Kellan levam a carta ao rei Doran na sala do trono.",
    "Doran ordena a prisão de Vex e nomeia Aria comandante da guarda.",
]


def main() -> int:
    print(f"LLM backend: {os.environ.get('LLM_BACKEND', 'fake')}")
    engine = get_engine()
    Base.metadata.create_all(engine)

    with get_sessionmaker(engine)() as session:
        world = WorldState(session)
        for model in (StoryBeat, Relation, Location, Character):
            session.execute(delete(model).where(model.session_id == SESSION_ID))
        session.commit()

        memory = Mem0Adapter(SESSION_ID)
        memory.clear()
        llm = create_llm_client()
        loop = StoryLoop(SESSION_ID, memory=memory, llm=llm)

        started = time.monotonic()
        print(f"\nRunning {len(TURNS)} turns...")
        for i, user_input in enumerate(TURNS, start=1):
            result = loop.run_turn(user_input)
            print(f"turn {i:2d}: {result.narrator_text[:80]!r}")

        print("\nReflecting over the 10 turns (real LLM)...")
        reflection = LlmReflection(llm, world, memory)
        outcome = reflection.consolidate(SESSION_ID, since_turn=0)
        elapsed = time.monotonic() - started

        characters = world.list(Character, SESSION_ID)
        locations = world.list(Location, SESSION_ID)
        relations = world.list(Relation, SESSION_ID)
        beats = world.list(StoryBeat, SESSION_ID)

        print("\n===== reflection result =====")
        print(
            f"characters={len(characters)} locations={len(locations)} "
            f"relations={outcome.relations_updated} beats={outcome.beats_created} "
            f"cost=${outcome.cost_usd:.4f}"
        )
        print(f"characters: {[c.name for c in characters]}")
        print(f"locations:  {[loc.name for loc in locations]}")
        print(f"relations:  {[(r.kind, r.valence) for r in relations]}")
        print("story_beats (real summaries):")
        for beat in beats:
            print(f"  turn {beat.turn} (imp {beat.importance}): {beat.summary}")
        print(f"\ntotal time: {elapsed:.1f}s")

        ok = len(beats) > 0 and all(b.summary.strip() for b in beats)
        print("\nPASS: story_beats populated with real summaries" if ok else "\nFAIL: no real beats")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
