"""Manual end-to-end test (S1.6): 5 story turns in one session, fully deterministic.

Runs on the deterministic FakeLlmClient by default — no ANTHROPIC_API_KEY, no cost.
Set LLM_BACKEND=anthropic (+ a real key) to exercise the real backend later.

Output is deterministic across runs: it prints narrator_text per turn (hash-seeded, so
stable) and list_all() sorted by turn. mem0's random memory UUIDs are deliberately NOT
printed — they are the only non-deterministic part — so repeated runs produce identical
stdout.

Requires the mem0 backend deps (sentence-transformers, faiss-cpu); the first run
downloads the ~100MB embedder model.

Run: poetry run python scripts/manual_test.py
Expected: 5 non-empty narrations, then "5 of 5 turns stored".
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
    print(f"LLM backend: {os.environ.get('LLM_BACKEND', 'fake')}")

    llm = create_llm_client()
    memory = Mem0Adapter(SESSION_ID)
    # Start clean so the per-turn count is unambiguous and the run is repeatable.
    memory.clear()
    loop = StoryLoop(SESSION_ID, memory=memory, llm=llm)

    total_cost = 0.0
    for i, user_input in enumerate(TURNS, start=1):
        result = loop.run_turn(user_input)
        total_cost += result.cost_usd
        print(f"\n===== TURN {i} of {len(TURNS)} =====")
        print(f"> {user_input}\n")
        print(result.narrator_text)
        print(f"[memories stored this turn: {len(result.stored_memory_ids)} | turn cost: ${result.cost_usd:.6f}]")

    stored = memory.list_all()
    print("\n===== mem0.list_all() =====")
    print(f"{len(stored)} of {len(TURNS)} turns stored in session {SESSION_ID!r}")
    # Sort by turn metadata so the listing is deterministic (mem0 IDs/order are not).
    for record in sorted(stored, key=lambda r: r.metadata.get("turn", 0)):
        turn = record.metadata.get("turn", "?")
        print(f"  turn {turn}: {record.text[:60]!r}")
    print(f"\nTotal LLM cost: ${total_cost:.6f}")

    return 0 if len(stored) == len(TURNS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
