"""AI Image Generation Service.

Provides AI-powered image generation for newsletter summaries and digests,
with provider abstraction (Gemini Imagen first, future: DALL-E, Stability AI).

Image generation prompts are fully configurable via the prompt management system:
- prompts.yaml defaults: pipeline.image_generation.*
- DB overrides via PromptService
- UI/CLI: aca prompts show pipeline.image_generation.suggestion_system

Architecture:
    ImageGeneratorProvider: Abstract base class for image generation backends
    GeminiImageGenerator: Google Imagen via Vertex AI
    MockImageGenerator: Deterministic provider for testing
    ImageGenerator: High-level orchestrator (provider + storage + prompts + DB)

Usage:
    from src.services.image_generator import ImageGenerator, get_image_generator

    generator = get_image_generator()
    suggestions = await generator.suggest_images(content_text)
    image = await generator.generate_for_summary(summary, prompt="...")
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from src.config.models import ModelStep
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.models.image import Image
    from src.models.summary import Summary
    from src.services.file_storage import FileStorageProvider
    from src.services.llm_router import LLMRouter
    from src.services.prompt_service import PromptService

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GenerationParams:
    """Parameters for image generation."""

    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "natural"


@dataclass
class ImageSuggestion:
    """Suggested image generation for content."""

    prompt: str
    rationale: str
    style: str = "professional"
    placement: str = "after_executive_summary"


@dataclass
class GenerationResult:
    """Result of an image generation call."""

    image_bytes: bytes
    model_name: str
    params: GenerationParams


# ---------------------------------------------------------------------------
# Provider abstraction
# ---------------------------------------------------------------------------


class ImageGeneratorProvider(ABC):
    """Abstract base class for image generation providers."""

    @abstractmethod
    async def generate(self, prompt: str, params: GenerationParams) -> bytes:
        """Generate image from prompt, return raw PNG bytes."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier (e.g., 'gemini/imagen-3.0-generate-001')."""


class GeminiImageGenerator(ImageGeneratorProvider):
    """Google Gemini/Imagen image generation via Vertex AI.

    Requires:
    - google-cloud-aiplatform package (optional extra: image-generation)
    - GOOGLE_CLOUD_PROJECT env var or Settings.google_cloud_project
    - Google Cloud credentials (ADC or GOOGLE_APPLICATION_CREDENTIALS)
    """

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        model: str = "imagen-3.0-generate-001",
    ):
        self._project_id = project_id
        self._location = location
        self._model = model
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy-init Vertex AI SDK to avoid import cost at module load."""
        if self._initialized:
            return
        try:
            from google.cloud import aiplatform  # type: ignore[import-untyped]

            aiplatform.init(project=self._project_id, location=self._location)
            self._initialized = True
        except ImportError:
            raise ImportError(
                "google-cloud-aiplatform is required for Gemini image generation. "
                "Install with: uv sync --extra image-generation"
            )

    async def generate(self, prompt: str, params: GenerationParams) -> bytes:
        """Generate image using Vertex AI Imagen model."""
        self._ensure_initialized()
        from vertexai.preview.vision_models import (
            ImageGenerationModel,  # type: ignore[import-untyped]
        )

        model = ImageGenerationModel.from_pretrained(self._model)

        response = await asyncio.to_thread(
            model.generate_images,
            prompt=prompt,
            number_of_images=1,
            aspect_ratio=self._size_to_aspect_ratio(params.size),
        )

        return response.images[0]._image_bytes

    @staticmethod
    def _size_to_aspect_ratio(size: str) -> str:
        """Convert size string to Imagen aspect ratio."""
        ratios = {
            "1024x1024": "1:1",
            "1024x1792": "9:16",
            "1792x1024": "16:9",
        }
        return ratios.get(size, "1:1")

    @property
    def model_name(self) -> str:
        return f"gemini/{self._model}"


class MockImageGenerator(ImageGeneratorProvider):
    """Deterministic mock provider for testing.

    Returns a minimal 1x1 white PNG so callers can verify the full flow
    without hitting any external API.
    """

    # Minimal 1x1 white PNG (67 bytes)
    _MOCK_PNG = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
        b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
        b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    @property
    def model_name(self) -> str:
        return "mock/test-imagen"

    async def generate(self, prompt: str, params: GenerationParams) -> bytes:
        logger.debug("MockImageGenerator: prompt=%s", prompt[:80])
        return self._MOCK_PNG


# ---------------------------------------------------------------------------
# High-level service
# ---------------------------------------------------------------------------


class ImageGenerator:
    """High-level service for AI image generation.

    Orchestrates:
    1. LLM-based content analysis for image suggestions (configurable prompts)
    2. Image generation via provider (Gemini Imagen, etc.)
    3. Storage and database record creation
    """

    def __init__(
        self,
        provider: ImageGeneratorProvider,
        storage: FileStorageProvider,
        db: Session,
        prompt_service: PromptService | None = None,
        llm_router: LLMRouter | None = None,
    ):
        self.provider = provider
        self.storage = storage
        self.db = db
        self._prompt_service = prompt_service
        self._llm_router = llm_router

    # -- Lazy accessors for optional deps --

    @property
    def prompt_service(self) -> PromptService:
        if self._prompt_service is None:
            from src.services.prompt_service import PromptService

            self._prompt_service = PromptService(self.db)
        return self._prompt_service

    @property
    def llm_router(self) -> LLMRouter:
        if self._llm_router is None:
            from src.config import settings
            from src.services.llm_router import LLMRouter

            self._llm_router = LLMRouter(settings.get_model_config())
        return self._llm_router

    # -- Public API --

    async def generate_for_summary(
        self,
        summary: Summary,
        prompt: str,
        params: GenerationParams | None = None,
    ) -> Image:
        """Generate an image for a newsletter summary.

        Args:
            summary: The summary to attach the image to.
            prompt: Image generation prompt text.
            params: Optional generation parameters (size, quality, style).

        Returns:
            Created Image ORM instance.
        """
        from src.models.image import Image as ImageModel, ImageSource

        params = params or self._default_params()
        image_bytes = await self.provider.generate(prompt, params)

        filename = f"summary_{summary.id}_{uuid4().hex[:8]}.png"
        storage_path = await self.storage.save(image_bytes, filename, "image/png")

        image = ImageModel(
            source_type=ImageSource.AI_GENERATED,
            source_summary_id=summary.id,
            storage_path=storage_path,
            storage_provider=getattr(self.storage, "provider_name", "local"),
            filename=filename,
            mime_type="image/png",
            file_size_bytes=len(image_bytes),
            generation_prompt=prompt,
            generation_model=self.provider.model_name,
            generation_params=asdict(params),
        )
        self.db.add(image)
        self.db.flush()

        logger.info(
            "Generated image for summary %d: %s (%d bytes)",
            summary.id,
            filename,
            len(image_bytes),
        )
        return image

    async def generate_for_digest(
        self,
        digest_id: int,
        prompt: str,
        params: GenerationParams | None = None,
    ) -> Image:
        """Generate an image for a digest.

        Args:
            digest_id: The digest ID to attach the image to.
            prompt: Image generation prompt text.
            params: Optional generation parameters.

        Returns:
            Created Image ORM instance.
        """
        from src.models.image import Image as ImageModel, ImageSource

        params = params or self._default_params()
        image_bytes = await self.provider.generate(prompt, params)

        filename = f"digest_{digest_id}_{uuid4().hex[:8]}.png"
        storage_path = await self.storage.save(image_bytes, filename, "image/png")

        image = ImageModel(
            source_type=ImageSource.AI_GENERATED,
            source_digest_id=digest_id,
            storage_path=storage_path,
            storage_provider=getattr(self.storage, "provider_name", "local"),
            filename=filename,
            mime_type="image/png",
            file_size_bytes=len(image_bytes),
            generation_prompt=prompt,
            generation_model=self.provider.model_name,
            generation_params=asdict(params),
        )
        self.db.add(image)
        self.db.flush()

        logger.info(
            "Generated image for digest %d: %s (%d bytes)",
            digest_id,
            filename,
            len(image_bytes),
        )
        return image

    async def suggest_images(
        self,
        content: str,
        content_type: str = "summary",
        max_suggestions: int = 3,
    ) -> list[ImageSuggestion]:
        """Analyze content and suggest images to generate.

        Uses the configurable prompt at pipeline.image_generation.suggestion_*
        to call an LLM that identifies visualization opportunities.

        Args:
            content: The text content to analyze.
            content_type: "summary" or "digest".
            max_suggestions: Maximum number of suggestions.

        Returns:
            List of ImageSuggestion objects.
        """
        from src.config.models import get_model_config

        model = get_model_config().get_model_for_step(ModelStep.IMAGE_SUGGESTION)

        system_prompt = self.prompt_service.get_pipeline_prompt(
            "image_generation", "suggestion_system"
        )
        user_prompt = self.prompt_service.render(
            "pipeline.image_generation.suggestion_template",
            content=content,
            content_type=content_type,
            max_suggestions=str(max_suggestions),
        )

        response = await self.llm_router.generate(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
        )

        return self._parse_suggestions(response.text)

    async def refine_prompt(
        self,
        original_prompt: str,
        context: str = "",
        style: str = "professional",
        size: str = "1024x1024",
    ) -> str:
        """Refine a rough prompt into a detailed image generation prompt.

        Uses the configurable prompt at pipeline.image_generation.prompt_refinement_*

        Args:
            original_prompt: The rough user-provided prompt.
            context: Optional content context for the image.
            style: Target visual style.
            size: Target image dimensions.

        Returns:
            Refined prompt string.
        """
        from src.config.models import get_model_config

        model = get_model_config().get_model_for_step(ModelStep.IMAGE_SUGGESTION)

        system_prompt = self.prompt_service.get_pipeline_prompt(
            "image_generation", "prompt_refinement_system"
        )
        user_prompt = self.prompt_service.render(
            "pipeline.image_generation.prompt_refinement_template",
            original_prompt=original_prompt,
            context=context,
            style=style,
            size=size,
        )

        response = await self.llm_router.generate(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.5,
        )

        return response.text.strip()

    # -- Helpers --

    def _default_params(self) -> GenerationParams:
        """Load default generation params from settings."""
        from src.config import settings

        return GenerationParams(
            size=settings.image_generation_default_size,
            quality=settings.image_generation_default_quality,
            style=settings.image_generation_default_style,
        )

    @staticmethod
    def _parse_suggestions(text: str) -> list[ImageSuggestion]:
        """Parse LLM response into ImageSuggestion objects."""
        try:
            # Strip markdown code fences if present
            cleaned = text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # Remove first line (```json) and last line (```)
                lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
                cleaned = "\n".join(lines)

            data = json.loads(cleaned)
            if not isinstance(data, list):
                logger.warning("Expected JSON array from suggestion LLM, got %s", type(data))
                return []

            suggestions = []
            for item in data:
                suggestions.append(
                    ImageSuggestion(
                        prompt=item.get("prompt", ""),
                        rationale=item.get("rationale", ""),
                        style=item.get("style", "professional"),
                        placement=item.get("placement", "after_executive_summary"),
                    )
                )
            return suggestions

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse image suggestions: %s", e)
            return []


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_image_generator(
    db: Session | None = None,
    provider: ImageGeneratorProvider | None = None,
) -> ImageGenerator:
    """Factory function for creating an ImageGenerator.

    Args:
        db: Optional DB session (auto-opens if None).
        provider: Optional explicit provider (defaults to settings-based selection).

    Returns:
        Configured ImageGenerator instance.

    Raises:
        ValueError: If image generation is disabled or provider is misconfigured.
    """
    from src.config import settings
    from src.services.file_storage import get_storage
    from src.storage.database import get_db

    if not settings.image_generation_enabled:
        raise ValueError(
            "Image generation is disabled. Set IMAGE_GENERATION_ENABLED=true to enable."
        )

    # Provider selection
    if provider is None:
        provider = _create_provider(settings)

    # Storage
    storage = get_storage(bucket="images")

    # DB session
    if db is None:
        ctx = get_db()
        db = ctx.__enter__()
        # Note: caller is responsible for committing/closing the session.
        # In API routes, the session lifecycle is managed by the route.

    return ImageGenerator(provider=provider, storage=storage, db=db)


def _create_provider(settings: Any) -> ImageGeneratorProvider:
    """Create the appropriate image generation provider from settings."""
    provider_name = settings.image_generation_provider

    if provider_name == "gemini":
        if not settings.google_cloud_project:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT is required for Gemini image generation. "
                "Set it in .env or profiles."
            )
        return GeminiImageGenerator(
            project_id=settings.google_cloud_project,
            location=settings.google_cloud_location,
            model=settings.image_generation_model,
        )
    elif provider_name == "mock":
        return MockImageGenerator()
    else:
        raise ValueError(
            f"Unknown image generation provider: '{provider_name}'. Supported: 'gemini', 'mock'"
        )
