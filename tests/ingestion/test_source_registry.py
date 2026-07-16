from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.config.sources import (
    GmailSource,
    ReadwiseSource,
    RSSSource,
    SourcesConfig,
    WebSearchSource,
    YouTubeChannelSource,
    load_sources_config,
)
from src.ingestion.commands import UrlIngestCommand
from src.ingestion.registry import SOURCE_REGISTRY, SourceRegistry
from src.ingestion.url_router import RouteKind
from src.models.content import ContentSource

EXPECTED_SOURCE_KEYS = {
    "gmail",
    "rss",
    "blog",
    "substack",
    "youtube_playlist",
    "youtube_rss",
    "podcast",
    "x_search",
    "perplexity_search",
    "files",
    "url",
    "scholar_search",
    "scholar_paper",
    "scholar_references",
    "arxiv_search",
    "arxiv_paper",
    "huggingface_papers",
    "readwise",
}


def test_default_registry_contains_complete_canonical_descriptor_set() -> None:
    assert set(SOURCE_REGISTRY.keys()) == EXPECTED_SOURCE_KEYS

    for descriptor in SOURCE_REGISTRY:
        assert descriptor.key
        assert descriptor.display_name
        assert descriptor.command_model.model_fields["kind"].default == descriptor.key
        assert descriptor.orchestrator is not None
        assert descriptor.emitted_sources
        assert descriptor.retry_policy.max_attempts >= 1
        assert 429 in descriptor.retry_policy.retryable_status_codes
        assert descriptor.transports == frozenset({"cli", "http", "mcp", "frontend"})


def test_url_descriptor_declares_and_resolves_every_possible_source() -> None:
    descriptor = SOURCE_REGISTRY.get("url")

    assert descriptor.emitted_sources == frozenset(
        {ContentSource.WEBPAGE, ContentSource.RSS, ContentSource.YOUTUBE}
    )
    assert descriptor.resolve_sources(
        UrlIngestCommand(url="https://example.com/feed")
    ) == frozenset({ContentSource.RSS})
    assert (
        descriptor.resolve_route(UrlIngestCommand(url="https://youtu.be/dQw4w9WgXcQ"))
        == RouteKind.YOUTUBE_VIDEO
    )
    assert (
        descriptor.resolve_route(
            UrlIngestCommand(
                url="https://youtu.be/dQw4w9WgXcQ",
                routing_mode="webpage",
            )
        )
        == RouteKind.WEBPAGE
    )


@pytest.mark.parametrize("field", ["key", "aliases"])
def test_registry_rejects_duplicate_keys_and_aliases(field: str) -> None:
    rss = SOURCE_REGISTRY.get("rss")
    blog = SOURCE_REGISTRY.get("blog")
    duplicate = replace(blog, **{field: rss.key if field == "key" else frozenset({rss.key})})

    with pytest.raises(ValueError, match="rss|blog"):
        SourceRegistry([rss, duplicate])


def test_registry_rejects_empty_emitted_source_set() -> None:
    rss = SOURCE_REGISTRY.get("rss")

    with pytest.raises(ValueError, match="emitted_sources"):
        SourceRegistry([replace(rss, emitted_sources=frozenset())])


def test_removed_legacy_key_has_actionable_diagnostic() -> None:
    diagnostics = {
        "youtube": "youtube_playlist.*youtube_rss",
        "youtube-playlist": "youtube_playlist",
        "youtube-rss": "youtube_rss",
        "perplexity": "perplexity_search",
        "perplexity-search": "perplexity_search",
    }
    for key, replacement in diagnostics.items():
        with pytest.raises(KeyError, match=replacement):
            SOURCE_REGISTRY.get(key)


def test_every_enabled_config_model_maps_to_exactly_one_descriptor() -> None:
    config = SourcesConfig(
        sources=[
            RSSSource(url="https://example.com/feed"),
            YouTubeChannelSource(channel_id="UC123"),
            WebSearchSource(provider="grok", prompt="AI"),
            WebSearchSource(provider="perplexity", prompt="agents"),
            ReadwiseSource(),
        ]
    )

    SOURCE_REGISTRY.validate_config(config)
    discovered = SOURCE_REGISTRY.configured_sources(config)

    assert [item.command_key for item in discovered] == [
        "rss",
        "youtube_playlist",
        "x_search",
        "perplexity_search",
        "readwise",
    ]
    assert discovered[-1].configuration["type"] == "readwise"
    assert "url" not in discovered[-1].configuration


def test_scheduled_accessors_return_each_enabled_config_once() -> None:
    config = SourcesConfig(
        sources=[
            RSSSource(url="https://example.com/feed"),
            YouTubeChannelSource(channel_id="UC123"),
            WebSearchSource(provider="grok", prompt="AI"),
            WebSearchSource(provider="perplexity", prompt="agents"),
            ReadwiseSource(enabled=False),
        ]
    )

    discovered = SOURCE_REGISTRY.scheduled_sources(config)

    assert [item.command_key for item in discovered] == [
        "rss",
        "youtube_playlist",
        "x_search",
        "perplexity_search",
    ]
    assert all(item.configuration["enabled"] for item in discovered)


def test_registry_plans_typed_scheduled_commands_and_applies_source_filter() -> None:
    config = SourcesConfig(
        sources=[
            RSSSource(url="https://example.com/one", max_entries=12),
            RSSSource(url="https://example.com/two", max_entries=8),
            WebSearchSource(provider="grok", prompt="first", max_threads=3),
            WebSearchSource(provider="grok", prompt="second", max_threads=4),
        ]
    )

    commands = SOURCE_REGISTRY.plan_scheduled_commands(
        config,
        sources=["rss", "x_search"],
        period_start=datetime(2026, 7, 1, tzinfo=UTC),
        period_end=datetime(2026, 7, 3, tzinfo=UTC),
    )

    assert [command.kind for command in commands] == ["rss", "x_search", "x_search"]
    assert commands[0].model_dump(mode="json") == {
        "kind": "rss",
        "configured_sources": [
            source.model_dump(mode="json") for source in config.get_rss_sources()
        ],
        "max_items": 12,
        "days_back": None,
        "after_date": "2026-07-01T00:00:00Z",
        "force_reprocess": False,
    }
    assert [command.prompt for command in commands[1:]] == ["first", "second"]


def test_registry_absolute_lower_bound_does_not_drift_while_command_is_queued() -> None:
    config = SourcesConfig(sources=[RSSSource(url="https://example.com/feed")])

    commands = SOURCE_REGISTRY.plan_scheduled_commands(
        config,
        sources=["rss"],
        period_start=datetime(2026, 7, 1, tzinfo=UTC),
        period_end=datetime(2026, 7, 2, tzinfo=UTC),
    )

    serialized = commands[0].model_dump(mode="json")
    assert serialized["after_date"] == "2026-07-01T00:00:00Z"
    assert serialized["days_back"] is None
    assert serialized["configured_sources"][0]["url"] == "https://example.com/feed"

    parsed_later = SOURCE_REGISTRY.parse_command(serialized)
    assert parsed_later.after_date == datetime(2026, 7, 1, tzinfo=UTC)


def test_registry_plans_each_configured_gmail_query() -> None:
    config = SourcesConfig(
        sources=[
            GmailSource(query="label:first", max_results=5),
            GmailSource(query="label:second", max_results=7),
        ]
    )

    commands = SOURCE_REGISTRY.plan_scheduled_commands(
        config,
        sources=["gmail"],
        period_start=datetime(2026, 7, 1, tzinfo=UTC),
        period_end=datetime(2026, 7, 2, tzinfo=UTC),
    )

    assert [command.query for command in commands] == ["label:first", "label:second"]
    assert [command.max_items for command in commands] == [5, 7]
    assert [len(command.configured_sources or []) for command in commands] == [1, 1]


def test_registry_rejects_disabled_unknown_and_unscheduled_pipeline_sources() -> None:
    config = SourcesConfig(sources=[RSSSource(url="https://example.com", enabled=False)])
    kwargs = {
        "config": config,
        "period_start": datetime(2026, 7, 1, tzinfo=UTC),
        "period_end": datetime(2026, 7, 2, tzinfo=UTC),
    }

    with pytest.raises(ValueError, match="not enabled"):
        SOURCE_REGISTRY.plan_scheduled_commands(sources=["rss"], **kwargs)
    with pytest.raises(ValueError, match="Unknown ingestion source"):
        SOURCE_REGISTRY.plan_scheduled_commands(sources=["nope"], **kwargs)
    with pytest.raises(ValueError, match="not scheduled"):
        SOURCE_REGISTRY.plan_scheduled_commands(sources=["url"], **kwargs)


def test_loading_source_config_runs_registry_validation(tmp_path, monkeypatch) -> None:
    source_file = tmp_path / "sources.yaml"
    source_file.write_text(
        "version: '1.0'\nsources:\n  - type: rss\n    url: https://example.com/feed\n"
    )
    registry = MagicMock()
    monkeypatch.setattr("src.ingestion.registry.SOURCE_REGISTRY", registry)
    monkeypatch.setattr(
        "src.config.sources._apply_db_source_overrides",
        lambda config: config,
    )

    config = load_sources_config(
        sources_dir=str(tmp_path / "missing"),
        sources_file=str(source_file),
    )

    registry.validate_config.assert_called_once_with(config)
