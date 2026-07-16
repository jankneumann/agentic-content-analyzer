"""Generated vertical and mixed-source contracts derived from the executable registry."""

from __future__ import annotations

from itertools import combinations

import pytest

from src.ingestion.registry import SOURCE_REGISTRY
from tests.fixtures.sources.harness import (
    VerticalWorkflowHarness,
    assert_one_duplicate_alias,
    assert_provenance_invariants,
)
from tests.fixtures.sources.library import (
    SOURCE_FIXTURES,
    URL_VARIANTS,
    SourceFixtureRegistryError,
    assert_fixture_registry_complete,
)

REGISTRY_KEYS = SOURCE_REGISTRY.keys()
assert_fixture_registry_complete(set(REGISTRY_KEYS), set(SOURCE_FIXTURES))
SOURCE_PAIRS = tuple(combinations(REGISTRY_KEYS, 2))
HIGH_RISK_TRIPLES = (
    ("gmail", "rss", "substack"),
    ("scholar_search", "arxiv_search", "huggingface_papers"),
)


def test_fixture_registry_error_reports_missing_and_extra_keys() -> None:
    with pytest.raises(SourceFixtureRegistryError) as error:
        assert_fixture_registry_complete(
            {"gmail", "rss"},
            {"gmail", "invented"},
        )

    assert "missing=['rss']" in str(error.value)
    assert "extra=['invented']" in str(error.value)


@pytest.mark.contract
@pytest.mark.asyncio
@pytest.mark.parametrize("source_key", REGISTRY_KEYS)
async def test_every_registry_source_reaches_persisted_podcast_context(
    db_session, source_key: str
) -> None:
    result = await VerticalWorkflowHarness(db_session).run((source_key,))

    assert result.persisted[0].key == source_key
    assert result.persisted[0].command.kind == source_key
    assert result.persisted[0].ingestion.details == {
        "content_id": result.persisted[0].content_id,
        "results": [{"content_id": result.persisted[0].content_id}],
        "command_key": source_key,
        "resolved_route": result.persisted[0].route,
        "emitted_sources": [result.persisted[0].source.value],
        "content_ids": [result.persisted[0].content_id],
    }
    assert result.resolved.eligible_content_count == 1
    assert result.resolved.eligible_summary_count == 1
    assert result.canonical_references == frozenset(result.resolved.content_ids)
    assert_provenance_invariants(result)


@pytest.mark.contract
@pytest.mark.parametrize(
    ("variant", "command_data", "expected_route", "expected_source"),
    URL_VARIANTS,
)
def test_url_variants_share_normalized_command_and_resolved_route(
    variant: str,
    command_data: dict[str, object],
    expected_route: str,
    expected_source: str,
) -> None:
    command = SOURCE_REGISTRY.parse_command(command_data)
    descriptor = SOURCE_REGISTRY.get(command.kind)

    assert variant
    assert command.kind == "url"
    assert str(descriptor.resolve_route(command)) == expected_route
    assert {source.value for source in descriptor.resolve_sources(command)} == {expected_source}


@pytest.mark.contract
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("first_source", "second_source"),
    SOURCE_PAIRS,
    ids=lambda value: value,
)
async def test_every_unordered_source_pair_preserves_canonical_provenance(
    db_session, first_source: str, second_source: str
) -> None:
    result = await VerticalWorkflowHarness(db_session).run(
        (first_source, second_source),
        add_cross_source_alias=True,
    )

    assert len(SOURCE_PAIRS) == len(REGISTRY_KEYS) * (len(REGISTRY_KEYS) - 1) // 2
    assert result.resolved.eligible_content_count == 2
    assert result.canonical_references == frozenset(result.resolved.content_ids)
    assert_one_duplicate_alias(result)
    assert_provenance_invariants(result)


@pytest.mark.contract
@pytest.mark.asyncio
@pytest.mark.parametrize("source_keys", HIGH_RISK_TRIPLES, ids=("newsletter", "academic"))
async def test_high_risk_triples_preserve_source_filtered_digest_and_context(
    db_session, source_keys: tuple[str, str, str]
) -> None:
    harness = VerticalWorkflowHarness(db_session)
    all_sources = {
        next(
            iter(
                SOURCE_REGISTRY.get(key).resolve_sources(
                    SOURCE_REGISTRY.parse_command(SOURCE_FIXTURES[key].command)
                )
            )
        )
        for key in source_keys
    }
    selected_source = min(all_sources, key=lambda value: value.value)

    result = await harness.run(source_keys, selected_sources=(selected_source,))

    assert result.resolved.eligible_content_count == sum(
        item.source == selected_source for item in result.persisted
    )
    assert {item.source_type for item in result.resolved.items} == {selected_source}
    assert_provenance_invariants(result)
