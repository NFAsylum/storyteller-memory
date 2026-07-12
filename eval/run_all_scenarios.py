"""Run all scenarios (seed or extended set) under a named config; write results.md.

Usage:
  LLM_BACKEND=local poetry run python -m eval.run_all_scenarios --config=no_memory
  LLM_BACKEND=local poetry run python -m eval.run_all_scenarios --config=mem0_plus_reflection --set=extended

results.json is nested by scenario set: {"seed": {config: stats}, "extended": {...}}.
results.md renders both sets side by side once measured.
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

_SEEDS = ["seed_01.json", "seed_02.json", "seed_03.json"]
_SCEN_DIRS = {
    "seed": Path(__file__).parent / "scenarios",
    "extended": Path(__file__).parent / "scenarios" / "extended",
}
_SET_LABELS = {
    "seed": "Cenários curtos (5 turnos)",
    "extended": "Cenários estendidos (16 turnos)",
}
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


def run_config(config_name: str, scenario_set: str) -> dict[str, float | int]:
    config = HarnessConfig(name=config_name, **CONFIGS[config_name])
    llm = create_llm_client()
    engine = get_engine()
    Base.metadata.create_all(engine)
    session_factory = get_sessionmaker(engine)
    scen_dir = _SCEN_DIRS[scenario_set]

    correct = total = 0
    cost = 0.0
    print(f"== set: {scenario_set} | config: {config_name} ==")
    for seed in _SEEDS:
        scenario = load_scenario(scen_dir / seed)
        session_id = f"{scenario.id}--{config_name}"
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


def _reflection_delta(set_data: dict) -> float | None:
    base, aug = set_data.get("baseline_mem0_only"), set_data.get("mem0_plus_reflection")
    if base and aug:
        return (aug["rate"] - base["rate"]) * 100
    return None


def _render_results_md(data: dict[str, dict]) -> str:
    backend = os.environ.get("LLM_BACKEND", "fake")
    total_cost = sum(cfg["cost"] for set_data in data.values() for cfg in set_data.values())

    def pct(d: dict) -> str:
        return f"{d['correct']} of {d['total']} recall ({d['rate'] * 100:.0f}%)"

    lines = [
        "# Resultados — Storyteller",
        "",
        f"Backend: `{backend}` (Qwen2.5-Coder-7B via llama-server; `temperature=0`, `seed=42`). "
        "Recall julgado por containment com **word boundary** (`\\b<ground_truth>\\b`) + strip de "
        "pontuação — correção F1.1 do audit; antes era substring ingênua (`'Vex'` batia em "
        "`'Vexado'`). Mesmo judge pra todos os configs.",
        "",
        "> **Números corrigidos pós-audit (F1.1):** os valores abaixo já usam o judge com word "
        "boundary. Na versão anterior (substring ingênua) os números eram: cenários curtos "
        "no_memory 0% / mem0_only 90% / mem0+reflection 93%; estendidos 0% / 80% / 67%. O "
        "diferencial de portfólio (no_memory vs mem0_only) permanece grande após a correção.",
    ]

    for set_key in ("seed", "extended"):
        set_data = data.get(set_key)
        if not set_data:
            continue
        lines += ["", f"## {_SET_LABELS[set_key]} — recall (30 perguntas, 3 cenários)", ""]
        for cfg, label in (
            ("no_memory", "no_memory (LLM puro)"),
            ("baseline_mem0_only", "mem0_only"),
            ("mem0_plus_reflection", "mem0 + reflection"),
        ):
            if cfg in set_data:
                lines.append(f"- {label}: {pct(set_data[cfg])}")

    lines += ["", f"Custo total: ${total_cost:.4f} (backend local)"]

    seed = data.get("seed", {})
    none, base = seed.get("no_memory"), seed.get("baseline_mem0_only")
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

    delta_seed = _reflection_delta(data.get("seed", {}))
    delta_ext = _reflection_delta(data.get("extended", {}))
    if delta_seed is not None:
        note = [
            "",
            "## Nota metodológica — reflection vs mem0 cru",
            "",
            f"Delta mem0-only → mem0+reflection: curtos **{delta_seed:+.0f}pp**"
            + (f", estendidos **{delta_ext:+.0f}pp**." if delta_ext is not None else "."),
        ]
        if delta_ext is not None and delta_ext < 0:
            note += [
                "",
                "**Achado (negativo, mas honesto):** nos cenários longos a reflection **piorou** o "
                "recall. O mem0 recupera por similaridade e já traz as memórias cruas (limpas e "
                "corretas) relevantes; a reflection injeta fatos estruturados gerados pelo Qwen 7B "
                "local, que são ruidosos/imprecisos e mais longos — pro modelo pequeno isso distrai "
                "em vez de ajudar. Para a reflection compensar seria preciso (a) um modelo mais forte "
                "fazendo a consolidação, ou (b) perguntas de síntese pura onde a memória crua não "
                "basta. Sprint 4 avalia isso com as 5 categorias + judges subjetivos.",
            ]
        note += [
            "",
            'Comparação justa: os 3 configs usam o **mesmo** prompt de QA (que manda responder '
            '"não sei" quando o contexto não tem a resposta). No `no_memory` o modelo se abstém em vez '
            "de chutar, então o 0% reflete incapacidade genuína — o único fator que muda entre os "
            "configs é a presença (e a forma) da memória.",
        ]
        lines += note
    return "\n".join(lines) + "\n"


def _load_data() -> dict[str, dict]:
    if not _RESULTS_JSON.exists():
        return {}
    raw = json.loads(_RESULTS_JSON.read_text())
    # Migrate the old flat {config: stats} shape into {"seed": {...}}.
    if raw and all(key in CONFIGS for key in raw):
        return {"seed": raw}
    return raw


def main() -> int:
    parser = argparse.ArgumentParser()
    # 'all' runs every config in ONE process — the embedder stack import (~70s) is paid
    # once instead of once per process (the real bottleneck, not the LLM or vector ops).
    parser.add_argument("--config", required=True, choices=[*CONFIGS, "all"])
    parser.add_argument("--set", default="seed", choices=list(_SCEN_DIRS))
    args = parser.parse_args()

    configs = list(CONFIGS) if args.config == "all" else [args.config]
    data = _load_data()
    for config_name in configs:
        stats = run_config(config_name, args.set)
        data.setdefault(args.set, {})[config_name] = stats
        _RESULTS_JSON.write_text(json.dumps(data, indent=2))
        _RESULTS_MD.write_text(_render_results_md(data))

    print(f"\nwrote {_RESULTS_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
