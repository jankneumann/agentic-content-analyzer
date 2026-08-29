"""Contract tests for correlated blog source and article outcomes."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

from src.contracts.operation_context import OperationOutcome, OperationStage
from src.ingestion.blog_scraper import (
    BlogContentIngestionService,
    BlogExtractionResult,
    BlogItemOutcome,
    DiscoveredLink,
)
from src.ingestion.gmail import ContentData
from src.models.content import ContentSource
from src.parsers.html_markdown import ConversionResult, QualityValidation


def _source(url: str, *, name: str = "Blog") -> SimpleNamespace:
    return SimpleNamespace(
        enabled=True,
        url=url,
        name=name,
        link_selector=None,
        link_pattern=None,
        max_entries=10,
        request_delay=0,
        content_filter_strategy="none",
    )


def _content(url: str) -> ContentData:
    return ContentData(
        source_type=ContentSource.BLOG,
        source_id=f"blog:{url}",
        source_url=url,
        title="Article",
        author=None,
        publication="Blog",
        published_date=None,
        markdown_content="# Article\n\n" + "useful " * 40,
        content_hash="hash",
    )


def test_preferred_extractor_failure_with_fallback_success_is_partial() -> None:
    client = BlogContentIngestionService().client
    response = Mock()
    response.text = "<html><h1>Article</h1><p>body</p></html>"
    response.raise_for_status.return_value = None
    client._client.get = Mock(return_value=response)
    fallback = ConversionResult(
        markdown="# Article\n\n" + "fallback content " * 20,
        method="crawl4ai",
        quality=QualityValidation(valid=True, issues=[], stats={}),
    )

    with patch("src.ingestion.blog_scraper.convert_html_with_result", return_value=fallback):
        result = client.extract_post("https://example.com/article")

    assert result.content is not None
    assert result.outcome.outcome == OperationOutcome.PARTIAL
    assert result.outcome.stage == OperationStage.FALLBACK
    assert result.outcome.error_code == "blog_preferred_extractor_failed"
    assert result.outcome.fallback_from == "trafilatura"


def test_terminal_extraction_failure_is_counted_not_skipped() -> None:
    service = BlogContentIngestionService()
    service.client.fetch_index_page = Mock(return_value="<html></html>")
    service.client.discover_post_links = Mock(
        return_value=[DiscoveredLink("https://example.com/article")]
    )
    service.client.extract_post = Mock(
        return_value=BlogExtractionResult(
            content=None,
            outcome=BlogItemOutcome.failed(
                stage=OperationStage.EXTRACT,
                error_code="blog_extraction_failed",
                retryable=False,
            ),
        )
    )

    result = service._ingest_source(
        _source("https://example.com"),
        max_entries=10,
        after_date=None,
        force_reprocess=False,
    )

    assert result.items_failed == 1
    assert result.items_skipped == 0
    assert result.item_errors[0].code == "blog_extraction_failed"
    assert result.item_outcomes[0].outcome == OperationOutcome.PERMANENT_FAILURE


def test_discovery_failure_is_correlated_and_other_sources_continue() -> None:
    service = BlogContentIngestionService()

    def fetch(url: str) -> str:
        if "broken" in url:
            raise httpx.ConnectError("token=secret-canary")
        return "<html></html>"

    service.client.fetch_index_page = Mock(side_effect=fetch)
    service.client.discover_post_links = Mock(return_value=[])

    response = service.ingest_content(
        sources=[
            _source("https://broken.example", name="Broken"),
            _source("https://healthy.example", name="Healthy"),
        ]
    )

    assert service.client.fetch_index_page.call_count == 2
    assert response.status == "error"
    assert response.errors[0].code == "blog_discovery_failed"
    assert "secret-canary" not in response.model_dump_json()


def test_filter_dedup_and_persistence_have_distinct_counts_and_codes() -> None:
    service = BlogContentIngestionService()
    links = [
        DiscoveredLink("https://example.com/filtered"),
        DiscoveredLink("https://example.com/duplicate"),
        DiscoveredLink("https://example.com/persist-fails"),
    ]
    service.client.fetch_index_page = Mock(return_value="<html></html>")
    service.client.discover_post_links = Mock(return_value=links)
    service.client.extract_post = Mock(
        side_effect=[
            BlogExtractionResult(
                content=_content(links[0].url),
                outcome=BlogItemOutcome.succeeded(OperationStage.EXTRACT),
            ),
            BlogExtractionResult(
                content=_content(links[1].url),
                outcome=BlogItemOutcome.succeeded(OperationStage.EXTRACT),
            ),
            BlogExtractionResult(
                content=_content(links[2].url),
                outcome=BlogItemOutcome.succeeded(OperationStage.EXTRACT),
            ),
        ]
    )
    service._content_filter_for_source = Mock(
        return_value=SimpleNamespace(
            is_relevant=Mock(
                side_effect=[
                    SimpleNamespace(relevant=False, strategy_used="topic"),
                    SimpleNamespace(relevant=True, strategy_used="topic"),
                    SimpleNamespace(relevant=True, strategy_used="topic"),
                ]
            )
        )
    )
    service._persist_contents = Mock(
        return_value=(
            0,
            [
                BlogItemOutcome.skipped_duplicate(),
                BlogItemOutcome.failed(
                    stage=OperationStage.PERSIST,
                    error_code="blog_persistence_failed",
                    retryable=True,
                ),
            ],
        )
    )

    result = service._ingest_source(
        _source("https://example.com"),
        max_entries=10,
        after_date=None,
        force_reprocess=False,
    )

    assert result.items_filtered == 1
    assert result.items_skipped == 1
    assert result.items_failed == 1
    assert [outcome.error_code for outcome in result.item_outcomes] == [
        "blog_filtered",
        "blog_duplicate",
        "blog_persistence_failed",
    ]


def test_fallback_records_failed_preferred_stage_and_selected_extractor() -> None:
    service = BlogContentIngestionService()
    url = "https://example.com/fallback"
    service.client.fetch_index_page = Mock(return_value="<html></html>")
    service.client.discover_post_links = Mock(return_value=[DiscoveredLink(url)])
    service.client.extract_post = Mock(
        return_value=BlogExtractionResult(
            content=_content(url),
            outcome=BlogItemOutcome.partial(
                OperationStage.FALLBACK,
                error_code="blog_preferred_extractor_failed",
                fallback_from="trafilatura",
            ),
        )
    )
    service._content_filter_for_source = Mock(return_value=None)
    service._persist_contents = Mock(return_value=(1, []))
    observations: list[tuple[str, OperationStage, Mock]] = []

    @contextmanager
    def record_stage(name: str, stage: OperationStage, **_: object):
        evidence = Mock()
        observations.append((name, stage, evidence))
        yield evidence

    with patch("src.ingestion.blog_scraper.operation_stage", side_effect=record_stage):
        result = service._ingest_source(
            _source("https://example.com"),
            max_entries=10,
            after_date=None,
            force_reprocess=False,
        )

    assert result.items_fetched == 1
    extract = next(item for item in observations if item[0] == "blog.extract")
    fallback = next(item for item in observations if item[0] == "blog.fallback")
    assert extract[1] == OperationStage.EXTRACT
    assert extract[2].finish.call_args.kwargs == {
        "error_code": "blog_preferred_extractor_failed",
        "retryable": False,
        "attributes": {
            "blog.fallback_from": "trafilatura",
            "blog.selected_extractor": "crawl4ai",
        },
    }
    assert extract[2].finish.call_args.args == (OperationOutcome.PARTIAL,)
    assert fallback[1] == OperationStage.FALLBACK
    assert fallback[2].finish.call_args.args == (OperationOutcome.SUCCEEDED,)
