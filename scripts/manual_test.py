"""Manual smoke test for S1.3: run 5 consecutive story turns in one session.

PENDING VERIFICATION — needs a live LLM and the mem0 backend, so it cannot run in the
CI sandbox. Requirements to run:
  - ANTHROPIC_API_KEY exported (or in .env)
  - mem0 embedder deps installed: sentence-transformers, faiss-cpu (first run downloads
    the ~100MB all-MiniLM-L6-v2 model)

Run: poetry run python scripts/manual_test.py

Expected: 5 non-empty narrations printed, then list_all() showing 5 stored memories.
"""

from __future__ import annotations

import os
import sys

from core.llm_client import LlmClient
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
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set — cannot run the live smoke test.", file=sys.stderr)
        return 2

    llm = LlmClient()
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
        print(f"[stored memory ids: {result.stored_memory_ids} | turn cost: ${result.cost_usd:.6f}]")

    stored = memory.list_all()
    print("\n===== mem0.list_all() =====")
    print(f"{len(stored)} of {len(TURNS)} turns stored in session {SESSION_ID!r}")
    for record in stored:
        print(f"  - {record.id}: {record.text[:60]!r}")
    print(f"\nTotal LLM cost: ${total_cost:.6f}")

    return 0 if len(stored) == len(TURNS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
