"""Unit tests for the filter_config resolution layer.

Exercises the three-layer override stack (yaml defaults → persona → source)
without touching ConfigRegistry internals — we monkeypatch the defaults loader.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.config import filter_config as fc


@pytest.fixture(autouse=True)
def _stub_defaults(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "enabled": True,
        "strict": False,
        "tiers": {
            "heuristic": {"min_word_count": 40, "allowed_languages": ["en"]},
            "embedding": {"provider": None, "model": None},
            "llm": {"enabled": True},
        },
        "borderline_band": {"low": 0.45, "high": 0.65},
        "priority_buckets": {"high_threshold": 0.65, "low_threshold": 0.45},
        "excerpt_chars": 1200,
    }
    monkeypatch.setattr(fc, "load_defaults", lambda: defaults)
    return defaults


def test_defaults_only() -> None:
    cfg = fc.resolve_filter_config()
    assert cfg.enabled is True
    assert cfg.min_word_count == 40
    assert cfg.borderline_band.low == pytest.approx(0.45)
    assert cfg.llm_enabled is True


def test_persona_extends_defaults_with_interest_and_keywords() -> None:
    persona = {
        "name": "default",
        "description": "ai",
        "filter_profile": {
            "interest_description": "AI agents, production ML",
            "must_include": ["agents"],
            "must_exclude": ["press release"],
            "min_word_count": 60,
            "borderline_band": {"low": 0.5, "high": 0.7},
        },
    }
    cfg = fc.resolve_filter_config(persona=persona)
    assert cfg.interest_description == "AI agents, production ML"
    assert cfg.must_include == ("agents",)
    assert cfg.must_exclude == ("press release",)
    assert cfg.min_word_count == 60
    assert cfg.borderline_band.low == pytest.approx(0.5)


def test_persona_without_filter_profile_uses_description_as_interest() -> None:
    # Per design D3: missing filter_profile falls back to persona.description.
    persona = {"name": "x", "description": "data engineering"}
    cfg = fc.resolve_filter_config(persona=persona)
    assert cfg.interest_description == "data engineering"


def test_source_override_disables_filter() -> None:
    cfg = fc.resolve_filter_config(source_overrides={"enabled": False})
    assert cfg.enabled is False


def test_source_override_disables_tier_3_only() -> None:
    cfg = fc.resolve_filter_config(
        persona={
            "filter_profile": {"interest_description": "ai"},
        },
        source_overrides={"override_tier_3": False},
    )
    assert cfg.enabled is True
    assert cfg.llm_enabled is False
    assert cfg.interest_description == "ai"


def test_priority_bucket_thresholding() -> None:
    cfg = fc.resolve_filter_config()
    assert cfg.priority_bucket(0.9) == "high"
    assert cfg.priority_bucket(0.5) == "normal"
    assert cfg.priority_bucket(0.1) == "low"


def test_borderline_band_classify_helper() -> None:
    cfg = fc.resolve_filter_config()
    band = cfg.borderline_band
    assert band.classify(0.2) == "below"
    assert band.classify(0.55) == "borderline"
    assert band.classify(0.9) == "above"
