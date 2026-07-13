"""Session-level narrative controls (genre / POV / tone / intensity / length).

The user picks these in the setup wizard; `StoryLoop` turns them into directives that
steer the continuation prompt. Stored as a plain JSON dict on the session so the schema
stays portable (SQLite -> Postgres).

The directive STRINGS below are a first draft: the mechanics (placeholders, wiring,
max_tokens) are final, but the exact wording is meant to be tuned by a human against
the real model — see docs/pending-human-tuning.md.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Genre = Literal["fantasy", "scifi", "horror", "mystery", "romance", "literary", "comedy"]
Pov = Literal["first_person", "third_limited", "third_omniscient"]
Tone = Literal["serious", "comedic", "gothic", "cyberpunk", "cozy", "dark"]
ContentIntensity = Literal["sfw", "mature", "dark"]
TargetLength = Literal["brief", "medium", "long"]


class SessionConfig(BaseModel):
    """Narrative knobs persisted per session (all optional, sensible defaults)."""

    genre: Genre = "fantasy"
    pov: Pov = "third_limited"
    tone: Tone = "serious"
    content_intensity: ContentIntensity = "sfw"
    target_length: TargetLength = "medium"


# --- DRAFT directive strings (tune wording against the model; keep the keys) ---------

_GENRE_DIRECTIVE: dict[str, str] = {
    "fantasy": "high-fantasy: magic, myth, courtly intrigue — concrete sensory detail.",
    "scifi": "science-fiction: technology or near-future stakes grounded in specific, plausible detail.",
    "horror": "horror: dread built from specific, mundane wrongness — not gore or vague menace.",
    "mystery": "mystery: clues, motives, misdirection; every scene advances the question.",
    "romance": "romance: interiority and tension; chemistry shown through action and subtext.",
    "literary": "literary: character interiority, precise language, restraint; theme over plot.",
    "comedy": "comedy: timing, escalation, specificity; earn the laugh with concrete absurdity.",
}

_TONE_DIRECTIVE: dict[str, str] = {
    "serious": "measured, sincere register.",
    "comedic": "light, witty register.",
    "gothic": "gothic register: decay, dread, ornate but controlled.",
    "cyberpunk": "cyberpunk register: neon, grit, corporate menace.",
    "cozy": "cozy register: warm, low-stakes, comforting detail.",
    "dark": "dark register: bleak, unflinching, morally grey.",
}

_POV_DIRECTIVE: dict[str, str] = {
    "first_person": "Write in first person (I/me), the protagonist's voice.",
    "third_limited": "Write in third person limited, close to one character's perspective.",
    "third_omniscient": "Write in third person omniscient, aware of all characters.",
}

_LENGTH_DIRECTIVE: dict[str, str] = {
    "brief": "Keep the response short: 80-150 words.",
    "medium": "Keep the response medium: 200-400 words.",
    "long": "Write a longer passage: 500+ words.",
}

_INTENSITY_DIRECTIVE: dict[str, str] = {
    "sfw": "Keep content safe-for-work.",
    "mature": "Mature themes allowed; avoid gratuitous explicitness.",
    "dark": "Dark, intense themes allowed in service of the story.",
}

_LENGTH_MAX_TOKENS: dict[str, int] = {"brief": 300, "medium": 700, "long": 1200}


def prompt_directives(config: SessionConfig) -> dict[str, str]:
    """Placeholder values for the continuation template, derived from the config."""
    return {
        "genre": _GENRE_DIRECTIVE.get(config.genre, config.genre),
        "tone": _TONE_DIRECTIVE.get(config.tone, config.tone),
        "pov": _POV_DIRECTIVE.get(config.pov, config.pov),
        "target_length": _LENGTH_DIRECTIVE.get(config.target_length, ""),
        "content_intensity": _INTENSITY_DIRECTIVE.get(config.content_intensity, ""),
    }


def max_tokens_for(config: SessionConfig) -> int:
    return _LENGTH_MAX_TOKENS.get(config.target_length, 700)
