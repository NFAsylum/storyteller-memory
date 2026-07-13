"""Tests for SessionConfig + the prompt directives derived from it (T2.1/T1.2 mechanics)."""

from core.session_config import SessionConfig, max_tokens_for, prompt_directives
from core.story_loop import load_prompt_template, render_prompt


def test_defaults() -> None:
    config = SessionConfig()
    assert config.genre == "fantasy"
    assert config.pov == "third_limited"
    assert config.tone == "serious"
    assert config.content_intensity == "sfw"
    assert config.target_length == "medium"


def test_prompt_directives_has_all_keys_nonempty() -> None:
    directives = prompt_directives(SessionConfig())
    assert set(directives) == {
        "genre",
        "tone",
        "pov",
        "target_length",
        "content_intensity",
        "protagonist",
    }
    assert all(isinstance(v, str) and v for v in directives.values())


def test_directives_change_with_genre_and_pov() -> None:
    assert (
        prompt_directives(SessionConfig(genre="fantasy"))["genre"]
        != prompt_directives(SessionConfig(genre="scifi"))["genre"]
    )
    assert "first person" in prompt_directives(SessionConfig(pov="first_person"))["pov"]


def test_max_tokens_scales_with_length() -> None:
    assert max_tokens_for(SessionConfig(target_length="brief")) < max_tokens_for(
        SessionConfig(target_length="long")
    )


def test_render_prompt_fills_every_placeholder() -> None:
    prompt = render_prompt(load_prompt_template(), None, "Aria entra.", SessionConfig(pov="first_person"))
    assert "{" not in prompt and "}" not in prompt  # no unfilled placeholders
    assert "first person" in prompt  # POV directive reached the prompt
    assert "Aria entra." in prompt


def test_protagonist_directive_uses_name_when_playing() -> None:
    directive = prompt_directives(
        SessionConfig(
            protagonist={"role": "protagonist", "character_name": "Aria", "character_role": "knight"}
        )
    )["protagonist"]
    assert "Aria" in directive
    assert "knight" in directive


def test_protagonist_directive_defaults_to_author() -> None:
    assert "author" in prompt_directives(SessionConfig())["protagonist"].lower()


def test_render_prompt_reflects_genre_choice() -> None:
    template = load_prompt_template()
    fantasy = render_prompt(template, None, "x", SessionConfig(genre="fantasy"))
    scifi = render_prompt(template, None, "x", SessionConfig(genre="scifi"))
    assert fantasy != scifi  # the same input produces a different prompt per genre
