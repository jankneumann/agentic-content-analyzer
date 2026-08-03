from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.config.sources import (
    ObsidianVaultSource,
    RSSSource,
    SourcesConfig,
    configured_source_public_key,
    load_sources_config,
)
from src.contracts.workflow_models import StrictModel
from src.ingestion.commands import (
    ArxivPaperIngestCommand,
    ArxivSearchIngestCommand,
    FilesIngestCommand,
    ObsidianVaultIngestCommand,
    PerplexitySearchIngestCommand,
    PodcastIngestCommand,
    ReadwiseIngestCommand,
    RssIngestCommand,
    ScholarPaperIngestCommand,
    ScholarReferencesIngestCommand,
    UrlIngestCommand,
    YouTubePlaylistIngestCommand,
)
from src.ingestion.content_references import (
    _commit_session_content_references,
    _record_loaded_content_reference,
    _stage_session_content_references,
)
from src.ingestion.registry import (
    SourceDescriptor,
    SourceRegistry,
    configured_source_version,
)
from src.ingestion.result import (
    IngestionResponse,
    SourceFetchResult,
    build_response_from_source_results,
    public_source_key_for,
)
from src.ingestion.scholar import ScholarPaperResult
from src.ingestion.service import IngestionService
from src.models.content import Content, ContentSource, ContentStatus


def _response(
    command: str = "ingest.arxiv-paper",
    source: str = "arxiv_paper",
    *,
    details: dict | None = None,
    items_ingested: int = 1,
) -> IngestionResponse:
    return IngestionResponse(
        command=command,  # type: ignore[arg-type]
        source=source,  # type: ignore[arg-type]
        status="ok",
        items_ingested=items_ingested,
        details=details or {},
    )


def _publish_content(
    content_id: int,
    source: ContentSource,
    canonical_id: int | None = None,
) -> None:
    session = MagicMock()
    session.info = {}
    transaction = MagicMock(nested=False, parent=None)
    session.get_nested_transaction.return_value = None
    session.get_transaction.return_value = transaction
    session.new = {
        Content(
            id=content_id,
            source_type=source,
            source_id=f"{source.value}:{content_id}",
            title="Item",
            markdown_content="Body",
            content_hash=str(content_id),
            status=ContentStatus.PARSED,
            canonical_id=canonical_id,
        )
    }
    session.dirty = set()
    _stage_session_content_references(session, None)
    _commit_session_content_references(session)


def test_dispatch_preserves_arxiv_paper_options() -> None:
    service = IngestionService()
    command = ArxivPaperIngestCommand(
        identifier="2401.12345",
        extract_pdf=False,
        force_reprocess=True,
    )

    with patch(
        "src.ingestion.orchestrator.ingest_arxiv_paper",
        return_value=_response(),
    ) as orchestrator:
        result = service.execute(command)

    orchestrator.assert_called_once_with(
        identifier="2401.12345",
        pdf_extraction=False,
        force_reprocess=True,
    )
    assert result.details["command_key"] == "arxiv_paper"
    assert result.details["resolved_route"] == "arxiv_paper"
    assert result.details["emitted_sources"] == ["arxiv"]


def test_days_back_is_translated_to_an_aware_after_date() -> None:
    service = IngestionService()

    with patch(
        "src.ingestion.orchestrator.ingest_rss",
        return_value=_response("ingest.rss", "rss"),
    ) as orchestrator:
        before = datetime.now(UTC)
        service.execute({"kind": "rss", "max_items": 7, "days_back": 2})
        after = datetime.now(UTC)

    kwargs = orchestrator.call_args.kwargs
    assert kwargs["max_entries_per_feed"] == 7
    assert before.timestamp() - (2 * 86400) <= kwargs["after_date"].timestamp()
    assert kwargs["after_date"].timestamp() <= after.timestamp() - (2 * 86400)


def test_absolute_after_date_is_preserved_when_execution_is_delayed() -> None:
    service = IngestionService()
    lower_bound = datetime(2026, 7, 1, tzinfo=UTC)

    with patch(
        "src.ingestion.orchestrator.ingest_rss",
        return_value=_response("ingest.rss", "rss"),
    ) as orchestrator:
        service.execute({"kind": "rss", "after_date": lower_bound})

    assert orchestrator.call_args.kwargs["after_date"] == lower_bound


def test_queued_source_snapshot_is_used_instead_of_current_configuration() -> None:
    service = IngestionService(
        configured_source_key_secret="configured-source-key-secret-for-tests"
    )
    observed_urls: list[str] = []

    def execute_from_snapshot(**_kwargs):
        observed_urls.extend(source.url for source in load_sources_config().get_rss_sources())
        return _response("ingest.rss", "rss")

    with patch(
        "src.ingestion.orchestrator.ingest_rss",
        side_effect=execute_from_snapshot,
    ):
        service.execute(
            {
                "kind": "rss",
                "configured_sources": [{"type": "rss", "url": "https://queued.example/feed"}],
            }
        )

    assert observed_urls == ["https://queued.example/feed"]


class _SingleSourceCommand(StrictModel):
    kind: Literal["single"] = "single"
    source_key: str
    configured_source_version: str | None = None


def test_worker_enforces_exact_opaque_source_selection_from_settings_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    secret = "configured-source-key-secret-for-tests"
    first = RSSSource(url="https://private.example/one")
    selected = RSSSource(url="https://private.example/two")
    observed_urls: list[str] = []

    def orchestrate(_command):
        observed_urls.extend(source.url for source in load_sources_config().get_rss_sources())
        return _response("ingest.rss", "rss")

    registry = SourceRegistry(
        [
            SourceDescriptor(
                key="single",
                display_name="Single",
                command_model=_SingleSourceCommand,
                orchestrator=orchestrate,
                emitted_sources=frozenset({ContentSource.RSS}),
                scheduled=False,
                config_matcher=lambda source: isinstance(source, RSSSource),
                config_accessor=lambda config: config.get_rss_sources(),
            )
        ]
    )
    settings = SimpleNamespace(
        get_configured_source_key_secret=lambda: secret,
        get_sources_config=lambda: SourcesConfig(sources=[first, selected]),
    )
    settings_module = importlib.import_module("src.config.settings")
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    service = IngestionService(registry)

    service.execute(
        {
            "kind": "single",
            "source_key": configured_source_public_key(selected, secret=secret),
            "configured_source_version": configured_source_version(selected, secret=secret),
        }
    )

    assert observed_urls == ["https://private.example/two"]


def test_worker_rejects_opaque_key_not_present_in_private_snapshot() -> None:
    source = RSSSource(url="https://private.example/one")
    orchestrator = MagicMock(return_value=_response("ingest.rss", "rss"))
    registry = SourceRegistry(
        [
            SourceDescriptor(
                key="single",
                display_name="Single",
                command_model=_SingleSourceCommand,
                orchestrator=orchestrator,
                emitted_sources=frozenset({ContentSource.RSS}),
                scheduled=False,
                config_matcher=lambda value: isinstance(value, RSSSource),
                config_accessor=lambda config: config.get_rss_sources(),
            )
        ]
    )

    with pytest.raises(ValueError, match="Configured source is unavailable"):
        IngestionService(
            registry,
            configured_source_key_secret="configured-source-key-secret-for-tests",
            source_config_loader=lambda: SourcesConfig(sources=[source]),
        ).execute(
            {
                "kind": "single",
                "source_key": "src_0123456789abcdef0123",
                "configured_source_version": configured_source_version(
                    source,
                    secret="configured-source-key-secret-for-tests",
                ),
            }
        )

    orchestrator.assert_not_called()


def test_worker_rejects_stale_configured_source_version() -> None:
    secret = "configured-source-key-secret-for-tests"
    current = RSSSource(url="https://private.example/feed", max_entries=11)
    previous = RSSSource(url="https://private.example/feed", max_entries=10)
    orchestrator = MagicMock(return_value=_response("ingest.rss", "rss"))
    registry = SourceRegistry(
        [
            SourceDescriptor(
                key="single",
                display_name="Single",
                command_model=_SingleSourceCommand,
                orchestrator=orchestrator,
                emitted_sources=frozenset({ContentSource.RSS}),
                scheduled=False,
                config_matcher=lambda value: isinstance(value, RSSSource),
                config_accessor=lambda config: config.get_rss_sources(),
            )
        ]
    )

    with pytest.raises(ValueError, match="Configured source changed"):
        IngestionService(
            registry,
            configured_source_key_secret=secret,
            source_config_loader=lambda: SourcesConfig(sources=[current]),
        ).execute(
            {
                "kind": "single",
                "source_key": configured_source_public_key(current, secret=secret),
                "configured_source_version": configured_source_version(previous, secret=secret),
            }
        )

    orchestrator.assert_not_called()


def test_obsidian_command_dispatches_with_reloaded_one_source_configuration() -> None:
    secret = "configured-source-key-secret-for-tests"
    source = ObsidianVaultSource(vault_id="personal", vault_path="/srv/private/vault")
    command = ObsidianVaultIngestCommand(
        source_key=configured_source_public_key(source, secret=secret),
        configured_source_version=configured_source_version(source, secret=secret),
        max_items=7,
        force_reprocess=True,
    )
    response = IngestionResponse(
        command="ingest.obsidian-vault",
        source="obsidian",
        status="ok",
        items_ingested=1,
    )

    with patch(
        "src.ingestion.orchestrator.ingest_obsidian_vault",
        return_value=response,
    ) as orchestrator:
        result = IngestionService(
            configured_source_key_secret=secret,
            source_config_loader=lambda: SourcesConfig(sources=[source]),
        ).execute(command)

    orchestrator.assert_called_once_with(max_items=7, force_reprocess=True)
    assert result.details["command_key"] == "obsidian_vault"
    assert result.details["emitted_sources"] == ["obsidian"]


def test_ingestion_service_rejects_short_injected_source_key_secret() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        IngestionService(configured_source_key_secret="too-short")


def test_queued_source_snapshot_carries_ordered_public_identity_into_results() -> None:
    secret = "configured-source-key-secret-for-tests"
    source = RSSSource(url="https://user:pass@private.example/feed?token=hidden")
    service = IngestionService(configured_source_key_secret=secret)

    def execute_from_snapshot(**_kwargs):
        public_source_key = public_source_key_for(source)
        assert public_source_key is not None
        return build_response_from_source_results(
            command="ingest.rss",
            source="rss",
            items_ingested=2,
            source_results=[
                SourceFetchResult(
                    url=source.url,
                    items_fetched=2,
                    public_source_key=public_source_key,
                )
            ],
        )

    with patch(
        "src.ingestion.orchestrator.ingest_rss",
        side_effect=execute_from_snapshot,
    ):
        response = service.execute(
            {
                "kind": "rss",
                "configured_sources": [source.model_dump(mode="json")],
            }
        )

    assert [outcome.source_key for outcome in response.source_outcomes] == [
        configured_source_public_key(source, secret=secret)
    ]
    assert response.source_outcomes[0].items_ingested == 2


def test_queued_source_identity_count_mismatch_omits_unsafe_attribution() -> None:
    service = IngestionService(
        configured_source_key_secret="configured-source-key-secret-for-tests"
    )

    def execute_from_snapshot(**_kwargs):
        return build_response_from_source_results(
            command="ingest.rss",
            source="rss",
            items_ingested=1,
            source_results=[SourceFetchResult(url="https://one.example/feed", items_fetched=1)],
        )

    with patch(
        "src.ingestion.orchestrator.ingest_rss",
        side_effect=execute_from_snapshot,
    ):
        response = service.execute(
            {
                "kind": "rss",
                "configured_sources": [
                    {"type": "rss", "url": "https://one.example/feed"},
                    {"type": "rss", "url": "https://two.example/feed"},
                ],
            }
        )

    assert response.source_outcomes == []
    assert response.source_outcomes_omitted == 2


def test_invalid_queued_source_snapshot_fails_before_dispatch() -> None:
    service = IngestionService()

    with (
        patch("src.ingestion.orchestrator.ingest_rss") as orchestrator,
        pytest.raises(ValidationError),
    ):
        service.execute(
            {
                "kind": "rss",
                "configured_sources": [{"type": "rss"}],
            }
        )

    orchestrator.assert_not_called()


def test_queued_source_snapshot_must_match_command_descriptor() -> None:
    service = IngestionService()

    with (
        patch("src.ingestion.orchestrator.ingest_rss") as orchestrator,
        pytest.raises(ValueError, match="does not match command 'rss'"),
    ):
        service.execute(
            {
                "kind": "rss",
                "configured_sources": [{"type": "podcast", "url": "https://example.com/feed"}],
            }
        )

    orchestrator.assert_not_called()


@pytest.mark.parametrize(
    ("command", "orchestrator_name", "expected"),
    [
        (
            YouTubePlaylistIngestCommand(
                max_items=4,
                force_reprocess=True,
                public_only=True,
            ),
            "ingest_youtube_playlist",
            {"max_videos": 4, "force_reprocess": True, "use_oauth": False},
        ),
        (
            PodcastIngestCommand(
                max_items=5,
                force_reprocess=True,
                transcribe=False,
            ),
            "ingest_podcast",
            {
                "max_entries_per_feed": 5,
                "force_reprocess": True,
                "transcribe": False,
            },
        ),
        (
            PerplexitySearchIngestCommand(
                prompt="agent systems",
                max_items=6,
                recency="week",
                context_size="high",
                force_reprocess=True,
            ),
            "ingest_perplexity_search",
            {
                "prompt": "agent systems",
                "max_results": 6,
                "recency_filter": "week",
                "context_size": "high",
                "force_reprocess": True,
            },
        ),
        (
            ScholarReferencesIngestCommand(
                after=datetime(2026, 1, 1, tzinfo=UTC),
                before=datetime(2026, 2, 1, tzinfo=UTC),
                source_types=["rss", "gmail"],
                dry_run=True,
                limit=9,
            ),
            "ingest_scholar_refs",
            {
                "after": datetime(2026, 1, 1, tzinfo=UTC),
                "before": datetime(2026, 2, 1, tzinfo=UTC),
                "source_types": ["rss", "gmail"],
                "dry_run": True,
                "limit": 9,
            },
        ),
        (
            ArxivSearchIngestCommand(
                max_items=8,
                force_reprocess=True,
                extract_pdf=False,
            ),
            "ingest_arxiv",
            {
                "max_results": 8,
                "force_reprocess": True,
                "no_pdf": True,
            },
        ),
    ],
)
def test_source_specific_options_are_translated_without_loss(
    command,
    orchestrator_name: str,
    expected: dict,
) -> None:
    service = IngestionService()
    with patch(
        f"src.ingestion.orchestrator.{orchestrator_name}",
        return_value=_response(),
    ) as orchestrator:
        service.execute(command)

    assert orchestrator.call_args.kwargs == expected


def test_readwise_legacy_count_is_normalized_to_response() -> None:
    service = IngestionService()
    command = ReadwiseIngestCommand(
        updated_after=datetime(2026, 1, 1, tzinfo=UTC),
        source_types=["reader"],
        include_deleted=True,
        max_books=3,
        force_reprocess=True,
    )

    with patch("src.ingestion.orchestrator.ingest_readwise", return_value=2) as orchestrator:
        result = service.execute(command)

    orchestrator.assert_called_once_with(
        updated_after=datetime(2026, 1, 1, tzinfo=UTC),
        source_types=["reader"],
        include_deleted=True,
        max_books=3,
        force_reprocess=True,
    )
    assert result.command == "ingest.readwise"
    assert result.source == "readwise"
    assert result.items_ingested == 2


@pytest.mark.parametrize(
    ("url", "routing_mode", "resolved_route", "emitted_source"),
    [
        ("https://example.com/article", "auto", "webpage", "webpage"),
        ("https://example.com/feed", "auto", "rss_feed", "rss"),
        (
            "https://www.youtube.com/playlist?list=PLabc123",
            "auto",
            "youtube_playlist",
            "youtube",
        ),
        ("https://youtu.be/dQw4w9WgXcQ", "auto", "youtube_video", "youtube"),
        ("https://youtu.be/dQw4w9WgXcQ", "webpage", "webpage", "webpage"),
    ],
)
def test_url_dispatch_uses_classifier_and_normalizes_result(
    url: str,
    routing_mode: str,
    resolved_route: str,
    emitted_source: str,
) -> None:
    service = IngestionService()
    command = UrlIngestCommand(
        url=url,
        routing_mode=routing_mode,  # type: ignore[arg-type]
        tags=["agents"],
        force_reprocess=True,
    )

    with patch(
        "src.ingestion.orchestrator.ingest_url",
        return_value=_response(
            "ingest.url",
            "url",
            details={"content_id": 42, "routed_to": resolved_route},
        ),
    ) as orchestrator:
        result = service.execute(command)

    orchestrator.assert_called_once_with(
        url=url,
        tags=["agents"],
        auto_route=routing_mode == "auto",
        force_reprocess=True,
    )
    assert result.details["resolved_route"] == resolved_route
    assert result.details["emitted_sources"] == [emitted_source]
    assert result.details["content_ids"] == [42]


def test_unknown_kind_and_extra_option_fail_before_dispatch() -> None:
    service = IngestionService()

    with pytest.raises(ValueError, match="Unknown ingestion source"):
        service.execute({"kind": "not_real"})

    with pytest.raises(ValidationError, match="unsupported_option"):
        service.execute({"kind": "rss", "unsupported_option": True})


def test_files_command_resolves_durable_uploads_before_dispatch() -> None:
    upload_service = MagicMock()
    upload_service.materialize_sync.return_value.__enter__.return_value = [
        SimpleNamespace(
            path=Path("uploaded.md"),
            title="Uploaded title",
            publication="Internal",
        )
    ]
    service = IngestionService(upload_service=upload_service)

    with patch(
        "src.ingestion.orchestrator.ingest_files",
        return_value=_response("ingest.files", "files", details={"results": []}),
    ) as orchestrator:
        service.execute(FilesIngestCommand(upload_ids=["upl_manifest"], force_reprocess=True))

    upload_service.materialize_sync.assert_called_once_with(["upl_manifest"])
    assert orchestrator.call_args.kwargs["paths"] == [Path("uploaded.md")]
    assert orchestrator.call_args.kwargs["title"] == "Uploaded title"
    assert orchestrator.call_args.kwargs["publication"] == "Internal"
    assert orchestrator.call_args.kwargs["force_reprocess"] is True


def test_aggregate_rss_collects_committed_content_references() -> None:
    service = MagicMock()
    service.ingest_content.side_effect = lambda **_: (
        _publish_content(101, ContentSource.RSS) or _response("ingest.rss", "rss")
    )

    with patch("src.ingestion.rss.RSSContentIngestionService", return_value=service):
        result = IngestionService().execute(RssIngestCommand())

    assert result.details["content_ids"] == [101]


def test_deduplicated_rss_receipt_includes_preexisting_canonical_content() -> None:
    service = MagicMock()
    service.ingest_content.side_effect = lambda **_: (
        _record_loaded_content_reference(
            MagicMock(),
            Content(
                id=111,
                source_type=ContentSource.RSS,
                source_id="rss:existing",
                title="Existing",
                markdown_content="Body",
                content_hash="existing",
                status=ContentStatus.COMPLETED,
                canonical_id=7,
            ),
        )
        or _response("ingest.rss", "rss", items_ingested=0)
    )

    with patch("src.ingestion.rss.RSSContentIngestionService", return_value=service):
        result = IngestionService().execute(RssIngestCommand())

    assert result.items_ingested == 0
    assert result.details["content_ids"] == [7]


def test_response_alias_ids_are_normalized_to_collected_canonical_id() -> None:
    service = MagicMock()
    service.ingest_content.side_effect = lambda **_: (
        _publish_content(111, ContentSource.RSS, canonical_id=7)
        or _response(
            "ingest.rss",
            "rss",
            details={
                "content_id": 111,
                "results": [{"content_id": 111}, {"content_id": 7}],
            },
        )
    )

    with patch("src.ingestion.rss.RSSContentIngestionService", return_value=service):
        result = IngestionService().execute(RssIngestCommand())

    assert result.details["content_ids"] == [7]


@pytest.mark.parametrize(
    ("url", "source", "content_id"),
    [
        ("https://example.com/feed", ContentSource.RSS, 102),
        (
            "https://www.youtube.com/playlist?list=PLabc123",
            ContentSource.YOUTUBE,
            103,
        ),
    ],
)
def test_url_aggregate_routes_collect_committed_content_references(
    url: str,
    source: ContentSource,
    content_id: int,
) -> None:
    if source is ContentSource.RSS:
        rss = MagicMock()
        rss.ingest_content.side_effect = lambda **_: (
            _publish_content(content_id, source) or _response("ingest.rss", "rss")
        )
        target = patch("src.ingestion.rss.RSSContentIngestionService", return_value=rss)
    else:
        youtube = MagicMock()
        youtube.ingest_playlist = AsyncMock(
            side_effect=lambda *_args, **_kwargs: (
                _publish_content(content_id, source) or SourceFetchResult(url=url, items_fetched=1)
            )
        )
        target = patch(
            "src.ingestion.youtube.YouTubeContentIngestionService",
            return_value=youtube,
        )

    with target:
        result = IngestionService().execute(UrlIngestCommand(url=url))

    assert result.details["content_ids"] == [content_id]


def test_single_scholar_paper_collects_committed_content_reference() -> None:
    scholar = MagicMock()
    scholar.ingest_paper = AsyncMock(
        side_effect=lambda identifier, **_: (
            _publish_content(104, ContentSource.SCHOLAR)
            or ScholarPaperResult(identifier=identifier, paper_id="S2", ingested=True)
        )
    )
    scholar.close = AsyncMock()

    with patch(
        "src.ingestion.scholar.ScholarContentIngestionService",
        return_value=scholar,
    ):
        result = IngestionService().execute(ScholarPaperIngestCommand(identifier="10.1000/test"))

    assert result.details["content_ids"] == [104]
