"""Tests for extended source types in the ingest_content worker handler.

Verifies that each source type in the handler's source_map correctly dispatches
to the corresponding orchestrator function with the right keyword arguments.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.queue.worker import _handlers, register_all_handlers


@pytest.fixture(autouse=True)
def _register():
    """Ensure all handlers are registered before each test."""
    register_all_handlers()


@pytest.fixture(autouse=True)
def _mock_progress():
    """Mock update_job_progress to avoid DB connections."""
    with patch("src.queue.setup.update_job_progress", new_callable=AsyncMock):
        yield


# ---------------------------------------------------------------------------
# ingest_content handler — source dispatch tests
# ---------------------------------------------------------------------------


@patch("src.ingestion.orchestrator.ingest_xsearch")
@pytest.mark.asyncio
async def test_ingest_xsearch(mock_xsearch):
    mock_xsearch.return_value = 3
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "xsearch", "prompt": "AI news", "max_threads": 5})
    mock_xsearch.assert_called_once()
    assert mock_xsearch.call_args[1].get("prompt") == "AI news"
    assert mock_xsearch.call_args[1].get("max_threads") == 5


@patch("src.ingestion.orchestrator.ingest_perplexity_search")
@pytest.mark.asyncio
async def test_ingest_perplexity(mock_perplexity):
    mock_perplexity.return_value = 5
    handler = _handlers["ingest_content"]
    await handler(
        1,
        {
            "source": "perplexity",
            "prompt": "latest AI",
            "recency_filter": "week",
            "context_size": "high",
        },
    )
    mock_perplexity.assert_called_once()
    kwargs = mock_perplexity.call_args[1]
    assert kwargs.get("prompt") == "latest AI"
    assert kwargs.get("recency_filter") == "week"
    assert kwargs.get("context_size") == "high"


@patch("src.ingestion.orchestrator.ingest_url")
@pytest.mark.asyncio
async def test_ingest_url(mock_url):
    mock_url.return_value = True
    handler = _handlers["ingest_content"]
    await handler(
        1,
        {
            "source": "url",
            "url": "https://example.com/article",
            "title": "Test Article",
            "tags": ["ai", "ml"],
            "notes": "Interesting read",
        },
    )
    mock_url.assert_called_once()
    kwargs = mock_url.call_args[1]
    assert kwargs["url"] == "https://example.com/article"
    assert kwargs["title"] == "Test Article"
    assert kwargs["tags"] == ["ai", "ml"]
    assert kwargs["notes"] == "Interesting read"


@patch("src.ingestion.orchestrator.ingest_gmail")
@pytest.mark.asyncio
async def test_ingest_gmail(mock_gmail):
    mock_gmail.return_value = 10
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "gmail", "days_back": 3})
    mock_gmail.assert_called_once()


@patch("src.ingestion.orchestrator.ingest_rss")
@pytest.mark.asyncio
async def test_ingest_rss(mock_rss):
    mock_rss.return_value = 7
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "rss", "max_results": 20})
    mock_rss.assert_called_once()
    assert mock_rss.call_args[1].get("max_entries_per_feed") == 20


@patch("src.ingestion.orchestrator.ingest_youtube")
@pytest.mark.asyncio
async def test_ingest_youtube(mock_yt):
    mock_yt.return_value = 4
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "youtube", "public_only": True})
    mock_yt.assert_called_once()
    # public_only=True → use_oauth=False
    assert mock_yt.call_args[1].get("use_oauth") is False


@patch("src.ingestion.orchestrator.ingest_youtube_playlist")
@pytest.mark.asyncio
async def test_ingest_youtube_playlist(mock_ytp):
    mock_ytp.return_value = 2
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "youtube-playlist", "max_results": 10})
    mock_ytp.assert_called_once()
    assert mock_ytp.call_args[1].get("max_videos") == 10


@patch("src.ingestion.orchestrator.ingest_youtube_rss")
@pytest.mark.asyncio
async def test_ingest_youtube_rss(mock_ytr):
    mock_ytr.return_value = 6
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "youtube-rss"})
    mock_ytr.assert_called_once()


@patch("src.ingestion.orchestrator.ingest_podcast")
@pytest.mark.asyncio
async def test_ingest_podcast(mock_podcast):
    mock_podcast.return_value = 3
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "podcast", "max_results": 5})
    mock_podcast.assert_called_once()
    assert mock_podcast.call_args[1].get("max_entries_per_feed") == 5


@patch("src.ingestion.orchestrator.ingest_substack")
@pytest.mark.asyncio
async def test_ingest_substack(mock_sub):
    mock_sub.return_value = 8
    handler = _handlers["ingest_content"]
    await handler(
        1,
        {"source": "substack", "session_cookie": "abc123", "max_results": 15},
    )
    mock_sub.assert_called_once()
    kwargs = mock_sub.call_args[1]
    assert kwargs.get("session_cookie") == "abc123"
    assert kwargs.get("max_entries_per_source") == 15


@pytest.mark.asyncio
async def test_ingest_unknown_source_raises():
    handler = _handlers["ingest_content"]
    with pytest.raises(ValueError, match="Unsupported source"):
        await handler(1, {"source": "nonexistent"})


# ---------------------------------------------------------------------------
# run_pipeline handler
# ---------------------------------------------------------------------------


@patch("src.pipeline.runner.run_pipeline", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_run_pipeline_handler(mock_run):
    handler = _handlers["run_pipeline"]
    await handler(1, {"pipeline_type": "daily", "sources": ["gmail", "rss"]})
    mock_run.assert_called_once()
    assert mock_run.call_args[1]["pipeline_type"] == "daily"
    assert mock_run.call_args[1]["sources"] == ["gmail", "rss"]
