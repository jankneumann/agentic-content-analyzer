"""Tests for YouTube transcript 429 exponential backoff."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError

from src.ingestion.youtube import YouTubeClient


def _mock_init(self, use_oauth=True):
    """Mock YouTubeClient init that avoids real auth."""
    self._service = MagicMock()
    self._authenticated = True
    self.use_oauth = use_oauth
    self.oauth_available = False


def _make_http_error(status: int = 429) -> HttpError:
    """Create a mock HttpError with the given status code."""
    resp = MagicMock()
    resp.status = status
    return HttpError(resp=resp, content=b"Rate limited")


class TestRetryWithBackoff:
    """Tests for _retry_with_backoff helper."""

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch("src.ingestion.youtube.settings")
    @patch("src.ingestion.youtube.time.sleep")
    def test_succeeds_first_try(self, mock_sleep, mock_settings):
        """Should return immediately on first success."""
        mock_settings.youtube_max_retries = 4
        mock_settings.youtube_backoff_base = 2.0

        client = YouTubeClient(use_oauth=False)
        result = client._retry_with_backoff(lambda: "success")

        assert result == "success"
        mock_sleep.assert_not_called()

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch("src.ingestion.youtube.settings")
    @patch("src.ingestion.youtube.time.sleep")
    @patch("src.ingestion.youtube.random.uniform", return_value=1.0)
    def test_retries_on_429(self, mock_uniform, mock_sleep, mock_settings):
        """Should retry with backoff on 429 errors."""
        mock_settings.youtube_max_retries = 3
        mock_settings.youtube_backoff_base = 2.0

        client = YouTubeClient(use_oauth=False)

        call_count = 0

        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise _make_http_error(429)
            return "success after retries"

        result = client._retry_with_backoff(fail_twice, context="test video")
        assert result == "success after retries"
        assert call_count == 3
        assert mock_sleep.call_count == 2

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch("src.ingestion.youtube.settings")
    @patch("src.ingestion.youtube.time.sleep")
    @patch("src.ingestion.youtube.random.uniform", return_value=1.0)
    def test_raises_after_max_retries(self, mock_uniform, mock_sleep, mock_settings):
        """Should raise HttpError after exhausting retries."""
        mock_settings.youtube_max_retries = 2
        mock_settings.youtube_backoff_base = 2.0

        client = YouTubeClient(use_oauth=False)

        import pytest

        with pytest.raises(HttpError):
            client._retry_with_backoff(
                lambda: (_ for _ in ()).throw(_make_http_error(429)),  # type: ignore
            )

        assert mock_sleep.call_count == 2

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch("src.ingestion.youtube.settings")
    @patch("src.ingestion.youtube.time.sleep")
    def test_non_429_errors_not_retried(self, mock_sleep, mock_settings):
        """Non-429 HTTP errors should be raised immediately."""
        mock_settings.youtube_max_retries = 4
        mock_settings.youtube_backoff_base = 2.0

        client = YouTubeClient(use_oauth=False)

        import pytest

        with pytest.raises(HttpError):
            client._retry_with_backoff(lambda: (_ for _ in ()).throw(_make_http_error(500)))  # type: ignore

        mock_sleep.assert_not_called()

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch("src.ingestion.youtube.settings")
    @patch("src.ingestion.youtube.time.sleep")
    @patch("src.ingestion.youtube.random.uniform", return_value=1.0)
    def test_exponential_backoff_delays(self, mock_uniform, mock_sleep, mock_settings):
        """Verify exponential backoff delay progression."""
        mock_settings.youtube_max_retries = 3
        mock_settings.youtube_backoff_base = 2.0

        client = YouTubeClient(use_oauth=False)

        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise _make_http_error(429)

        import pytest

        with pytest.raises(HttpError):
            client._retry_with_backoff(always_fail)

        # With uniform returning 1.0: delay = base * 2^attempt * 1.0
        # Attempt 0: 2.0 * 1 * 1.0 = 2.0
        # Attempt 1: 2.0 * 2 * 1.0 = 4.0
        # Attempt 2: 2.0 * 4 * 1.0 = 8.0
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [2.0, 4.0, 8.0]

    @patch.object(YouTubeClient, "__init__", _mock_init)
    @patch("src.ingestion.youtube.settings")
    @patch("src.ingestion.youtube.time.sleep")
    def test_jitter_applied(self, mock_sleep, mock_settings):
        """Verify jitter is applied (random.uniform(0.8, 1.2) called)."""
        mock_settings.youtube_max_retries = 1
        mock_settings.youtube_backoff_base = 2.0

        client = YouTubeClient(use_oauth=False)

        call_count = 0

        def fail_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _make_http_error(429)
            return "ok"

        with patch("src.ingestion.youtube.random.uniform", return_value=0.9) as mock_jitter:
            client._retry_with_backoff(fail_once)
            mock_jitter.assert_called_once_with(0.8, 1.2)
            # Delay should be 2.0 * 1 * 0.9 = 1.8
            mock_sleep.assert_called_once_with(1.8)
