"""Tests for the story-starter library (T2.3 / audit 2.6)."""

from core.story_starters import load_story_starters, starters_for

_GENRES = {"fantasy", "scifi", "horror", "mystery", "romance", "literary", "comedy"}


def test_loads_and_covers_every_genre() -> None:
    data = load_story_starters()
    assert set(data) == _GENRES
    assert all(isinstance(v, list) and v for v in data.values())


def test_all_starters_are_nonempty_strings() -> None:
    for starters in load_story_starters().values():
        assert all(isinstance(s, str) and s.strip() for s in starters)


def test_starters_for_single_genre() -> None:
    result = starters_for("fantasy")
    assert set(result) == {"fantasy"}
    assert len(result["fantasy"]) >= 3


def test_starters_for_unknown_genre_is_empty() -> None:
    assert starters_for("nope") == {"nope": []}
