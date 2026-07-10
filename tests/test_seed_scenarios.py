"""Validates the committed seed scenarios against the Scenario model (S1.5 DoD)."""

from pathlib import Path

import pytest

from eval.scenario import load_scenario

_SEED_DIR = Path(__file__).resolve().parent.parent / "eval" / "scenarios"
_SEEDS = sorted(_SEED_DIR.glob("seed_*.json"))


def test_three_seed_files_exist() -> None:
    assert [p.name for p in _SEEDS] == ["seed_01.json", "seed_02.json", "seed_03.json"]


@pytest.mark.parametrize("path", _SEEDS, ids=lambda p: p.name)
def test_seed_validates_and_has_expected_shape(path: Path) -> None:
    scenario = load_scenario(path)  # raises ScenarioLoadError if invalid

    assert len(scenario.scenes) == 5
    assert len(scenario.questions) == 10
    for question in scenario.questions:
        assert question.ground_truth.strip() != ""
        assert question.category is not None
