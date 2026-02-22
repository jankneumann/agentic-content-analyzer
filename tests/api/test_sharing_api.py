"""Tests for content sharing API endpoints.

Tests both the share management endpoints (POST/GET/DELETE /api/v1/{type}/{id}/share)
and the public shared content endpoints (GET /shared/{type}/{token}).
"""

import uuid

# ============================================================================
# Share Management API Tests
# ============================================================================


class TestEnableSharing:
    """Tests for POST /api/v1/{resource}/{id}/share."""

    def test_enable_sharing_content(self, client, sample_content):
        """Enable sharing for a content item."""
        response = client.post(f"/api/v1/contents/{sample_content.id}/share")
        assert response.status_code == 200

        data = response.json()
        assert data["is_public"] is True
        assert data["share_token"] is not None
        assert len(data["share_token"]) == 36  # UUID4 length
        assert "/shared/content/" in data["share_url"]
        assert data["share_token"] in data["share_url"]

    def test_enable_sharing_summary(self, client, sample_summary):
        """Enable sharing for a summary."""
        response = client.post(f"/api/v1/summaries/{sample_summary.id}/share")
        assert response.status_code == 200

        data = response.json()
        assert data["is_public"] is True
        assert data["share_token"] is not None
        assert "/shared/summary/" in data["share_url"]

    def test_enable_sharing_digest(self, client, sample_digest):
        """Enable sharing for a digest."""
        response = client.post(f"/api/v1/digests/{sample_digest.id}/share")
        assert response.status_code == 200

        data = response.json()
        assert data["is_public"] is True
        assert data["share_token"] is not None
        assert "/shared/digest/" in data["share_url"]

    def test_enable_sharing_preserves_token(self, client, sample_content, db_session):
        """Re-enabling sharing preserves the existing token."""
        # Enable sharing
        resp1 = client.post(f"/api/v1/contents/{sample_content.id}/share")
        token1 = resp1.json()["share_token"]

        # Disable sharing
        client.delete(f"/api/v1/contents/{sample_content.id}/share")

        # Re-enable — same token
        resp2 = client.post(f"/api/v1/contents/{sample_content.id}/share")
        token2 = resp2.json()["share_token"]

        assert token1 == token2

    def test_enable_sharing_nonexistent_resource(self, client):
        """404 for nonexistent resource ID."""
        response = client.post("/api/v1/contents/99999/share")
        assert response.status_code == 404

    def test_enable_sharing_unknown_resource_type(self, client):
        """404 for unknown resource type."""
        response = client.post("/api/v1/foobar/1/share")
        assert response.status_code == 404


class TestGetShareStatus:
    """Tests for GET /api/v1/{resource}/{id}/share."""

    def test_get_share_status_not_shared(self, client, sample_content):
        """Content that hasn't been shared returns is_public=False."""
        response = client.get(f"/api/v1/contents/{sample_content.id}/share")
        assert response.status_code == 200

        data = response.json()
        assert data["is_public"] is False
        assert data["share_token"] is None
        assert data["share_url"] is None

    def test_get_share_status_shared(self, client, sample_content):
        """Shared content returns status with token and URL."""
        # Enable first
        client.post(f"/api/v1/contents/{sample_content.id}/share")

        response = client.get(f"/api/v1/contents/{sample_content.id}/share")
        assert response.status_code == 200

        data = response.json()
        assert data["is_public"] is True
        assert data["share_token"] is not None
        assert data["share_url"] is not None

    def test_get_share_status_disabled(self, client, sample_content):
        """Disabled sharing preserves token but is_public=False."""
        client.post(f"/api/v1/contents/{sample_content.id}/share")
        client.delete(f"/api/v1/contents/{sample_content.id}/share")

        response = client.get(f"/api/v1/contents/{sample_content.id}/share")
        data = response.json()
        assert data["is_public"] is False
        assert data["share_token"] is not None  # Preserved
        assert data["share_url"] is not None  # Still valid, even if not public


class TestDisableSharing:
    """Tests for DELETE /api/v1/{resource}/{id}/share."""

    def test_disable_sharing(self, client, sample_content):
        """Disable sharing sets is_public=False but preserves token."""
        client.post(f"/api/v1/contents/{sample_content.id}/share")

        response = client.delete(f"/api/v1/contents/{sample_content.id}/share")
        assert response.status_code == 200

        data = response.json()
        assert data["is_public"] is False
        assert data["share_token"] is not None  # Preserved
        assert data["share_url"] is None  # Not available when disabled

    def test_disable_sharing_not_shared(self, client, sample_content):
        """Disabling sharing on unshared content works fine."""
        response = client.delete(f"/api/v1/contents/{sample_content.id}/share")
        assert response.status_code == 200
        assert response.json()["is_public"] is False


# ============================================================================
# Public Shared Content Tests
# ============================================================================


class TestSharedContentEndpoints:
    """Tests for GET /shared/{type}/{token}."""

    def test_view_shared_content_json(self, client, sample_content, db_session):
        """View shared content as JSON (no Accept: text/html header)."""
        # Enable sharing
        resp = client.post(f"/api/v1/contents/{sample_content.id}/share")
        token = resp.json()["share_token"]

        # Access shared content
        response = client.get(
            f"/shared/content/{token}",
            headers={"Accept": "application/json", "X-Admin-Key": ""},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["title"] == sample_content.title
        assert data["markdown_content"] == sample_content.markdown_content
        assert data["author"] == sample_content.author

    def test_view_shared_content_html(self, client, sample_content, db_session):
        """View shared content as HTML."""
        resp = client.post(f"/api/v1/contents/{sample_content.id}/share")
        token = resp.json()["share_token"]

        response = client.get(
            f"/shared/content/{token}",
            headers={"Accept": "text/html", "X-Admin-Key": ""},
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert sample_content.title in response.text
        assert "Shared via Newsletter Aggregator" in response.text

    def test_shared_content_invalid_token(self, client):
        """Invalid token returns 404."""
        fake_token = str(uuid.uuid4())
        response = client.get(
            f"/shared/content/{fake_token}",
            headers={"X-Admin-Key": ""},
        )
        assert response.status_code == 404

    def test_shared_content_disabled(self, client, sample_content, db_session):
        """Disabled shared content returns 404."""
        resp = client.post(f"/api/v1/contents/{sample_content.id}/share")
        token = resp.json()["share_token"]

        # Disable sharing
        client.delete(f"/api/v1/contents/{sample_content.id}/share")

        response = client.get(
            f"/shared/content/{token}",
            headers={"X-Admin-Key": ""},
        )
        assert response.status_code == 404

    def test_view_shared_summary_json(self, client, sample_summary, db_session):
        """View shared summary as JSON."""
        resp = client.post(f"/api/v1/summaries/{sample_summary.id}/share")
        token = resp.json()["share_token"]

        response = client.get(
            f"/shared/summary/{token}",
            headers={"Accept": "application/json", "X-Admin-Key": ""},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["executive_summary"] == sample_summary.executive_summary
        assert data["key_themes"] == sample_summary.key_themes

    def test_view_shared_summary_html(self, client, sample_summary, db_session):
        """View shared summary as HTML."""
        resp = client.post(f"/api/v1/summaries/{sample_summary.id}/share")
        token = resp.json()["share_token"]

        response = client.get(
            f"/shared/summary/{token}",
            headers={"Accept": "text/html", "X-Admin-Key": ""},
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Executive Summary" in response.text

    def test_view_shared_digest_json(self, client, sample_digest, db_session):
        """View shared digest as JSON."""
        resp = client.post(f"/api/v1/digests/{sample_digest.id}/share")
        token = resp.json()["share_token"]

        response = client.get(
            f"/shared/digest/{token}",
            headers={"Accept": "application/json", "X-Admin-Key": ""},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["title"] == sample_digest.title
        assert data["executive_overview"] == sample_digest.executive_overview

    def test_view_shared_digest_html(self, client, sample_digest, db_session):
        """View shared digest as HTML with OG tags."""
        resp = client.post(f"/api/v1/digests/{sample_digest.id}/share")
        token = resp.json()["share_token"]

        response = client.get(
            f"/shared/digest/{token}",
            headers={"Accept": "text/html", "X-Admin-Key": ""},
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert sample_digest.title in response.text
        assert "og:title" in response.text
        assert "Shared via Newsletter Aggregator" in response.text


class TestSharedAudioEndpoint:
    """Tests for GET /shared/audio/{token}."""

    def test_shared_audio_no_audio(self, client, sample_digest, db_session):
        """404 when digest has no audio."""
        resp = client.post(f"/api/v1/digests/{sample_digest.id}/share")
        token = resp.json()["share_token"]

        response = client.get(
            f"/shared/audio/{token}",
            headers={"X-Admin-Key": ""},
            follow_redirects=False,
        )
        assert response.status_code == 404

    def test_shared_audio_invalid_token(self, client):
        """Invalid token returns 404."""
        fake_token = str(uuid.uuid4())
        response = client.get(
            f"/shared/audio/{fake_token}",
            headers={"X-Admin-Key": ""},
            follow_redirects=False,
        )
        assert response.status_code == 404


# ============================================================================
# Rate Limiting Tests
# ============================================================================


class TestShareRateLimiter:
    """Tests for the share rate limiter."""

    def test_rate_limiter_allows_normal_traffic(self):
        """Rate limiter allows requests under the limit."""
        from src.api.share_rate_limiter import ShareRateLimiter

        limiter = ShareRateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_limited("192.168.1.1") is False

    def test_rate_limiter_blocks_excess_traffic(self):
        """Rate limiter blocks after exceeding limit."""
        from src.api.share_rate_limiter import ShareRateLimiter

        limiter = ShareRateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.is_limited("192.168.1.1")

        assert limiter.is_limited("192.168.1.1") is True

    def test_rate_limiter_per_ip_isolation(self):
        """Different IPs have independent limits."""
        from src.api.share_rate_limiter import ShareRateLimiter

        limiter = ShareRateLimiter(max_requests=2, window_seconds=60)
        for _ in range(2):
            limiter.is_limited("192.168.1.1")

        # Different IP should not be limited
        assert limiter.is_limited("192.168.1.2") is False

    def test_rate_limiter_retry_after(self):
        """Retry-After returns positive value when blocked."""
        from src.api.share_rate_limiter import ShareRateLimiter

        limiter = ShareRateLimiter(max_requests=2, window_seconds=60)
        for _ in range(2):
            limiter.is_limited("192.168.1.1")

        retry = limiter.get_retry_after("192.168.1.1")
        assert retry > 0
        assert retry <= 60

    def test_rate_limiter_retry_after_not_blocked(self):
        """Retry-After returns 0 when not blocked."""
        from src.api.share_rate_limiter import ShareRateLimiter

        limiter = ShareRateLimiter(max_requests=10, window_seconds=60)
        assert limiter.get_retry_after("192.168.1.1") == 0


# ============================================================================
# Token Generation Tests
# ============================================================================


class TestTokenGeneration:
    """Tests for share token generation."""

    def test_token_is_valid_uuid4(self, client, sample_content):
        """Generated token is a valid UUID4."""
        resp = client.post(f"/api/v1/contents/{sample_content.id}/share")
        token = resp.json()["share_token"]

        # Should not raise
        parsed = uuid.UUID(token, version=4)
        assert str(parsed) == token

    def test_tokens_are_unique(self, client, sample_contents, db_session):
        """Each resource gets a unique token."""
        tokens = set()
        for content in sample_contents:
            resp = client.post(f"/api/v1/contents/{content.id}/share")
            tokens.add(resp.json()["share_token"])

        assert len(tokens) == len(sample_contents)
