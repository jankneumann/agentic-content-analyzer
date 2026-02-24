"""API tests for image generation endpoints.

Tests cover:
- POST /api/v1/images/generate (with mock provider)
- POST /api/v1/images/suggest
- POST /api/v1/images/{id}/regenerate
- Validation errors (missing fields, bad source_id)
- Feature disabled behavior
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_image_generator():
    """Create a mock ImageGenerator for testing API routes."""
    from src.services.image_generator import (
        ImageSuggestion,
        MockImageGenerator,
    )

    mock_gen = MagicMock()
    mock_gen.provider = MockImageGenerator()
    mock_gen.storage = MagicMock()
    mock_gen.storage.get_url.return_value = "http://localhost/images/test.png"

    # Mock generate_for_summary
    mock_image = MagicMock()
    mock_image.id = uuid4()
    mock_image.storage_path = "2026/02/23/test.png"
    mock_image.file_size_bytes = 67
    mock_gen.generate_for_summary = AsyncMock(return_value=mock_image)
    mock_gen.generate_for_digest = AsyncMock(return_value=mock_image)

    # Mock suggest_images
    mock_gen.suggest_images = AsyncMock(
        return_value=[
            ImageSuggestion(
                prompt="A diagram of neural networks",
                rationale="Visualizes the key concept",
                style="diagram",
                placement="after_executive_summary",
            )
        ]
    )

    # Mock refine_prompt
    mock_gen.refine_prompt = AsyncMock(return_value="A refined prompt")

    return mock_gen


# ---------------------------------------------------------------------------
# POST /api/v1/images/suggest
# ---------------------------------------------------------------------------


class TestSuggestEndpoint:
    def test_suggest_returns_suggestions(self, client, mock_image_generator):
        with patch(
            "src.services.image_generator.get_image_generator",
            return_value=mock_image_generator,
        ):
            response = client.post(
                "/api/v1/images/suggest",
                json={
                    "content": "AI agents are transforming software development with multi-step reasoning.",
                    "content_type": "summary",
                    "max_suggestions": 2,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["prompt"] == "A diagram of neural networks"
        assert data["suggestions"][0]["style"] == "diagram"

    def test_suggest_validates_content_length(self, client, mock_image_generator):
        with patch(
            "src.services.image_generator.get_image_generator",
            return_value=mock_image_generator,
        ):
            response = client.post(
                "/api/v1/images/suggest",
                json={"content": "short"},  # min_length=10
            )

        assert response.status_code == 422

    def test_suggest_validates_max_suggestions(self, client, mock_image_generator):
        with patch(
            "src.services.image_generator.get_image_generator",
            return_value=mock_image_generator,
        ):
            response = client.post(
                "/api/v1/images/suggest",
                json={"content": "A" * 20, "max_suggestions": 0},  # ge=1
            )

        assert response.status_code == 422

    def test_suggest_validates_content_type(self, client, mock_image_generator):
        """content_type must be 'summary' or 'digest'."""
        with patch(
            "src.services.image_generator.get_image_generator",
            return_value=mock_image_generator,
        ):
            response = client.post(
                "/api/v1/images/suggest",
                json={
                    "content": "A" * 20,
                    "content_type": "invalid_type",
                },
            )

        assert response.status_code == 422

    def test_suggest_returns_empty_on_llm_failure(self, client, mock_image_generator):
        """LLM failures should return empty suggestions, not 500."""
        mock_image_generator.suggest_images = AsyncMock(
            side_effect=RuntimeError("LLM unavailable"),
        )

        with patch(
            "src.services.image_generator.get_image_generator",
            return_value=mock_image_generator,
        ):
            response = client.post(
                "/api/v1/images/suggest",
                json={
                    "content": "AI agents are transforming software development with multi-step reasoning.",
                },
            )

        assert response.status_code == 200
        assert response.json()["suggestions"] == []


# ---------------------------------------------------------------------------
# POST /api/v1/images/generate
# ---------------------------------------------------------------------------


class TestGenerateEndpoint:
    def test_generate_for_summary(self, client, db_session, mock_image_generator):
        from tests.factories.content import ContentFactory
        from tests.factories.summary import SummaryFactory

        content = ContentFactory()
        summary = SummaryFactory(content=content)
        db_session.flush()

        with patch(
            "src.services.image_generator.get_image_generator",
            return_value=mock_image_generator,
        ):
            response = client.post(
                "/api/v1/images/generate",
                json={
                    "prompt": "A professional diagram showing AI trends",
                    "source_type": "summary",
                    "source_id": summary.id,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "image_id" in data
        assert data["model"] == "mock/test-imagen"
        assert data["url"] == "http://localhost/images/test.png"

    def test_generate_with_refine_prompt(self, client, db_session, mock_image_generator):
        from tests.factories.content import ContentFactory
        from tests.factories.summary import SummaryFactory

        content = ContentFactory()
        summary = SummaryFactory(content=content)
        db_session.flush()

        with patch(
            "src.services.image_generator.get_image_generator",
            return_value=mock_image_generator,
        ):
            response = client.post(
                "/api/v1/images/generate",
                json={
                    "prompt": "a cat",
                    "source_type": "summary",
                    "source_id": summary.id,
                    "refine_prompt": True,
                },
            )

        assert response.status_code == 200
        # The refined prompt should be used
        mock_image_generator.refine_prompt.assert_called_once()

    def test_generate_summary_not_found(self, client, mock_image_generator):
        with patch(
            "src.services.image_generator.get_image_generator",
            return_value=mock_image_generator,
        ):
            response = client.post(
                "/api/v1/images/generate",
                json={
                    "prompt": "test prompt for generation",
                    "source_type": "summary",
                    "source_id": 99999,
                },
            )

        assert response.status_code == 404

    def test_generate_validates_empty_prompt(self, client, mock_image_generator):
        with patch(
            "src.services.image_generator.get_image_generator",
            return_value=mock_image_generator,
        ):
            response = client.post(
                "/api/v1/images/generate",
                json={
                    "prompt": "",
                    "source_type": "summary",
                    "source_id": 1,
                },
            )

        assert response.status_code == 422

    def test_generate_for_digest(self, client, db_session, mock_image_generator):
        from tests.factories.digest import DigestFactory

        digest = DigestFactory()
        db_session.flush()

        with patch(
            "src.services.image_generator.get_image_generator",
            return_value=mock_image_generator,
        ):
            response = client.post(
                "/api/v1/images/generate",
                json={
                    "prompt": "Weekly digest hero image with AI theme",
                    "source_type": "digest",
                    "source_id": digest.id,
                },
            )

        assert response.status_code == 200

    def test_generate_returns_502_on_provider_failure(
        self, client, db_session, mock_image_generator
    ):
        """Provider failures should return 502 with meaningful message."""
        from tests.factories.content import ContentFactory
        from tests.factories.summary import SummaryFactory

        content = ContentFactory()
        summary = SummaryFactory(content=content)
        db_session.flush()

        mock_image_generator.generate_for_summary = AsyncMock(
            side_effect=RuntimeError("Provider API unavailable"),
        )

        with patch(
            "src.services.image_generator.get_image_generator",
            return_value=mock_image_generator,
        ):
            response = client.post(
                "/api/v1/images/generate",
                json={
                    "prompt": "Test prompt for generation",
                    "source_type": "summary",
                    "source_id": summary.id,
                },
            )

        assert response.status_code == 502
        assert "provider" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/v1/images/{id}/regenerate
# ---------------------------------------------------------------------------


class TestRegenerateEndpoint:
    def test_regenerate_not_found(self, client, mock_image_generator):
        fake_id = str(uuid4())
        with patch(
            "src.services.image_generator.get_image_generator",
            return_value=mock_image_generator,
        ):
            response = client.post(
                f"/api/v1/images/{fake_id}/regenerate",
                json={},
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Feature flag validation
# ---------------------------------------------------------------------------


class TestFeatureFlag:
    def test_generate_fails_when_disabled(self, client):
        """When IMAGE_GENERATION_ENABLED=false, factory raises ValueError."""
        with patch(
            "src.services.image_generator.get_image_generator",
            side_effect=ValueError("Image generation is disabled"),
        ):
            # ValueError propagates through TestClient — verify it raises
            with pytest.raises(ValueError, match="disabled"):
                client.post(
                    "/api/v1/images/suggest",
                    json={"content": "Test content for suggestions here"},
                )
