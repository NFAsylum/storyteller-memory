"""Load and serve genre-organised story starters (audit 2.6).

Static content shipped in data/story_starters.json, validated on load so a malformed
file fails loudly instead of silently serving nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import RootModel

_STARTERS_PATH = Path(__file__).parent.parent / "data" / "story_starters.json"


class StoryStarters(RootModel[dict[str, list[str]]]):
    """genre -> list of opening lines."""


def load_story_starters() -> dict[str, list[str]]:
    raw = json.loads(_STARTERS_PATH.read_text(encoding="utf-8"))
    return StoryStarters.model_validate(raw).root


def starters_for(genre: str | None = None) -> dict[str, list[str]]:
    """All starters, or just one genre's (as a single-key dict) when genre is given."""
    data = load_story_starters()
    if genre is None:
        return data
    return {genre: data.get(genre, [])}
