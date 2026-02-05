"""Tests for sync adapter functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cli.adapters import (
    create_digest_sync,
    generate_podcast_script_sync,
    list_pending_reviews_sync,
    run_async,
    search_graph_sync,
)


class TestRunAsync:
    def test_run_async_basic(self):
        async def coro():
            return 42

        result = run_async(coro())
        assert result == 42

    def test_run_async_with_exception(self):
        async def failing_coro():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            run_async(failing_coro())


class TestCreateDigestSync:
    @patch("src.processors.digest_creator.DigestCreator")
    def test_creates_digest(self, mock_cls):
        mock_creator = MagicMock()
        mock_creator.create_digest = AsyncMock(return_value="digest_result")
        mock_cls.return_value = mock_creator

        result = create_digest_sync("request")
        assert result == "digest_result"


class TestGeneratePodcastScriptSync:
    @patch("src.processors.podcast_creator.PodcastCreator")
    def test_generates_script(self, mock_cls):
        mock_creator = MagicMock()
        mock_creator.generate_script = AsyncMock(return_value="script_result")
        mock_cls.return_value = mock_creator

        result = generate_podcast_script_sync("request")
        assert result == "script_result"


class TestListPendingReviewsSync:
    @patch("src.services.review_service.ReviewService")
    def test_lists_reviews(self, mock_cls):
        mock_service = MagicMock()
        mock_service.list_pending_reviews = AsyncMock(return_value=["review1", "review2"])
        mock_cls.return_value = mock_service

        result = list_pending_reviews_sync()
        assert result == ["review1", "review2"]


class TestSearchGraphSync:
    @patch("src.storage.graphiti_client.GraphitiClient")
    def test_searches_graph(self, mock_cls):
        mock_client = MagicMock()
        mock_client.search_related_concepts = AsyncMock(return_value=["result1"])
        mock_cls.return_value = mock_client

        result = search_graph_sync("test query", limit=5)
        assert result == ["result1"]
        mock_client.search_related_concepts.assert_called_once_with("test query", limit=5)
