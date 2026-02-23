"""API tests for voice transcript cleanup endpoint."""

from unittest.mock import AsyncMock, patch


class TestVoiceCleanup:
    """Test POST /api/v1/voice/cleanup."""

    def test_cleanup_success(self, client):
        mock_response = AsyncMock()
        mock_response.text = "Fixed grammar and removed filler words."

        with patch("src.services.llm_router.LLMRouter") as mock_router_cls:
            instance = mock_router_cls.return_value
            instance.generate = AsyncMock(return_value=mock_response)

            resp = client.post(
                "/api/v1/voice/cleanup",
                json={"text": "um so like I wanted to uh talk about the API"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "cleaned_text" in data
        assert data["cleaned_text"] == "Fixed grammar and removed filler words."

    def test_cleanup_empty_text(self, client):
        resp = client.post(
            "/api/v1/voice/cleanup",
            json={"text": ""},
        )
        assert resp.status_code == 422  # Pydantic validation (min_length=1)

    def test_cleanup_missing_text(self, client):
        resp = client.post(
            "/api/v1/voice/cleanup",
            json={},
        )
        assert resp.status_code == 422

    def test_cleanup_uses_voice_cleanup_model_step(self, client):
        mock_response = AsyncMock()
        mock_response.text = "Cleaned text."

        with (
            patch("src.config.models.get_model_config") as mock_get_config,
            patch("src.services.llm_router.LLMRouter") as mock_router_cls,
        ):
            mock_config = mock_get_config.return_value
            mock_config.get_model_for_step.return_value = "claude-haiku-4-5"
            instance = mock_router_cls.return_value
            instance.generate = AsyncMock(return_value=mock_response)

            resp = client.post(
                "/api/v1/voice/cleanup",
                json={"text": "hello world"},
            )

            assert resp.status_code == 200
            # Verify it used VOICE_CLEANUP model step
            from src.config.models import ModelStep

            mock_config.get_model_for_step.assert_called_once_with(ModelStep.VOICE_CLEANUP)

    def test_cleanup_llm_error_returns_502(self, client):
        with patch("src.services.llm_router.LLMRouter") as mock_router_cls:
            instance = mock_router_cls.return_value
            instance.generate = AsyncMock(side_effect=RuntimeError("API key missing"))

            resp = client.post(
                "/api/v1/voice/cleanup",
                json={"text": "hello world"},
            )

        assert resp.status_code == 502
        assert "temporarily unavailable" in resp.json()["detail"]

    def test_cleanup_empty_llm_response_returns_original(self, client):
        mock_response = AsyncMock()
        mock_response.text = ""

        with patch("src.services.llm_router.LLMRouter") as mock_router_cls:
            instance = mock_router_cls.return_value
            instance.generate = AsyncMock(return_value=mock_response)

            resp = client.post(
                "/api/v1/voice/cleanup",
                json={"text": "original text"},
            )

        assert resp.status_code == 200
        assert resp.json()["cleaned_text"] == "original text"

    def test_cleanup_none_llm_response_returns_original(self, client):
        mock_response = AsyncMock()
        mock_response.text = None

        with patch("src.services.llm_router.LLMRouter") as mock_router_cls:
            instance = mock_router_cls.return_value
            instance.generate = AsyncMock(return_value=mock_response)

            resp = client.post(
                "/api/v1/voice/cleanup",
                json={"text": "original text"},
            )

        assert resp.status_code == 200
        assert resp.json()["cleaned_text"] == "original text"
