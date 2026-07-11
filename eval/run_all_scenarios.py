"""Run all seed scenarios under a named config, aggregate recall, and write results.md.

Usage:
  LLM_BACKEND=local poetry run python -m eval.run_all_scenarios --config=baseline_mem0_only
  LLM_BACKEND=local poetry run python -m eval.run_all_scenarios --config=mem0_plus_reflection

Each run updates results.json (per-config stats) and re-renders results.md; once both
configs have run, results.md shows both numbers, the delta, and total cost.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import delete

from core.db import get_engine, get_sessionmaker
from core.llm_client import create_llm_client
from core.memory.mem0_adapter import Mem0Adapter
from core.memory.world_state import (
    Base,
    Character,
    Location,
    Relation,
    StoryBeat,
    WorldState,
)
from eval.harness import HarnessConfig, run_scenario
from eval.scenario import load_scenario

load_dotenv()

_SCEN_DIR = Path(__file__).parent / "scenarios"
_SEEDS = ["seed_01.json", "seed_02.json", "seed_03.json"]
_RESULTS_MD = Path("results.md")
_RESULTS_JSON = Path("results.json")

CONFIGS: dict[str, dict[str, bool]] = {
    "baseline_mem0_only": {"use_retrieval": True, "use_reflection": False},
    "mem0_plus_reflection": {"use_retrieval": True, "use_reflection": True},
}


def _reset_world(session, session_id: str) -> None:
    for model in (StoryBeat, Relation, Location, Character):
        session.execute(delete(model).where(model.session_id == session_id))
    session.commit()


def run_config(config_name: str) -> dict[str, float | int]:
    config = HarnessConfig(name=config_name, **CONFIGS[config_name])
    llm = create_llm_client()
    engine = get_engine()
    Base.metadata.create_all(engine)
    session_factory = get_sessionmaker(engine)

    correct = total = 0
    cost = 0.0
    print(f"== config: {config_name} ==")
    for seed in _SEEDS:
        scenario = load_scenario(_SCEN_DIR / seed)
        session_id = f"{scenario.id}--{config_name}"
        memory = Mem0Adapter(session_id)
        with session_factory() as session:
            world = WorldState(session)
            _reset_world(session, session_id)
            result = run_scenario(scenario, config, llm, memory, world)
        correct += result.correct
        total += result.total
        cost += result.total_cost_usd
        print(f"  {seed}: {result.correct} of {result.total} ({result.recall_rate:.0%})")

    rate = correct / total if total else 0.0
    print(f"{config_name}: {correct} of {total} recall ({rate:.0%}) | cost ${cost:.4f}")
    return {"correct": correct, "total": total, "rate": rate, "cost": cost}


def _render_results_md(data: dict[str, dict]) -> str:
    backend = os.environ.get("LLM_BACKEND", "fake")
    lines = [
        "# Resultados — Storyteller",
        "",
        f"Backend: `{backend}` (modelo local Qwen2.5-Coder-7B via llama-server).",
        "",
        "## Sprint 3 — baseline",
        "",
    ]
    base = data.get("baseline_mem0_only")
    aug = data.get("mem0_plus_reflection")
    if base:
        lines.append(
            f"sprint 3 baseline (mem0 only): {base['correct']} of {base['total']} recall ({base['rate'] * 100:.0f}%)"
        )
    if aug:
        lines.append(
            f"sprint 3 augmented (mem0 + reflection): {aug['correct']} of {aug['total']} recall ({aug['rate'] * 100:.0f}%)"
        )
    if base and aug:
        delta = (aug["rate"] - base["rate"]) * 100
        lines.append(f"delta: {delta:+.0f}pp")
        lines.append(f"Custo total: ${base['cost'] + aug['cost']:.4f}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, choices=list(CONFIGS))
    args = parser.parse_args()

    stats = run_config(args.config)

    data = json.loads(_RESULTS_JSON.read_text()) if _RESULTS_JSON.exists() else {}
    data[args.config] = stats
    _RESULTS_JSON.write_text(json.dumps(data, indent=2))
    _RESULTS_MD.write_text(_render_results_md(data))
    print(f"\nwrote {_RESULTS_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
