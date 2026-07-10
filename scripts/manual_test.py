"""Manual smoke test for S1.3: run 5 consecutive story turns in one session.

Runs entirely on the deterministic FakeLlmClient by default — no ANTHROPIC_API_KEY, no
cost. Set LLM_BACKEND=anthropic (+ a real key) to exercise the real backend later.

Requires the mem0 backend deps (sentence-transformers, faiss-cpu); the first run
downloads the ~100MB embedder model.

Run: poetry run python scripts/manual_test.py
Expected: 5 non-empty, deterministic narrations, then list_all() showing 5 memories.
"""

from __future__ import annotations

import os

from core.llm_client import create_llm_client
from core.memory.mem0_adapter import Mem0Adapter
from core.story_loop import StoryLoop

SESSION_ID = "manual-test-session"
TURNS = [
    "Introduzo Aria, uma cavaleira leal ao rei, chegando ao castelo ao anoitecer.",
    "Aria escuta o conselheiro Vex sussurrando com um mensageiro nas sombras.",
    "Aria confronta Vex no salão principal diante da corte.",
    "O rei ordena que Aria investigue as masmorras em segredo.",
    "Nas masmorras, Aria encontra uma carta que prova a traição de Vex.",
]


def main() -> int:
    backend = os.environ.get("LLM_BACKEND", "fake")
    print(f"LLM backend: {backend}")

    llm = create_llm_client()
    memory = Mem0Adapter(SESSION_ID)
    # Start clean so the per-turn count is unambiguous.
    memory.clear()
    loop = StoryLoop(SESSION_ID, memory=memory, llm=llm)

    total_cost = 0.0
    for i, user_input in enumerate(TURNS, start=1):
        result = loop.run_turn(user_input)
        total_cost += result.cost_usd
        print(f"\n===== TURN {i} of {len(TURNS)} =====")
        print(f"> {user_input}\n")
        print(result.narrator_text)
        print(f"[stored: {result.stored_memory_ids} | turn cost: ${result.cost_usd:.6f}]")

    stored = memory.list_all()
    print("\n===== mem0.list_all() =====")
    print(f"{len(stored)} of {len(TURNS)} turns stored in session {SESSION_ID!r}")
    for record in stored:
        print(f"  - {record.id}: {record.text[:60]!r}")
    print(f"\nTotal LLM cost: ${total_cost:.6f}")

    return 0 if len(stored) == len(TURNS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
