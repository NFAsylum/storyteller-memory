"""Pydantic shapes for the structured facts an LLM returns during reflection.

Lenient by design: unknown keys are ignored and every field has a default, so a
partially-formed model reply still validates instead of raising.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class _ExtractedCharacter(BaseModel):
    name: str
    traits: list[str] = Field(default_factory=list)
    first_appeared_turn: int = 0


class _CharacterUpdate(BaseModel):
    name: str
    new_traits: list[str] = Field(default_factory=list)
    evidence_turn: int = 0


class _ExtractedLocation(BaseModel):
    name: str
    description: str = ""
    first_visited_turn: int = 0


class _ExtractedRelation(BaseModel):
    a: str
    b: str
    kind: str
    valence: int = 0
    since_turn: int = 0


class _ExtractedBeat(BaseModel):
    summary: str
    importance: int = 1
    turn: int = 0
    tags: list[str] = Field(default_factory=list)


class ReflectionExtraction(BaseModel):
    """Structured facts the LLM returns; lenient (ignores unexpected keys)."""

    new_characters: list[_ExtractedCharacter] = Field(default_factory=list)
    character_updates: list[_CharacterUpdate] = Field(default_factory=list)
    new_locations: list[_ExtractedLocation] = Field(default_factory=list)
    relations: list[_ExtractedRelation] = Field(default_factory=list)
    beats: list[_ExtractedBeat] = Field(default_factory=list)
