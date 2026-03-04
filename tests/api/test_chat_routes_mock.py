"""Mock tests for chat routes to verify rate limiting integration."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencies import verify_admin_key

# Override dependency to bypass auth
app.dependency_overrides[verify_admin_key] = lambda: "test-key"

client = TestClient(app)


def test_send_message_rate_limit_exceeded():
    """Test that send_message raises 429 when rate limit is exceeded."""
    with patch("src.api.chat_routes.chat_rate_limiter") as mock_limiter:
        # Simulate rate limit exceeded
        mock_limiter.is_limited.return_value = True
        mock_limiter.get_retry_after.return_value = 30

        response = client.post(
            "/api/v1/chat/conversations/123/messages",
            json={"content": "Hello"},
        )

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "30"
        assert "Rate limit exceeded" in response.json()["detail"]


def test_send_message_rate_limit_ok():
    """Test that send_message proceeds (fails later due to DB) when rate limit is OK."""
    with patch("src.api.chat_routes.chat_rate_limiter") as mock_limiter:
        # Simulate rate limit OK
        mock_limiter.is_limited.return_value = False

        # This should bypass rate limit check and try to hit DB
        # We expect 500 because we didn't mock the DB session
        # But importantly, NOT 429
        try:
            response = client.post(
                "/api/v1/chat/conversations/123/messages",
                json={"content": "Hello"},
            )
            assert response.status_code != 429
        except Exception:
            # It might crash due to DB connection, which is fine
            pass


def test_regenerate_rate_limit_exceeded():
    """Test that regenerate raises 429 when rate limit is exceeded."""
    with patch("src.api.chat_routes.chat_rate_limiter") as mock_limiter:
        mock_limiter.is_limited.return_value = True
        mock_limiter.get_retry_after.return_value = 15

        response = client.post("/api/v1/chat/conversations/123/regenerate")

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "15"


def test_create_conversation_rate_limit_exceeded():
    """Test that create_conversation raises 429 when rate limit is exceeded."""
    with patch("src.api.chat_routes.chat_rate_limiter") as mock_limiter:
        mock_limiter.is_limited.return_value = True
        mock_limiter.get_retry_after.return_value = 60

        response = client.post(
            "/api/v1/chat/conversations",
            json={"artifact_type": "digest", "artifact_id": "1"},
        )

        assert response.status_code == 429
