"""Count questions across the full scenario set. Run: python -m eval.count_questions"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from eval.scenario import load_scenario

_FULL_DIR = Path(__file__).parent / "scenarios" / "full"


def count() -> tuple[int, Counter[str]]:
    by_category: Counter[str] = Counter()
    total = 0
    for path in sorted(_FULL_DIR.glob("*.json")):
        scenario = load_scenario(path)
        total += len(scenario.questions)
        for question in scenario.questions:
            by_category[question.category.value] += 1
    return total, by_category


def main() -> int:
    total, by_category = count()
    n_files = len(list(_FULL_DIR.glob("*.json")))
    print(f"{n_files} cenários em eval/scenarios/full/")
    for category, n in sorted(by_category.items()):
        print(f"  {category}: {n}")
    print(total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
