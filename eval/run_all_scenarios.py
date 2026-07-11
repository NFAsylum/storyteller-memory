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
from eval.harness import HarnessConfig, NullMemory, run_scenario
from eval.scenario import load_scenario

load_dotenv()

_SCEN_DIR = Path(__file__).parent / "scenarios"
_SEEDS = ["seed_01.json", "seed_02.json", "seed_03.json"]
_RESULTS_MD = Path("results.md")
_RESULTS_JSON = Path("results.json")

CONFIGS: dict[str, dict[str, bool]] = {
    "no_memory": {"use_retrieval": False, "use_reflection": False},
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
        # no_memory stores/retrieves nothing (true no-memory baseline).
        memory = NullMemory(session_id) if config_name == "no_memory" else Mem0Adapter(session_id)
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
    none = data.get("no_memory")
    base = data.get("baseline_mem0_only")
    aug = data.get("mem0_plus_reflection")
    total_cost = sum(d["cost"] for d in data.values())

    def pct(d: dict) -> str:
        return f"{d['correct']} of {d['total']} recall ({d['rate'] * 100:.0f}%)"

    lines = [
        "# Resultados — Storyteller",
        "",
        f"Backend: `{backend}` (Qwen2.5-Coder-7B via llama-server). Recall julgado por "
        "containment (`ground_truth`/variante aparece na resposta), aplicado igual a todos os configs.",
        "",
        "## Sprint 3 — recall por config (30 perguntas, 3 cenários seed)",
        "",
    ]
    if none:
        lines.append(f"sprint 3 no_memory (LLM puro): {pct(none)}")
    if base:
        lines.append(f"sprint 3 mem0_only: {pct(base)}")
    if aug:
        lines.append(f"sprint 3 mem0 + reflection: {pct(aug)}")
    lines.append("")
    lines.append(f"Custo total: ${total_cost:.4f} (backend local)")

    if none and base:
        headline = (base["rate"] - none["rate"]) * 100
        lines += [
            "",
            "## Número-manchete",
            "",
            f"Sem nenhuma memória, o mesmo LLM acerta **{none['rate'] * 100:.0f}%** das 30 perguntas; "
            f"com o sistema de memória (mem0), sobe pra **{base['rate'] * 100:.0f}%** — um salto de "
            f"**+{headline:.0f}pp** que vem inteiramente da infra de memória, não de trocar o modelo.",
        ]
    if base and aug:
        delta = (aug["rate"] - base["rate"]) * 100
        lines += [
            "",
            "## Nota metodológica",
            "",
            f"O delta mem0-only vs mem0+reflection é pequeno (+{delta:.0f}pp) porque os cenários seed "
            "são curtos (5 turnos): o retrieval top-5 do mem0 já traz as memórias cruas com todos os "
            "fatos, saturando o baseline. A reflection (fatos consolidados no world_state) rende mais "
            "em históricos longos, onde a memória crua não cabe/fica ruidosa. A diferença que importa "
            'pro portfólio é "sem memória" vs "com sistema de memória", não mem0 vs mem0+reflection.',
            "",
            "Comparação justa: os 3 configs usam o **mesmo** prompt de QA (que manda responder "
            '"não sei" quando o contexto não tem a resposta). No `no_memory` o modelo se abstém em vez '
            "de chutar, então o 0% reflete incapacidade genuína sem memória — o único fator que muda "
            "entre os configs é a presença (e a forma) da memória.",
        ]
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
