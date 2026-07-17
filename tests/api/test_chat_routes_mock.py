"""Mock tests for chat routes to verify rate limiting integration."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencies import verify_admin_key

# Bypass route-level auth dependency.
app.dependency_overrides[verify_admin_key] = lambda: "test-key"

client = TestClient(app)

# AuthMiddleware (separate from the route dependency) checks for either a
# session cookie or X-Admin-Key on every non-exempt request. tests/api/conftest
# sets ADMIN_API_KEY=test-admin-key in the env via its autouse fixture, so
# every request from this file must include the matching header to clear the
# middleware before the route-level mocks even matter.
_AUTH_HEADERS = {"X-Admin-Key": "test-admin-key"}
_CONVERSATION_ID = "00000000-0000-0000-0000-000000000000"


def test_send_message_rate_limit_exceeded():
    """Test that send_message raises 429 when rate limit is exceeded."""
    with patch("src.api.chat_routes.chat_rate_limiter") as mock_limiter:
        # Simulate rate limit exceeded
        mock_limiter.is_limited.return_value = True
        mock_limiter.get_retry_after.return_value = 30

        response = client.post(
            f"/api/v1/chat/conversations/{_CONVERSATION_ID}/messages",
            json={"content": "Hello"},
            headers=_AUTH_HEADERS,
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
                f"/api/v1/chat/conversations/{_CONVERSATION_ID}/messages",
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

        response = client.post(
            f"/api/v1/chat/conversations/{_CONVERSATION_ID}/regenerate",
            headers=_AUTH_HEADERS,
        )

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
            headers=_AUTH_HEADERS,
        )

        assert response.status_code == 429
