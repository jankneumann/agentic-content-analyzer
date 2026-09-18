"""One setting, one section: a key in two sections resolves to the wrong one.

``_flatten_profile_to_settings`` walks the profile's sections in a fixed order
and writes each key into one flat namespace, so the last section carrying a
key wins no matter which section the value belongs to. The base profile kept
``langfuse_base_url`` under ``api_keys``, which is flattened after
``observability``, so every profile that pointed Langfuse at a self-hosted
instance was silently overridden with the cloud URL. On GX-10 that meant the
roles tried to ship traces to us.cloud.langfuse.com, where the egress proxy
refused the CONNECT and every export ended in a 403 traceback.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.config.profiles import load_profile
from src.config.settings import _flatten_profile_to_settings

PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"
PROFILE_NAMES = sorted(path.stem for path in PROFILES_DIR.glob("*.yaml"))


def _sections(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    settings = profile.get("settings", {})
    return {
        name: data for name, data in settings.items() if isinstance(data, dict) and name != "gx10"
    }


@pytest.mark.parametrize("name", PROFILE_NAMES)
def test_no_setting_is_declared_in_two_sections_at_once(name: str) -> None:
    """A key in two sections is decided by flatten order, not by intent."""
    raw = yaml.safe_load((PROFILES_DIR / name).with_suffix(".yaml").read_text(encoding="utf-8"))
    owners: dict[str, list[str]] = {}
    for section, data in _sections(raw or {}).items():
        for key in data:
            owners.setdefault(str(key), []).append(section)
    shared = {key: sections for key, sections in owners.items() if len(sections) > 1}
    assert not shared, f"{name}: declared in more than one section: {shared}"


def test_langfuse_points_where_each_profile_says_it_does() -> None:
    """The self-hosted profiles must not resolve to Langfuse Cloud."""
    os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
    for name, expected in (
        ("local", "http://localhost:3100"),
        ("local-langfuse", "http://localhost:3100"),
    ):
        flat = _flatten_profile_to_settings(load_profile(name).model_dump())
        assert flat["langfuse_base_url"] == expected, name
