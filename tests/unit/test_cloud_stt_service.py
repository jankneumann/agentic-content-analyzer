"""Unit tests for cloud STT provider abstraction and factory."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from src.config.models import ModelFamily
from src.services.cloud_stt.models import TranscriptResult, TranscriptResultType
from src.services.cloud_stt.service import CloudSTTService


class TestTranscriptResult:
    """Test the TranscriptResult model."""

    def test_interim_result(self):
        result = TranscriptResult(
            type=TranscriptResultType.INTERIM,
            text="hello world",
            cleaned=False,
        )
        assert result.type == "interim"
        assert result.text == "hello world"
        assert result.cleaned is False
        assert result.confidence is None

    def test_final_result_with_confidence(self):
        result = TranscriptResult(
            type=TranscriptResultType.FINAL,
            text="Hello, world!",
            cleaned=True,
            confidence=0.95,
        )
        assert result.type == "final"
        assert result.cleaned is True
        assert result.confidence == 0.95

    def test_error_result(self):
        result = TranscriptResult(
            type=TranscriptResultType.ERROR,
            text="Provider unavailable",
        )
        assert result.type == "error"
        assert result.cleaned is False  # Default

    def test_confidence_range_validation(self):
        """Confidence must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            TranscriptResult(
                type=TranscriptResultType.FINAL,
                text="test",
                confidence=1.5,
            )

    def test_result_serialization(self):
        """Result should serialize to dict for JSON WebSocket messages."""
        result = TranscriptResult(
            type=TranscriptResultType.FINAL,
            text="Clean transcript.",
            cleaned=True,
            confidence=0.92,
        )
        data = result.model_dump()
        assert data["type"] == "final"
        assert data["text"] == "Clean transcript."
        assert data["cleaned"] is True
        assert data["confidence"] == 0.92


class TestTranscriptResultType:
    """Test the TranscriptResultType enum."""

    def test_enum_values(self):
        assert TranscriptResultType.INTERIM == "interim"
        assert TranscriptResultType.FINAL == "final"
        assert TranscriptResultType.ERROR == "error"


class TestCloudSTTServiceFactory:
    """Test provider factory resolution from model family."""

    def _mock_model_config(self, model_id: str, family: ModelFamily):
        """Create a mock model config that returns the given model and family."""
        mock_config = MagicMock()
        mock_config.get_model_for_step.return_value = model_id
        mock_info = MagicMock()
        mock_info.family = family
        mock_config.get_model_info.return_value = mock_info
        return mock_config

    def test_gemini_family_creates_gemini_provider(self):
        mock_config = self._mock_model_config("gemini-2.5-flash", ModelFamily.GEMINI)

        with patch("src.services.cloud_stt.service.get_model_config", return_value=mock_config):
            service = CloudSTTService()
            provider = service.create_provider()

        from src.services.cloud_stt.gemini_provider import GeminiSTTProvider

        assert isinstance(provider, GeminiSTTProvider)

    def test_whisper_family_creates_whisper_provider(self):
        mock_config = self._mock_model_config("whisper-1", ModelFamily.WHISPER)

        with patch("src.services.cloud_stt.service.get_model_config", return_value=mock_config):
            service = CloudSTTService()
            provider = service.create_provider()

        from src.services.cloud_stt.whisper_provider import WhisperSTTProvider

        assert isinstance(provider, WhisperSTTProvider)

    def test_deepgram_family_creates_deepgram_provider(self):
        mock_config = self._mock_model_config("deepgram-nova-3", ModelFamily.DEEPGRAM)

        with patch("src.services.cloud_stt.service.get_model_config", return_value=mock_config):
            service = CloudSTTService()
            provider = service.create_provider()

        from src.services.cloud_stt.deepgram_provider import DeepgramSTTProvider

        assert isinstance(provider, DeepgramSTTProvider)

    def test_unsupported_family_raises(self):
        mock_config = self._mock_model_config("claude-sonnet-4-5", ModelFamily.CLAUDE)

        with patch("src.services.cloud_stt.service.get_model_config", return_value=mock_config):
            service = CloudSTTService()
            with pytest.raises(ValueError, match="does not support cloud STT"):
                service.create_provider()

    def test_api_key_passed_to_provider(self):
        mock_config = self._mock_model_config("gemini-2.5-flash", ModelFamily.GEMINI)

        with patch("src.services.cloud_stt.service.get_model_config", return_value=mock_config):
            service = CloudSTTService()
            provider = service.create_provider(api_key="test-key-123")

        # Provider should have received the api_key
        assert provider._api_key == "test-key-123"
