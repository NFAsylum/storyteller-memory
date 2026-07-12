# Storyteller

An LLM storyteller with **long-term memory you can measure**. The differentiator
isn't "chat + a vector store" — it's a quantitative harness that proves, on the
*same* model, that the memory infrastructure changes what the model can recall
across sessions.

> **Headline:** with no memory the model answers **0 of 30** recall questions (0%);
> with the memory system it answers **27 of 30** (90%) — a **+90pp** jump that comes
> entirely from the memory infrastructure, not from swapping the model.
> Cost of the whole measurement: **$0** (local model).

## The idea

The LLM is a **fixed narrative engine** — no fine-tuning. We build memory,
reflection and retrieval *around* it and then measure whether the same model
performs better. The model is the *subject* of the measurement, not the measurer.

"Long-term memory" here means the system verifiably remembers past-session events,
character traits, relationships and world state — and forgets selectively. The
claim is only worth making if it's falsifiable, so every number below comes from
an eval harness you can re-run.

## Does the memory actually work? (measured)

Backend for these runs: a **local** Qwen2.5-Coder-7B via llama-server
(`temperature=0`, `seed=42`) — deliberately a small, reproducible, $0 model so the
*only* thing changing between configs is the memory, not the LLM. Recall is judged
by containment with **word boundaries** (`\b<ground_truth>\b`) + punctuation strip
(audit fix F1.1 — the naive substring version inflated numbers, e.g. `"Vex"`
matched `"Vexado"`). The same QA prompt is used for all three configs, and it tells
the model to answer *"I don't know"* when the context lacks the answer — so the
`no_memory` 0% is genuine abstention, not random guessing.

**Short scenarios (5 turns, 30 questions across 3 scenarios):**

| Config | Recall |
| --- | --- |
| `no_memory` (bare LLM) | 0 of 30 (0%) |
| `mem0_only` | 27 of 30 (90%) |
| `mem0 + reflection` | 28 of 30 (93%) |

**Extended scenarios (16 turns, 30 questions across 3 scenarios):**

| Config | Recall |
| --- | --- |
| `no_memory` | 0 of 30 (0%) |
| `mem0_only` | 21 of 30 (70%) |
| `mem0 + reflection` | 17 of 30 (57%) |

### An honest negative result

Reflection (LLM-generated structured facts) **helped by +3pp** on short scenarios
but **hurt by -13pp** on long ones. With a 7B local model the consolidated facts
are noisier and longer than mem0's clean raw memories, so they distract more than
they help. Reflection would need a stronger consolidation model, or pure-synthesis
questions where raw memory isn't enough, to pay off. This is documented rather than
hidden — see [`results.md`](results.md).

Re-run it yourself:

```bash
LLM_BACKEND=local poetry run python -m eval.run_all_scenarios --config=all
```

## See it (the UI)

The `ui/` app (Next.js 16 + shadcn/ui) makes the memory *felt*, not just tabulated:
a three-column workspace (sessions · chat · memory inspector) with a **compare
with/without memory** split-screen — the same turn re-run twice, generic answer on
the left, contextualized answer on the right.

_Screenshots and a demo GIF are coming — see [`docs/screenshots/README.md`](docs/screenshots/README.md)._

<!-- Uncomment once the files exist (generated on a machine with a browser):
![Memory inspector populated](docs/screenshots/03-memory-inspector.png)
![With/without memory split-screen](docs/screenshots/04-compare-split-screen.png)
-->

See [`ui/README.md`](ui/README.md) for the frontend.

## Architecture

```
core/
├── llm_client.py        # LlmClient Protocol + create_llm_client() factory (LLM_BACKEND=fake|local|anthropic)
├── llm_fakes.py         # deterministic FakeLlmClient (cost $0, no key) — drives all the wiring/tests
├── llm_local.py         # LocalLlmClient (llama-server, OpenAI-compatible) — the measured backend
├── llm_anthropic.py     # AnthropicLlmClient (claude-sonnet-4-6)
├── story_loop.py        # the turn loop (retrieval + narration + reflection)
└── memory/
    ├── mem0_adapter.py   # mem0: Anthropic/local LLM + local HF embedder (all-MiniLM-L6-v2) + local FAISS — no OpenAI
    ├── world_state.py    # SQLAlchemy: Character / Location / Relation / StoryBeat (portable schema for SQLite→Postgres)
    ├── reflection.py     # consolidate turns → structured world state
    └── retrieval_policy.py
eval/
├── harness.py           # run_scenario → ScenarioResult (recall_rate, cost)
├── judges.py            # containment recall judge + LLM-as-judge
├── run_all_scenarios.py # produces results.md
└── scenarios/           # JSON test scenarios
api/                     # FastAPI: 9 endpoints reusing the core, + CORS + /health
ui/                      # Next.js frontend
```

The `LlmClient` Protocol is the spine: `FakeLlmClient` validates the entire system
offline at $0, then the identical wiring runs against a real model for the actual
measurement.

## Running it

```bash
# Backend
poetry install
LLM_BACKEND=local poetry run uvicorn api.main:app --port 8000   # or LLM_BACKEND=fake for offline

# Frontend
cd ui && npm install && npm run dev                            # http://localhost:3000
```

Tests: `poetry run pytest` (backend) · `cd ui && npm run test` (Vitest).

## Status

Sprints 1-4 complete (memory backend + eval harness + measured baseline). Sprint 5
(web UI) built; only screenshots/GIF remain. Next: Sprint 6 deploy (Fly.io + Postgres
migration — the schema is portable). See [`docs/tasks.md`](docs/tasks.md).

## Stack

Python 3.11 · FastAPI · SQLAlchemy + Alembic · mem0 (local embedder + FAISS) ·
pytest — Next.js 16 · shadcn/ui · Tailwind 4 · Vitest.

## License

MIT — see [`LICENSE`](LICENSE).
