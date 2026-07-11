"""Validates the full scenario set (S4.1): 5 files, 30 questions, 5-category distribution."""

from pathlib import Path

import pytest

from eval.count_questions import count
from eval.scenario import load_scenario

_FULL_DIR = Path(__file__).resolve().parent.parent / "eval" / "scenarios" / "full"
_FULL = sorted(_FULL_DIR.glob("*.json"))

_EXPECTED_CATEGORIES = {
    "recall_factual": 10,
    "character_consistency": 6,
    "relation_evolution": 6,
    "world_state": 4,
    "controlled_forgetting": 4,
}


def test_five_full_files_exist() -> None:
    assert len(_FULL) == 5


@pytest.mark.parametrize("path", _FULL, ids=lambda p: p.name)
def test_each_full_scenario_validates(path: Path) -> None:
    scenario = load_scenario(path)  # raises ScenarioLoadError if invalid
    assert len(scenario.questions) == 6
    for question in scenario.questions:
        assert question.ground_truth.strip() != ""
        assert question.category is not None


def test_total_is_thirty_with_expected_category_split() -> None:
    total, by_category = count()
    assert total == 30
    assert dict(by_category) == _EXPECTED_CATEGORIES
