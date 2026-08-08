"""Tests for origin-aware merge strategy selection.

Rebase is the default for every origin: commit history is documentation, and
collapsing it discards the ordering and rationale that make `git blame` and
`git bisect` useful later. ``ORIGIN_STRATEGY_MAP`` exists as the opt-out for
origins whose commits are known to carry nothing worth keeping — it is currently
empty, and these tests pin that so a re-introduced squash default is a visible
decision rather than a drive-by edit.

Covers spec scenarios:
- Agent-authored PR uses rebase-merge by default
- Dependency PR uses rebase-merge by default
- Automation PR uses rebase-merge by default
- Operator overrides default strategy via CLI flag
- Rebase-merge fails due to merge conflicts
"""

import sys
from pathlib import Path

import pytest

# Add scripts dir to path so we can import merge_pr
sys.path.insert(0, str(Path(__file__).parent.parent))

from merge_pr import ORIGIN_STRATEGY_MAP, get_default_strategy, resolve_strategy


class TestGetDefaultStrategy:
    """Every origin defaults to rebase unless explicitly opted out."""

    @pytest.mark.parametrize(
        "origin",
        [
            # Agent-authored: structured commits encoding design intent.
            "openspec",
            "codex",
            # Dependency bumps: usually one commit, so rebase and squash agree —
            # but when a bump carries a lockfile follow-up, both survive.
            "dependabot",
            "renovate",
            # Jules automation.
            "sentinel",
            "bolt",
            "palette",
            "jules",
            # Manual and unrecognized.
            "other",
            "unknown_thing",
        ],
    )
    def test_origin_defaults_to_rebase(self, origin: str) -> None:
        assert get_default_strategy(origin) == "rebase"

    def test_opt_out_map_is_empty(self) -> None:
        """A non-empty map means some origin was quietly returned to squash."""
        assert ORIGIN_STRATEGY_MAP == {}


class TestResolveStrategy:
    """Scenario: Operator overrides default strategy via CLI flag."""

    def test_explicit_strategy_overrides_origin(self) -> None:
        assert resolve_strategy(
            explicit_strategy="squash", origin="openspec",
        ) == "squash"

    def test_explicit_squash_overrides_dependabot(self) -> None:
        """The escape hatch for a PR whose history is genuinely noise."""
        assert resolve_strategy(
            explicit_strategy="squash", origin="dependabot",
        ) == "squash"

    def test_explicit_merge_overrides_any_origin(self) -> None:
        assert resolve_strategy(
            explicit_strategy="merge", origin="openspec",
        ) == "merge"

    def test_no_explicit_strategy_uses_origin_default(self) -> None:
        assert resolve_strategy(
            explicit_strategy=None, origin="openspec",
        ) == "rebase"

    def test_no_explicit_strategy_no_origin_falls_back_to_rebase(self) -> None:
        assert resolve_strategy(
            explicit_strategy=None, origin=None,
        ) == "rebase"

    def test_no_explicit_strategy_with_dependabot_uses_rebase(self) -> None:
        assert resolve_strategy(
            explicit_strategy=None, origin="dependabot",
        ) == "rebase"
