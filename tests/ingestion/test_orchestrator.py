"""Tests for the ingestion orchestrator module.

Each orchestrator function is tested with mocked service classes
to verify correct wiring: lazy import, instantiation, call, and return type.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ingestion.result import IngestionResponse


def _rss_response(n: int) -> IngestionResponse:
    """Helper: build a minimal canonical response for an RSS service mock."""
    return IngestionResponse(
        command="ingest.rss",
        source="rss",
        status="ok",
        items_ingested=n,
    )


class TestIngestGmail:
    @patch("src.ingestion.gmail.GmailContentIngestionService")
    def test_returns_int(self, mock_cls):
        from src.ingestion.orchestrator import ingest_gmail

        mock_cls.return_value.ingest_content.return_value = 5
        result = ingest_gmail()
        assert result == 5
        assert isinstance(result, int)

    @patch("src.ingestion.gmail.GmailContentIngestionService")
    def test_passes_parameters(self, mock_cls):
        from src.ingestion.orchestrator import ingest_gmail

        mock_service = MagicMock()
        mock_service.ingest_content.return_value = 3
        mock_cls.return_value = mock_service
        after = datetime(2025, 1, 1, tzinfo=UTC)

        ingest_gmail(query="label:test", max_results=5, after_date=after, force_reprocess=True)

        mock_service.ingest_content.assert_called_once_with(
            query="label:test",
            max_results=5,
            after_date=after,
            force_reprocess=True,
        )


class TestIngestRss:
    @patch("src.ingestion.rss.RSSContentIngestionService")
    def test_returns_ingestion_response(self, mock_cls):
        from src.ingestion.orchestrator import ingest_rss
        from src.ingestion.result import IngestionResponse

        mock_cls.return_value.ingest_content.return_value = _rss_response(10)
        result = ingest_rss()
        assert isinstance(result, IngestionResponse)
        assert result.items_ingested == 10
        assert result.command == "ingest.rss"
        assert result.status == "ok"

    @patch("src.ingestion.rss.RSSContentIngestionService")
    def test_on_result_callback_receives_ingestion_result(self, mock_cls):
        from src.ingestion.orchestrator import ingest_rss

        ingestion_result = _rss_response(7)
        mock_cls.return_value.ingest_content.return_value = ingestion_result

        callback = MagicMock()
        ingest_rss(on_result=callback)

        callback.assert_called_once_with(ingestion_result)

    @patch("src.ingestion.rss.RSSContentIngestionService")
    def test_on_result_not_called_when_none(self, mock_cls):
        from src.ingestion.orchestrator import ingest_rss

        mock_cls.return_value.ingest_content.return_value = _rss_response(3)
        # Should not raise when on_result is None (default)
        result = ingest_rss()
        assert result.items_ingested == 3

    @patch("src.ingestion.rss.RSSContentIngestionService")
    def test_passes_parameters(self, mock_cls):
        from src.ingestion.orchestrator import ingest_rss

        mock_service = MagicMock()
        mock_service.ingest_content.return_value = _rss_response(0)
        mock_cls.return_value = mock_service
        after = datetime(2025, 1, 1, tzinfo=UTC)

        ingest_rss(max_entries_per_feed=20, after_date=after, force_reprocess=True)

        mock_service.ingest_content.assert_called_once_with(
            max_entries_per_feed=20,
            after_date=after,
            force_reprocess=True,
        )


def _yt_response(command: str, source: str, n: int) -> IngestionResponse:
    return IngestionResponse(
        command=command,  # type: ignore[arg-type]
        source=source,  # type: ignore[arg-type]
        status="ok",
        items_ingested=n,
    )


class TestIngestYoutube:
    """YouTube orchestrator tests.

    Service methods are now async and return IngestionResponse envelopes;
    orchestrator bridges via asyncio.run() and merges sub-envelopes via
    ``_merge_youtube_envelopes``. Mocks must use AsyncMock for awaitable
    methods AND return real IngestionResponse instances — returning ints
    masks production bugs where consumers treat the envelope like an int.
    """

    @patch("src.ingestion.youtube.YouTubeRSSIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_calls_all_three_methods_across_two_services(self, mock_content_cls, mock_rss_cls):
        from src.ingestion.orchestrator import ingest_youtube

        mock_content = MagicMock()
        mock_content.ingest_all_playlists = AsyncMock(
            return_value=_yt_response("ingest.youtube-playlist", "youtube-playlist", 3)
        )
        mock_content.ingest_channels = AsyncMock(
            return_value=_yt_response("ingest.youtube-playlist", "youtube-playlist", 2)
        )
        mock_content_cls.return_value = mock_content

        mock_rss = MagicMock()
        mock_rss.ingest_all_feeds = AsyncMock(
            return_value=_yt_response("ingest.youtube-rss", "youtube-rss", 1)
        )
        mock_rss_cls.return_value = mock_rss

        result = ingest_youtube()

        assert isinstance(result, IngestionResponse)
        assert result.command == "ingest.youtube"
        assert result.source == "youtube"
        assert result.items_ingested == 6  # 3 + 2 + 1
        mock_content.ingest_all_playlists.assert_called_once()
        mock_content.ingest_channels.assert_called_once()
        mock_rss.ingest_all_feeds.assert_called_once()

    @patch("src.ingestion.youtube.YouTubeRSSIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_returns_ingestion_response(self, mock_content_cls, mock_rss_cls):
        from src.ingestion.orchestrator import ingest_youtube

        mock_content_cls.return_value.ingest_all_playlists = AsyncMock(
            return_value=_yt_response("ingest.youtube-playlist", "youtube-playlist", 0)
        )
        mock_content_cls.return_value.ingest_channels = AsyncMock(
            return_value=_yt_response("ingest.youtube-playlist", "youtube-playlist", 0)
        )
        mock_rss_cls.return_value.ingest_all_feeds = AsyncMock(
            return_value=_yt_response("ingest.youtube-rss", "youtube-rss", 0)
        )

        result = ingest_youtube()
        assert isinstance(result, IngestionResponse)
        assert result.items_ingested == 0
        assert result.command == "ingest.youtube"

    @patch("src.ingestion.youtube.YouTubeRSSIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_passes_use_oauth(self, mock_content_cls, mock_rss_cls):
        from src.ingestion.orchestrator import ingest_youtube

        mock_content_cls.return_value.ingest_all_playlists = AsyncMock(
            return_value=_yt_response("ingest.youtube-playlist", "youtube-playlist", 0)
        )
        mock_content_cls.return_value.ingest_channels = AsyncMock(
            return_value=_yt_response("ingest.youtube-playlist", "youtube-playlist", 0)
        )
        mock_rss_cls.return_value.ingest_all_feeds = AsyncMock(
            return_value=_yt_response("ingest.youtube-rss", "youtube-rss", 0)
        )

        ingest_youtube(use_oauth=False)

        mock_content_cls.assert_called_once_with(use_oauth=False)

    @patch("src.ingestion.youtube.YouTubeRSSIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_passes_parameters_to_all_calls(self, mock_content_cls, mock_rss_cls):
        from src.ingestion.orchestrator import ingest_youtube

        mock_content = MagicMock()
        mock_content.ingest_all_playlists = AsyncMock(
            return_value=_yt_response("ingest.youtube-playlist", "youtube-playlist", 0)
        )
        mock_content.ingest_channels = AsyncMock(
            return_value=_yt_response("ingest.youtube-playlist", "youtube-playlist", 0)
        )
        mock_content_cls.return_value = mock_content

        mock_rss = MagicMock()
        mock_rss.ingest_all_feeds = AsyncMock(
            return_value=_yt_response("ingest.youtube-rss", "youtube-rss", 0)
        )
        mock_rss_cls.return_value = mock_rss

        after = datetime(2025, 1, 1, tzinfo=UTC)
        ingest_youtube(max_videos=20, after_date=after, force_reprocess=True)

        mock_content.ingest_all_playlists.assert_called_once_with(
            max_videos_per_playlist=20,
            after_date=after,
            force_reprocess=True,
        )
        mock_content.ingest_channels.assert_called_once_with(
            max_videos_per_channel=20,
            after_date=after,
            force_reprocess=True,
        )
        mock_rss.ingest_all_feeds.assert_called_once_with(
            max_entries_per_feed=20,
            after_date=after,
            force_reprocess=True,
        )

    @patch("src.ingestion.youtube.YouTubeRSSIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_merges_errors_and_warnings_across_subenvelopes(self, mock_content_cls, mock_rss_cls):
        """Errors from the playlist and RSS sub-envelopes are concatenated.

        Without this preservation, a single failed feed inside the RSS
        sub-envelope would be invisible to the consumer of the combined
        ``ingest.youtube`` envelope, since the orchestrator merges counts
        before returning.
        """
        from src.ingestion.orchestrator import ingest_youtube
        from src.ingestion.result import IngestionError

        playlist_resp = IngestionResponse(
            command="ingest.youtube-playlist",
            source="youtube-playlist",
            status="partial",
            items_ingested=2,
            errors=[IngestionError(code="oauth_unavailable", message="private")],
        )
        rss_resp = IngestionResponse(
            command="ingest.youtube-rss",
            source="youtube-rss",
            status="partial",
            items_ingested=1,
            errors=[IngestionError(code="feed_ingest_error", message="500")],
        )
        # Inner playlist response (before merge with channels) needs to be
        # returnable from each service call separately.
        mock_content_cls.return_value.ingest_all_playlists = AsyncMock(return_value=playlist_resp)
        mock_content_cls.return_value.ingest_channels = AsyncMock(
            return_value=_yt_response("ingest.youtube-playlist", "youtube-playlist", 0)
        )
        mock_rss_cls.return_value.ingest_all_feeds = AsyncMock(return_value=rss_resp)

        result = ingest_youtube()

        assert result.command == "ingest.youtube"
        assert result.items_ingested == 3  # 2 + 0 + 1
        assert len(result.errors) == 2
        codes = {e.code for e in result.errors}
        assert codes == {"oauth_unavailable", "feed_ingest_error"}
        assert result.status == "partial"


def _podcast_response(n: int) -> IngestionResponse:
    """Helper: build a minimal canonical response for a Podcast service mock."""
    return IngestionResponse(
        command="ingest.podcast",
        source="podcast",
        status="ok",
        items_ingested=n,
    )


class TestIngestPodcast:
    @patch("src.ingestion.podcast.PodcastContentIngestionService")
    def test_returns_envelope(self, mock_cls):
        from src.ingestion.orchestrator import ingest_podcast

        mock_cls.return_value.ingest_all_feeds.return_value = _podcast_response(4)
        result = ingest_podcast()
        assert isinstance(result, IngestionResponse)
        assert result.command == "ingest.podcast"
        assert result.source == "podcast"
        assert result.items_ingested == 4
        assert result.status == "ok"

    @patch("src.ingestion.podcast.PodcastContentIngestionService")
    def test_passes_parameters(self, mock_cls):
        from src.ingestion.orchestrator import ingest_podcast

        mock_service = MagicMock()
        mock_service.ingest_all_feeds.return_value = _podcast_response(0)
        mock_cls.return_value = mock_service
        after = datetime(2025, 1, 1, tzinfo=UTC)

        ingest_podcast(max_entries_per_feed=5, after_date=after, force_reprocess=True)

        mock_service.ingest_all_feeds.assert_called_once_with(
            max_entries_per_feed=5,
            after_date=after,
            force_reprocess=True,
        )


def _substack_response(n: int) -> IngestionResponse:
    return IngestionResponse(
        command="ingest.substack",
        source="substack",
        status="ok",
        items_ingested=n,
    )


class TestIngestSubstack:
    @patch("src.ingestion.substack.SubstackContentIngestionService")
    def test_returns_ingestion_response(self, mock_cls):
        from src.ingestion.orchestrator import ingest_substack

        mock_cls.return_value.ingest_content.return_value = _substack_response(6)
        result = ingest_substack()
        assert isinstance(result, IngestionResponse)
        assert result.items_ingested == 6
        assert result.command == "ingest.substack"

    @patch("src.ingestion.substack.SubstackContentIngestionService")
    def test_calls_close_on_success(self, mock_cls):
        from src.ingestion.orchestrator import ingest_substack

        mock_service = MagicMock()
        mock_service.ingest_content.return_value = _substack_response(2)
        mock_cls.return_value = mock_service

        ingest_substack()

        mock_service.close.assert_called_once()

    @patch("src.ingestion.substack.SubstackContentIngestionService")
    def test_calls_close_on_exception(self, mock_cls):
        from src.ingestion.orchestrator import ingest_substack

        mock_service = MagicMock()
        mock_service.ingest_content.side_effect = RuntimeError("API error")
        mock_cls.return_value = mock_service

        with pytest.raises(RuntimeError, match="API error"):
            ingest_substack()

        mock_service.close.assert_called_once()

    @patch("src.ingestion.substack.SubstackContentIngestionService")
    def test_passes_session_cookie(self, mock_cls):
        from src.ingestion.orchestrator import ingest_substack

        mock_cls.return_value.ingest_content.return_value = _substack_response(0)

        ingest_substack(session_cookie="test-cookie")

        mock_cls.assert_called_once_with(session_cookie="test-cookie")

    @patch("src.ingestion.substack.SubstackContentIngestionService")
    def test_passes_parameters(self, mock_cls):
        from src.ingestion.orchestrator import ingest_substack

        mock_service = MagicMock()
        mock_service.ingest_content.return_value = _substack_response(0)
        mock_cls.return_value = mock_service
        after = datetime(2025, 1, 1, tzinfo=UTC)

        ingest_substack(max_entries_per_source=15, after_date=after, force_reprocess=True)

        mock_service.ingest_content.assert_called_once_with(
            max_entries_per_source=15,
            after_date=after,
            force_reprocess=True,
        )


# ---------------------------------------------------------------------------
# Scholar variants — multi-source (ingest_scholar), single paper
# (ingest_scholar_paper), reference traversal (ingest_scholar_refs).
# Each test mocks at the service-class level (post-PR-#147 boundary):
# patches go on src.ingestion.scholar.* / src.services.reference_extractor.*.
# ---------------------------------------------------------------------------


def _scholar_search_result(
    *,
    ingested: int = 0,
    skipped_dup: int = 0,
    skipped_filter: int = 0,
    failed: int = 0,
):
    """Build a ScholarSearchResult-shaped mock for service-method returns."""
    from src.ingestion.scholar import ScholarSearchResult

    return ScholarSearchResult(
        source_name="test-source",
        query="test",
        papers_found=ingested + skipped_dup + skipped_filter + failed,
        papers_ingested=ingested,
        papers_skipped_duplicate=skipped_dup,
        papers_skipped_filter=skipped_filter,
        papers_failed=failed,
    )


class TestIngestScholar:
    @patch("src.ingestion.scholar.ScholarContentIngestionService")
    @patch("src.config.sources.load_sources_config")
    def test_returns_envelope_with_aggregated_counts(self, mock_load, mock_cls):
        from src.ingestion.orchestrator import ingest_scholar

        # Two enabled sources contributing to the aggregation.
        source_a = MagicMock(name="source_a", enabled=True)
        source_b = MagicMock(name="source_b", enabled=True)
        mock_load.return_value.get_scholar_sources.return_value = [source_a, source_b]

        mock_service = MagicMock()
        mock_service.ingest_from_search = AsyncMock(
            side_effect=[
                _scholar_search_result(ingested=4, skipped_dup=1, skipped_filter=2),
                _scholar_search_result(ingested=3, failed=1),
            ]
        )
        mock_service.close = AsyncMock()
        mock_cls.return_value = mock_service

        result = ingest_scholar()

        assert isinstance(result, IngestionResponse)
        assert result.command == "ingest.scholar"
        assert result.source == "scholar"
        # 4 + 3 ingested; (1 dup + 2 filter) + 0 = 3 skipped; 0 + 1 failed
        assert result.items_ingested == 7
        assert result.items_skipped == 3
        assert result.items_failed == 1
        # Status is partial because items_ingested>0 and items_failed>0.
        assert result.status == "partial"
        mock_service.close.assert_awaited_once()

    @patch("src.ingestion.scholar.ScholarContentIngestionService")
    @patch("src.config.sources.load_sources_config")
    def test_source_exception_becomes_error_entry(self, mock_load, mock_cls):
        from src.ingestion.orchestrator import ingest_scholar

        bad = MagicMock(name="bad", enabled=True)
        bad.name = "bad-source"
        mock_load.return_value.get_scholar_sources.return_value = [bad]

        mock_service = MagicMock()
        mock_service.ingest_from_search = AsyncMock(side_effect=RuntimeError("boom"))
        mock_service.close = AsyncMock()
        mock_cls.return_value = mock_service

        result = ingest_scholar()

        assert result.status == "error"
        assert result.items_ingested == 0
        assert len(result.errors) == 1
        assert result.errors[0].code == "scholar_source_error"
        assert "boom" in result.errors[0].message

    @patch("src.config.sources.load_sources_config")
    def test_no_sources_returns_ok_envelope(self, mock_load):
        from src.ingestion.orchestrator import ingest_scholar

        mock_load.return_value.get_scholar_sources.return_value = []
        result = ingest_scholar()

        assert isinstance(result, IngestionResponse)
        assert result.status == "ok"
        assert result.items_ingested == 0


def _scholar_paper_result(
    *,
    paper_id: str | None = "p1",
    ingested: bool = True,
    already_exists: bool = False,
    refs_ingested: int = 0,
    error: str | None = None,
):
    from src.ingestion.scholar import ScholarPaperResult

    return ScholarPaperResult(
        identifier="DOI:10.1/x",
        paper_id=paper_id,
        ingested=ingested,
        already_exists=already_exists,
        refs_ingested=refs_ingested,
        error=error,
    )


class TestIngestScholarPaper:
    @patch("src.ingestion.scholar.ScholarContentIngestionService")
    def test_returns_envelope_with_details(self, mock_cls):
        from src.ingestion.orchestrator import ingest_scholar_paper

        mock_service = MagicMock()
        mock_service.ingest_paper = AsyncMock(
            return_value=_scholar_paper_result(ingested=True, refs_ingested=3)
        )
        mock_service.close = AsyncMock()
        mock_cls.return_value = mock_service

        result = ingest_scholar_paper(identifier="DOI:10.1/x", with_refs=True)

        assert isinstance(result, IngestionResponse)
        assert result.command == "ingest.scholar-paper"
        assert result.source == "scholar_paper"
        # 1 (seed paper) + 3 (refs) = 4 total
        assert result.items_ingested == 4
        assert result.details["with_refs"] is True
        assert result.details["refs_ingested"] == 3
        assert result.details["paper_id"] == "p1"

    @patch("src.ingestion.scholar.ScholarContentIngestionService")
    def test_already_exists_classified_as_skipped(self, mock_cls):
        from src.ingestion.orchestrator import ingest_scholar_paper

        mock_service = MagicMock()
        mock_service.ingest_paper = AsyncMock(
            return_value=_scholar_paper_result(ingested=False, already_exists=True)
        )
        mock_service.close = AsyncMock()
        mock_cls.return_value = mock_service

        result = ingest_scholar_paper(identifier="DOI:10.1/x")

        assert result.items_ingested == 0
        assert result.items_skipped == 1
        assert result.status == "ok"

    @patch("src.ingestion.scholar.ScholarContentIngestionService")
    def test_error_field_populates_errors(self, mock_cls):
        from src.ingestion.orchestrator import ingest_scholar_paper

        mock_service = MagicMock()
        mock_service.ingest_paper = AsyncMock(
            return_value=_scholar_paper_result(ingested=False, error="Paper not found")
        )
        mock_service.close = AsyncMock()
        mock_cls.return_value = mock_service

        result = ingest_scholar_paper(identifier="DOI:10.1/x")

        assert result.status == "error"
        assert len(result.errors) == 1
        assert result.errors[0].code == "scholar_paper_error"


class TestIngestScholarRefs:
    @patch("src.services.reference_extractor.ReferenceExtractor")
    def test_returns_envelope_with_papers_ingested_in_details(self, mock_cls):
        """scholar-refs uses the reserved ``papers_ingested`` key in details
        per the result.py registry, even though items_ingested carries the
        same number — preserves the legacy CLI JSON consumer's expectations."""
        from src.ingestion.orchestrator import ingest_scholar_refs
        from src.services.reference_extractor import ReferenceExtractionResult

        mock_extractor = MagicMock()
        mock_extractor.ingest_extracted_references = AsyncMock(
            return_value=ReferenceExtractionResult(
                content_scanned=10,
                references_found=8,
                references_resolved=6,
                references_unresolved=2,
                papers_ingested=5,
                papers_skipped_duplicate=1,
            )
        )
        mock_extractor.close = AsyncMock()
        mock_cls.return_value = mock_extractor

        result = ingest_scholar_refs(dry_run=False)

        assert isinstance(result, IngestionResponse)
        assert result.command == "ingest.scholar-refs"
        assert result.source == "scholar-refs"
        assert result.items_ingested == 5
        assert result.items_skipped == 1
        assert result.details["papers_ingested"] == 5
        assert result.details["content_scanned"] == 10
        assert result.details["references_found"] == 8
        assert result.details["dry_run"] is False


# ---------------------------------------------------------------------------
# arXiv variants — multi-source (ingest_arxiv) and single paper
# (ingest_arxiv_paper). Service methods here are sync, so plain MagicMock
# (no AsyncMock) suffices.
# ---------------------------------------------------------------------------


def _arxiv_ingestion_result(
    *,
    ingested: int = 0,
    updated: int = 0,
    enriched: int = 0,
    skipped_dup: int = 0,
    failed: int = 0,
    errors: list[str] | None = None,
):
    from src.ingestion.arxiv import ArxivIngestionResult

    return ArxivIngestionResult(
        source_name="test",
        query="test",
        papers_found=ingested + updated + enriched + skipped_dup + failed,
        papers_ingested=ingested,
        papers_updated_version=updated,
        papers_enriched_scholar=enriched,
        papers_skipped_duplicate=skipped_dup,
        papers_failed=failed,
        errors=errors or [],
    )


class TestIngestArxiv:
    @patch("src.ingestion.arxiv.ArxivContentIngestionService")
    @patch("src.config.sources.load_sources_config")
    def test_returns_envelope_aggregating_three_landed_categories(self, mock_load, mock_cls):
        """Ingested + updated_version + enriched_scholar all roll up into items_ingested,
        because each represents content that landed in (or refreshed) the DB.
        """
        from src.ingestion.orchestrator import ingest_arxiv

        s1 = MagicMock(enabled=True, max_entries=None, pdf_extraction=True)
        mock_load.return_value.get_arxiv_sources.return_value = [s1]

        mock_service = MagicMock()
        mock_service.ingest_from_search.return_value = _arxiv_ingestion_result(
            ingested=3, updated=1, enriched=2, skipped_dup=4, failed=0
        )
        mock_cls.return_value = mock_service

        result = ingest_arxiv()

        assert isinstance(result, IngestionResponse)
        assert result.command == "ingest.arxiv"
        assert result.source == "arxiv"
        # 3 ingested + 1 updated + 2 enriched = 6 items_ingested
        assert result.items_ingested == 6
        assert result.items_skipped == 4
        assert result.status == "ok"

    @patch("src.ingestion.arxiv.ArxivContentIngestionService")
    @patch("src.config.sources.load_sources_config")
    def test_per_paper_errors_become_ingestion_errors(self, mock_load, mock_cls):
        from src.ingestion.orchestrator import ingest_arxiv

        s1 = MagicMock(enabled=True, max_entries=None, pdf_extraction=True)
        mock_load.return_value.get_arxiv_sources.return_value = [s1]

        mock_service = MagicMock()
        mock_service.ingest_from_search.return_value = _arxiv_ingestion_result(
            ingested=1, failed=2, errors=["2301.x: parse failed", "2301.y: HTTP 503"]
        )
        mock_cls.return_value = mock_service

        result = ingest_arxiv()

        # Status="partial": some items landed, some failed.
        assert result.status == "partial"
        assert result.items_ingested == 1
        assert result.items_failed == 2
        assert len(result.errors) == 2
        assert all(e.code == "arxiv_paper_error" for e in result.errors)

    @patch("src.ingestion.arxiv.ArxivContentIngestionService")
    @patch("src.config.sources.load_sources_config")
    def test_no_pdf_flips_pdf_extraction_on_all_sources(self, mock_load, mock_cls):
        from src.ingestion.orchestrator import ingest_arxiv

        s1 = MagicMock(enabled=True, max_entries=None, pdf_extraction=True)
        s2 = MagicMock(enabled=True, max_entries=None, pdf_extraction=True)
        mock_load.return_value.get_arxiv_sources.return_value = [s1, s2]

        mock_service = MagicMock()
        mock_service.ingest_from_search.return_value = _arxiv_ingestion_result(ingested=0)
        mock_cls.return_value = mock_service

        ingest_arxiv(no_pdf=True)

        assert s1.pdf_extraction is False
        assert s2.pdf_extraction is False


def _arxiv_paper_result(
    *,
    arxiv_id: str | None = "2301.12345",
    ingested: bool = True,
    already_exists: bool = False,
    version_updated: bool = False,
    error: str | None = None,
):
    from src.ingestion.arxiv import ArxivPaperResult

    return ArxivPaperResult(
        identifier="2301.12345",
        arxiv_id=arxiv_id,
        ingested=ingested,
        already_exists=already_exists,
        version_updated=version_updated,
        error=error,
    )


class TestIngestArxivPaperOrch:
    @patch("src.ingestion.arxiv.ArxivContentIngestionService")
    def test_returns_envelope_with_arxiv_id_in_details(self, mock_cls):
        from src.ingestion.orchestrator import ingest_arxiv_paper

        mock_service = MagicMock()
        mock_service.ingest_paper.return_value = _arxiv_paper_result(
            ingested=True, version_updated=True
        )
        mock_cls.return_value = mock_service

        result = ingest_arxiv_paper(identifier="2301.12345")

        assert isinstance(result, IngestionResponse)
        assert result.command == "ingest.arxiv-paper"
        assert result.source == "arxiv_paper"
        assert result.items_ingested == 1
        assert result.details["arxiv_id"] == "2301.12345"
        assert result.details["version_updated"] is True

    @patch("src.ingestion.arxiv.ArxivContentIngestionService")
    def test_close_called_on_exception(self, mock_cls):
        from src.ingestion.orchestrator import ingest_arxiv_paper

        mock_service = MagicMock()
        mock_service.ingest_paper.side_effect = RuntimeError("API error")
        mock_cls.return_value = mock_service

        with pytest.raises(RuntimeError, match="API error"):
            ingest_arxiv_paper(identifier="2301.12345")

        mock_service.close.assert_called_once()
