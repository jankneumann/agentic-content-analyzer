"""Registry-completeness guard for the real-ingestion tiers.

Spec: ``openspec/changes/real-ingestion-test-tiers-in-ci/specs/real-ingestion-ci/spec.md``
Requirement: "Every source registry entry maps to a fixture tier or a reviewed
exclusion."

The module-level call below runs at *collection* time (pytest imports the module
before applying ``-m`` deselection), so a registry source added without either a
fixture or a documented exclusion breaks collection everywhere — not just in the
real-ingestion job.
"""

from __future__ import annotations

import pytest

from src.ingestion.registry import SOURCE_REGISTRY
from tests.fixtures.sources.library import (
    FIXTURE_EXCLUSIONS,
    SOURCE_FIXTURES,
    SourceFixtureRegistryError,
    assert_fixture_registry_complete,
)

# Collection-time guard on the real, current registry (must always hold).
assert_fixture_registry_complete(
    set(SOURCE_REGISTRY.keys()), set(SOURCE_FIXTURES), FIXTURE_EXCLUSIONS
)

pytestmark = pytest.mark.real_ingest


def test_real_registry_is_fully_covered() -> None:
    """Every executable source has a fixture or a reviewed exclusion, no stragglers."""

    assert_fixture_registry_complete(
        set(SOURCE_REGISTRY.keys()), set(SOURCE_FIXTURES), FIXTURE_EXCLUSIONS
    )


def test_new_registry_source_without_fixture_or_exclusion_fails() -> None:
    """A registry source with neither a fixture nor an exclusion breaks collection."""

    with pytest.raises(SourceFixtureRegistryError) as error:
        assert_fixture_registry_complete(
            {"gmail", "rss", "brand_new_source"},
            {"gmail", "rss"},
            {},
        )

    assert "missing=['brand_new_source']" in str(error.value)


def test_exclusion_naming_unknown_source_fails() -> None:
    """An exclusion for a source absent from the registry is a stale exclusion."""

    with pytest.raises(SourceFixtureRegistryError) as error:
        assert_fixture_registry_complete(
            {"gmail", "rss"},
            {"gmail", "rss"},
            {"retired_source": "removed in a past release"},
        )

    assert "stale_exclusions=['retired_source']" in str(error.value)


def test_reviewed_exclusion_satisfies_coverage() -> None:
    """A registry source covered only by a reviewed exclusion passes."""

    assert_fixture_registry_complete(
        {"gmail", "rss", "manual_only"},
        {"gmail", "rss"},
        {"manual_only": "operator-only source with no automatable fixture"},
    )
