"""S4.3: run 4 prompt/retrieval variants over the full scenarios; write experiments.md + best.yaml.

Deciding metric is recall_rate (containment — reliable, deterministic). consistency_score
and hallucination_rate use the LOCAL LLM judges and are INDICATIVE only (the 7B judge is
noisy, per the Sprint-3 reflection finding). Winner is picked by recall.

Run: LLM_BACKEND=local poetry run python -m eval.run_experiments
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from eval.harness import QA_PROMPTS, HarnessConfig, run_scenario
from eval.judges import LlmJudge
from eval.scenario import load_scenario

load_dotenv()

_FULL_DIR = Path(__file__).parent / "scenarios" / "full"
_SEEDS = ["full_01.json", "full_02.json", "full_03.json", "full_04.json", "full_05.json"]
_EXPERIMENTS_MD = Path("docs/experiments.md")
_BEST_YAML = Path("configs/best.yaml")


@dataclass(frozen=True)
class Variant:
    variant_id: str
    axis: str
    config: HarnessConfig
    qa: str


def _hc(name: str, **kw: Any) -> HarnessConfig:
    return HarnessConfig(name=name, use_retrieval=True, **kw)


VARIANTS = [
    Variant("qa_base", "prompt", _hc("qa_base", use_reflection=False, top_memories=5), "base"),
    Variant("qa_strict", "prompt", _hc("qa_strict", use_reflection=False, top_memories=5), "strict"),
    Variant("retr_reflection", "retrieval", _hc("retr_reflection", use_reflection=True, top_memories=5), "base"),
    Variant("retr_top2", "retrieval", _hc("retr_top2", use_reflection=False, top_memories=2), "base"),
]


def _reset_world(session, session_id: str) -> None:
    for model in (StoryBeat, Relation, Location, Character):
        session.execute(delete(model).where(model.session_id == session_id))
    session.commit()


def run_variant(variant: Variant, llm, judge: LlmJudge, session_factory) -> dict[str, Any]:
    correct = total = turns = 0
    cost = 0.0
    answers: list[tuple[Any, str]] = []
    print(f"== variant: {variant.variant_id} ({variant.axis}) ==")
    for seed in _SEEDS:
        scenario = load_scenario(_FULL_DIR / seed)
        session_id = f"{scenario.id}--{variant.variant_id}"
        memory = Mem0Adapter(session_id)
        with session_factory() as session:
            world = WorldState(session)
            _reset_world(session, session_id)
            result = run_scenario(
                scenario, variant.config, llm, memory, world, qa_system=QA_PROMPTS[variant.qa]
            )
        correct += result.correct
        total += result.total
        turns += result.n_turns
        cost += result.total_cost_usd
        answers.extend(result.answers)
        print(f"  {seed}: {result.correct} of {result.total}")

    # Indicative judged metrics (local 7B judge — noisy).
    hallucinated = sum(1 for q, a in answers if judge.judge_hallucination(q.ground_truth, a))
    consistency = [
        judge.judge_consistency(
            {"name": "", "traits": [q.ground_truth], "relations": [], "backstory": q.question}, a
        )
        for q, a in answers
        if q.category.value == "character_consistency"
    ]
    recall = correct / total if total else 0.0
    print(f"  recall {recall:.0%} | cost ${cost:.4f}")
    return {
        "variant_id": variant.variant_id,
        "axis": variant.axis,
        "recall_rate": recall,
        "consistency_score": sum(consistency) / len(consistency) if consistency else 0.0,
        "hallucination_rate": hallucinated / len(answers) if answers else 0.0,
        "avg_cost_per_turn": cost / turns if turns else 0.0,
        "variant": variant,
    }


def _write_experiments_md(rows: list[dict[str, Any]], winner: dict[str, Any]) -> None:
    backend = os.environ.get("LLM_BACKEND", "fake")
    lines = [
        "# Experiments — Storyteller",
        "",
        "## Sprint 4 (S4.3) — iteração de prompt + retrieval",
        "",
        f"Backend: `{backend}` (Qwen2.5-Coder-7B local). **Métrica de decisão: `recall_rate`** "
        "(containment — determinística e confiável). `consistency_score` e `hallucination_rate` "
        "vêm dos judges LLM locais e são **indicativos** (o 7B é ruidoso — ver achado da reflection "
        "no Sprint 3).",
        "",
        "Método: 4 variantes (2 no eixo prompt, 2 no eixo retrieval) rodadas sobre os 5 cenários "
        "`full` (30 perguntas). `qa_base` é a referência compartilhada.",
        "",
        "| variant_id | eixo | recall_rate | consistency_score\\* | hallucination_rate\\* | avg_cost_per_turn |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['variant_id']}` | {r['axis']} | {r['recall_rate'] * 100:.0f}% | "
            f"{r['consistency_score']:.2f} | {r['hallucination_rate'] * 100:.0f}% | "
            f"${r['avg_cost_per_turn']:.4f} |"
        )
    lines += [
        "",
        "\\* indicativo (judge LLM local ruidoso), não usado como critério de decisão.",
        "",
        "## Decisão",
        "",
        f"**Vencedor: `{winner['variant_id']}`** — maior `recall_rate` ({winner['recall_rate'] * 100:.0f}%). "
        "A decisão é pelo recall porque é a única métrica determinística/confiável aqui; os judges "
        "subjetivos rodam no mesmo 7B ruidoso e servem só de sinal. Config salva em `configs/best.yaml`.",
        "",
        "## Próximos experimentos sugeridos",
        "",
        "- Rodar os judges subjetivos num modelo mais forte (Anthropic) pra calibrar (S4.2).",
        "- Gate na reflection (só injetar fatos estruturados em histórico longo / alta confiança), "
        "dado que ela piorou o recall em cenários de 16 turnos.",
    ]
    _EXPERIMENTS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_best_yaml(winner: dict[str, Any]) -> None:
    cfg = winner["variant"].config
    _BEST_YAML.parent.mkdir(parents=True, exist_ok=True)
    _BEST_YAML.write_text(
        "# Config vencedora do S4.3 (escolhida por recall_rate)\n"
        f"name: {winner['variant_id']}\n"
        f"use_retrieval: {str(cfg.use_retrieval).lower()}\n"
        f"use_reflection: {str(cfg.use_reflection).lower()}\n"
        f"top_memories: {cfg.top_memories}\n"
        f"reflect_every: {cfg.reflect_every}\n"
        f"qa_prompt: {winner['variant'].qa}\n"
        f"recall_rate: {winner['recall_rate']:.4f}\n",
        encoding="utf-8",
    )


def main() -> int:
    llm = create_llm_client()
    judge = LlmJudge(llm)
    engine = get_engine()
    Base.metadata.create_all(engine)
    session_factory = get_sessionmaker(engine)

    rows = [run_variant(v, llm, judge, session_factory) for v in VARIANTS]
    winner = max(rows, key=lambda r: r["recall_rate"])

    _write_experiments_md(rows, winner)
    _write_best_yaml(winner)
    print(f"\nvencedor: {winner['variant_id']} (recall {winner['recall_rate']:.0%})")
    print(f"wrote {_EXPERIMENTS_MD} and {_BEST_YAML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
