"""Tests for eval.scenario — valid load, malformed JSON, and missing required field."""

import json
from pathlib import Path

import pytest

from eval.scenario import QuestionCategory, Scenario, ScenarioLoadError, load_scenario

_VALID = {
    "id": "escala-castelo-01",
    "scenes": [
        {"turn_id": 1, "user_input": "Introduzo Aria como cavaleira leal ao rei."},
        {"turn_id": 2, "user_input": "Aria descobre a traição do conselheiro Vex."},
    ],
    "questions": [
        {
            "id": "q1",
            "asked_after_turn": 10,
            "category": "recall_factual",
            "question": "Quem descobriu a traição de Vex?",
            "ground_truth": "Aria",
            "acceptable_variants": ["a cavaleira Aria", "Aria, a cavaleira"],
        }
    ],
}


def _write(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_valid_scenario(tmp_path: Path) -> None:
    scenario = load_scenario(_write(tmp_path, _VALID))

    assert isinstance(scenario, Scenario)
    assert scenario.id == "escala-castelo-01"
    assert len(scenario.scenes) == 2
    assert scenario.scenes[1].user_input.startswith("Aria descobre")
    q = scenario.questions[0]
    assert q.category is QuestionCategory.recall_factual
    assert q.ground_truth == "Aria"
    assert q.acceptable_variants == ["a cavaleira Aria", "Aria, a cavaleira"]


def test_acceptable_variants_defaults_to_empty(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(_VALID))
    del payload["questions"][0]["acceptable_variants"]
    scenario = load_scenario(_write(tmp_path, payload))
    assert scenario.questions[0].acceptable_variants == []


def test_malformed_json_fails_clearly(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{ not valid json ,,, ", encoding="utf-8")

    with pytest.raises(ScenarioLoadError, match="Malformed JSON"):
        load_scenario(path)


def test_question_without_ground_truth_fails_clearly(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(_VALID))
    del payload["questions"][0]["ground_truth"]

    with pytest.raises(ScenarioLoadError, match="failed validation"):
        load_scenario(_write(tmp_path, payload))


def test_unknown_category_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(json.dumps(_VALID))
    payload["questions"][0]["category"] = "vibes_check"

    with pytest.raises(ScenarioLoadError, match="failed validation"):
        load_scenario(_write(tmp_path, payload))


def test_missing_file_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(ScenarioLoadError, match="Cannot read"):
        load_scenario(tmp_path / "does_not_exist.json")
