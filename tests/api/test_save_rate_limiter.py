"""Tests for rate limiting on save-url and save-page endpoints.

Validates that the EndpointRateLimiter is correctly wired into both
content save endpoints with 30 req/min per IP.
"""

from unittest.mock import AsyncMock, patch

from src.api.rate_limiter_base import EndpointRateLimiter


class TestSaveRateLimiterSingleton:
    """Tests for the save_rate_limiter module-level singleton."""

    def test_save_rate_limiter_singleton_created(self):
        """Verify singleton has correct limits (30 req/min)."""
        from src.api.save_rate_limiter import save_rate_limiter

        assert isinstance(save_rate_limiter, EndpointRateLimiter)
        assert save_rate_limiter._max == 30
        assert save_rate_limiter._window == 60


class TestSaveRateLimiterUnit:
    """Unit tests for rate limiter logic applied to save endpoints."""

    def test_rate_limiter_allows_under_limit(self):
        """Requests under the limit are allowed."""
        limiter = EndpointRateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_limited("10.0.0.1") is False

    def test_rate_limiter_blocks_over_limit(self):
        """31st request is blocked after 30 allowed."""
        limiter = EndpointRateLimiter(max_requests=30, window_seconds=60)
        for _ in range(30):
            assert limiter.is_limited("10.0.0.1") is False

        assert limiter.is_limited("10.0.0.1") is True

    def test_rate_limiter_per_ip_isolation(self):
        """Different IPs have independent limits."""
        limiter = EndpointRateLimiter(max_requests=2, window_seconds=60)
        for _ in range(2):
            limiter.is_limited("10.0.0.1")

        assert limiter.is_limited("10.0.0.1") is True
        assert limiter.is_limited("10.0.0.2") is False

    def test_rate_limiter_retry_after_positive_when_blocked(self):
        """Retry-After returns a positive value when blocked."""
        limiter = EndpointRateLimiter(max_requests=2, window_seconds=60)
        for _ in range(2):
            limiter.is_limited("10.0.0.1")

        retry = limiter.get_retry_after("10.0.0.1")
        assert retry > 0
        assert retry <= 60

    def test_rate_limiter_retry_after_zero_when_not_blocked(self):
        """Retry-After returns 0 when not blocked."""
        limiter = EndpointRateLimiter(max_requests=10, window_seconds=60)
        assert limiter.get_retry_after("10.0.0.1") == 0


class TestSaveURLRateLimited:
    """API-level tests for rate limiting on POST /api/v1/content/save-url."""

    @patch("src.api.save_routes._enqueue_extraction", new_callable=AsyncMock)
    def test_save_url_rate_limited(self, mock_extract, client, db_session):
        """Verify save-url returns 429 when rate limit exceeded."""
        # Replace the module-level singleton with a low-limit instance
        low_limiter = EndpointRateLimiter(max_requests=2, window_seconds=60)
        with patch("src.api.save_routes.save_rate_limiter", low_limiter):
            for i in range(2):
                resp = client.post(
                    "/api/v1/content/save-url",
                    json={"url": f"https://example.com/rl-article-{i}"},
                )
                assert resp.status_code == 201, f"Request {i} should succeed"

            # 3rd request should be rate limited
            resp = client.post(
                "/api/v1/content/save-url",
                json={"url": "https://example.com/rl-blocked"},
            )
            assert resp.status_code == 429
            assert "Rate limit exceeded" in resp.json()["detail"]

    @patch("src.api.save_routes._enqueue_extraction", new_callable=AsyncMock)
    def test_save_url_rate_limit_includes_retry_after(self, mock_extract, client, db_session):
        """Verify 429 response includes Retry-After header."""
        low_limiter = EndpointRateLimiter(max_requests=1, window_seconds=60)
        with patch("src.api.save_routes.save_rate_limiter", low_limiter):
            client.post(
                "/api/v1/content/save-url",
                json={"url": "https://example.com/rl-retry-first"},
            )
            resp = client.post(
                "/api/v1/content/save-url",
                json={"url": "https://example.com/rl-retry-second"},
            )
            assert resp.status_code == 429
            assert "retry-after" in resp.headers
            retry_val = int(resp.headers["retry-after"])
            assert 0 < retry_val <= 60


class TestSavePageRateLimited:
    """API-level tests for rate limiting on POST /api/v1/content/save-page."""

    @patch("src.api.save_routes._process_client_html", new_callable=AsyncMock)
    def test_save_page_rate_limited(self, mock_process, client, db_session):
        """Verify save-page returns 429 when rate limit exceeded."""
        low_limiter = EndpointRateLimiter(max_requests=2, window_seconds=60)
        with patch("src.api.save_routes.save_rate_limiter", low_limiter):
            for i in range(2):
                resp = client.post(
                    "/api/v1/content/save-page",
                    json={
                        "url": f"https://example.com/rl-page-{i}",
                        "html": "<html><body>Test</body></html>",
                    },
                )
                assert resp.status_code == 201, f"Request {i} should succeed"

            # 3rd request should be rate limited
            resp = client.post(
                "/api/v1/content/save-page",
                json={
                    "url": "https://example.com/rl-page-blocked",
                    "html": "<html><body>Blocked</body></html>",
                },
            )
            assert resp.status_code == 429
            assert "Rate limit exceeded" in resp.json()["detail"]

    @patch("src.api.save_routes._process_client_html", new_callable=AsyncMock)
    def test_save_page_rate_limit_includes_retry_after(self, mock_process, client, db_session):
        """Verify 429 response includes Retry-After header."""
        low_limiter = EndpointRateLimiter(max_requests=1, window_seconds=60)
        with patch("src.api.save_routes.save_rate_limiter", low_limiter):
            client.post(
                "/api/v1/content/save-page",
                json={
                    "url": "https://example.com/rl-page-retry-first",
                    "html": "<html><body>First</body></html>",
                },
            )
            resp = client.post(
                "/api/v1/content/save-page",
                json={
                    "url": "https://example.com/rl-page-retry-second",
                    "html": "<html><body>Second</body></html>",
                },
            )
            assert resp.status_code == 429
            assert "retry-after" in resp.headers
            retry_val = int(resp.headers["retry-after"])
            assert 0 < retry_val <= 60
