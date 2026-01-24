# Design: AI Image Generator Service

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer                                 │
│   POST /images/generate    POST /images/suggest                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ImageGenerator Service                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ generate_for_   │  │ generate_for_   │  │ suggest_images  │ │
│  │ summary()       │  │ digest()        │  │ ()              │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │           │
│           └────────────────────┼────────────────────┘           │
│                                ▼                                 │
│                    ImageGeneratorProvider                        │
│                    (Abstract Base Class)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ OpenAI DALL-E   │ │ Stability AI    │ │ Mock Provider   │
│ Provider        │ │ Provider        │ │ (Testing)       │
└─────────────────┘ └─────────────────┘ └─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Image Storage Service                         │
│              (Existing: LocalImageStorage / S3)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Image Database Record                         │
│              (source_type = AI_GENERATED)                        │
└─────────────────────────────────────────────────────────────────┘
```

## Service Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from src.models.image import Image
from src.models.summary import NewsletterSummary
from src.models.digest import Digest


@dataclass
class ImageSuggestion:
    """Suggested image generation for content."""
    prompt: str
    rationale: str
    style: str = "professional"
    placement: str = "after_executive_summary"


@dataclass
class GenerationParams:
    """Parameters for image generation."""
    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "natural"


class ImageGeneratorProvider(ABC):
    """Abstract base class for image generation providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        params: GenerationParams
    ) -> bytes:
        """Generate image from prompt, return raw bytes."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        pass


class OpenAIImageGenerator(ImageGeneratorProvider):
    """DALL-E 3 image generation provider."""

    def __init__(self, api_key: str, model: str = "dall-e-3"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate(
        self,
        prompt: str,
        params: GenerationParams
    ) -> bytes:
        response = await self.client.images.generate(
            model=self.model,
            prompt=prompt,
            size=params.size,
            quality=params.quality,
            style=params.style,
            response_format="b64_json",
        )
        return base64.b64decode(response.data[0].b64_json)

    @property
    def model_name(self) -> str:
        return self.model


class ImageGenerator:
    """High-level service for AI image generation."""

    def __init__(
        self,
        provider: ImageGeneratorProvider,
        storage: ImageStorageProvider,
        db: Session
    ):
        self.provider = provider
        self.storage = storage
        self.db = db

    async def generate_for_summary(
        self,
        summary: NewsletterSummary,
        prompt: str,
        params: GenerationParams | None = None
    ) -> Image:
        """Generate image for a newsletter summary."""
        params = params or GenerationParams()

        # Generate image bytes
        image_bytes = await self.provider.generate(prompt, params)

        # Save to storage
        filename = f"summary_{summary.id}_{uuid4().hex[:8]}.png"
        storage_path = await self.storage.save(image_bytes, filename)

        # Create database record
        image = Image(
            source_type=ImageSource.AI_GENERATED,
            source_summary_id=summary.id,
            storage_path=storage_path,
            storage_provider=self.storage.provider_name,
            filename=filename,
            mime_type="image/png",
            generation_prompt=prompt,
            generation_model=self.provider.model_name,
            generation_params=asdict(params),
        )
        self.db.add(image)
        self.db.commit()

        return image

    async def suggest_images(
        self,
        content: str,
        max_suggestions: int = 3
    ) -> list[ImageSuggestion]:
        """Analyze content and suggest images to generate."""
        # Use LLM to analyze content and generate suggestions
        # This would call Claude/GPT to identify visualization opportunities
        suggestions = await self._analyze_content(content, max_suggestions)
        return suggestions

    async def _analyze_content(
        self,
        content: str,
        max_suggestions: int
    ) -> list[ImageSuggestion]:
        """Use LLM to identify visualization opportunities."""
        # Placeholder for LLM-based content analysis
        # Would return structured suggestions based on content themes
        pass
```

## API Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/images", tags=["images"])


class GenerateRequest(BaseModel):
    """Request to generate an image."""
    prompt: str
    source_type: Literal["summary", "digest"]
    source_id: int
    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "natural"


class GenerateResponse(BaseModel):
    """Response from image generation."""
    image_id: UUID
    url: str
    prompt: str
    model: str


class SuggestRequest(BaseModel):
    """Request for image suggestions."""
    content: str
    max_suggestions: int = 3


class SuggestResponse(BaseModel):
    """Image suggestions for content."""
    suggestions: list[ImageSuggestion]


@router.post("/generate", response_model=GenerateResponse)
async def generate_image(
    request: GenerateRequest,
    generator: ImageGenerator = Depends(get_image_generator),
    db: Session = Depends(get_db),
):
    """Generate a new AI image."""
    if request.source_type == "summary":
        summary = db.get(NewsletterSummary, request.source_id)
        if not summary:
            raise HTTPException(404, "Summary not found")
        image = await generator.generate_for_summary(
            summary,
            request.prompt,
            GenerationParams(
                size=request.size,
                quality=request.quality,
                style=request.style,
            ),
        )
    else:
        # Similar for digest
        pass

    return GenerateResponse(
        image_id=image.id,
        url=image.get_url(),
        prompt=request.prompt,
        model=generator.provider.model_name,
    )


@router.post("/suggest", response_model=SuggestResponse)
async def suggest_images(
    request: SuggestRequest,
    generator: ImageGenerator = Depends(get_image_generator),
):
    """Get image generation suggestions for content."""
    suggestions = await generator.suggest_images(
        request.content,
        request.max_suggestions,
    )
    return SuggestResponse(suggestions=suggestions)
```

## Configuration

```python
# In src/config/settings.py

class Settings(BaseSettings):
    # ... existing settings ...

    # Image Generation
    image_generation_enabled: bool = False
    image_generation_provider: str = "openai"  # "openai", "stability"
    image_generation_model: str = "dall-e-3"
    image_generation_default_size: str = "1024x1024"
    image_generation_default_quality: str = "standard"
    image_generation_default_style: str = "natural"

    # Provider API Keys
    openai_api_key: str | None = None
    stability_api_key: str | None = None
```

## Integration with Review Workflow

The image generator integrates with the existing review workflow:

1. **Reviewer requests image**: During summary/digest review, reviewer can click "Suggest Images"
2. **System analyzes content**: LLM identifies visualization opportunities
3. **Suggestions displayed**: Reviewer sees suggested prompts with rationale
4. **Reviewer generates**: Reviewer can generate, modify prompt, or skip
5. **Image inserted**: Generated image is linked to summary/digest and markdown updated

```python
# In src/services/review_service.py

class ReviewService:
    # ... existing methods ...

    async def request_image_generation(
        self,
        item_type: str,  # "summary" or "digest"
        item_id: int,
        prompt: str,
        placement: str = "after_executive_summary",
    ) -> Image:
        """Request image generation during review."""
        image = await self.image_generator.generate_for_summary(
            summary=self._get_item(item_type, item_id),
            prompt=prompt,
        )

        # Log in revision history
        self._log_revision(
            item_type=item_type,
            item_id=item_id,
            action="image_generated",
            metadata={
                "image_id": str(image.id),
                "prompt": prompt,
                "placement": placement,
            },
        )

        return image
```

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| API costs | High generation costs | Rate limiting, quality tiers, caching |
| Content policy | Generated images may violate policies | Prompt filtering, content moderation |
| Latency | Generation takes 10-30 seconds | Async generation, progress indicators |
| Quality variance | AI output inconsistent | Multiple attempts, style guidelines |
