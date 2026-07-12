"""Scenario/Scene/Question Pydantic models and the JSON loader for eval scenarios.

Just the data shape — no harness yet (that's S1.4's successor). A scenario is a fixed
sequence of story turns (scenes) plus questions asked after specific turns to measure
recall/consistency/etc.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class QuestionCategory(str, Enum):
    """The five measured dimensions (see docs/tasks.md S3.1)."""

    recall_factual = "recall_factual"
    character_consistency = "character_consistency"
    relation_evolution = "relation_evolution"
    world_state = "world_state"
    controlled_forgetting = "controlled_forgetting"


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: int
    user_input: str


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    asked_after_turn: int
    category: QuestionCategory
    question: str
    ground_truth: str
    acceptable_variants: list[str] = Field(default_factory=list)


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    scenes: list[Scene]
    questions: list[Question]


class ScenarioLoadError(Exception):
    """Raised when a scenario file can't be read, isn't valid JSON, or fails the model."""


def load_scenario(path: str | Path) -> Scenario:
    """Read a scenario JSON file and validate it against the Scenario model."""
    file_path = Path(path)
    try:
        raw = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScenarioLoadError(f"Cannot read scenario file {file_path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScenarioLoadError(f"Malformed JSON in {file_path}: {exc}") from exc
    try:
        return Scenario.model_validate(data)
    except ValidationError as exc:
        raise ScenarioLoadError(f"Scenario {file_path} failed validation:\n{exc}") from exc
