"""API endpoints for AI image generation.

Provides:
- POST /api/v1/images/generate — Generate a new AI image for a summary or digest
- POST /api/v1/images/suggest — Get LLM-powered image suggestions for content
- POST /api/v1/images/{image_id}/regenerate — Regenerate with same/modified prompt
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/images",
    tags=["images"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    """Request to generate an AI image."""

    prompt: str = Field(..., min_length=1, max_length=2000, description="Image generation prompt")
    source_type: Literal["summary", "digest"] = Field(
        ..., description="Type of content to attach image to"
    )
    source_id: int = Field(..., gt=0, description="ID of the summary or digest")
    size: str = Field(default="1024x1024", description="Image dimensions")
    quality: str = Field(default="standard", description="Generation quality")
    style: str = Field(default="natural", description="Visual style guidance")
    refine_prompt: bool = Field(
        default=False,
        description="If true, refine the prompt via LLM before generating",
    )


class GenerateResponse(BaseModel):
    """Response from image generation."""

    image_id: UUID
    url: str
    prompt: str
    model: str
    file_size_bytes: int


class SuggestRequest(BaseModel):
    """Request for LLM-powered image suggestions."""

    content: str = Field(..., min_length=10, max_length=50000, description="Content to analyze")
    content_type: Literal["summary", "digest"] = Field(
        default="summary", description="Type of content"
    )
    max_suggestions: int = Field(default=3, ge=1, le=10, description="Maximum suggestions")


class SuggestionItem(BaseModel):
    """A single image suggestion."""

    prompt: str
    rationale: str
    style: str
    placement: str


class SuggestResponse(BaseModel):
    """Response with image suggestions."""

    suggestions: list[SuggestionItem]


class RegenerateRequest(BaseModel):
    """Request to regenerate an image."""

    prompt: str | None = Field(
        default=None,
        max_length=2000,
        description="New prompt (uses original if omitted)",
    )
    size: str | None = None
    quality: str | None = None
    style: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/generate",
    response_model=GenerateResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def generate_image(request: GenerateRequest) -> GenerateResponse:
    """Generate an AI image and attach it to a summary or digest.

    The image generation prompt can be customized via the prompt management UI
    at pipeline.image_generation.* keys.
    """
    from src.models.digest import Digest
    from src.models.summary import Summary
    from src.services.image_generator import (
        GenerationParams,
        get_image_generator,
    )

    with get_db() as db:
        try:
            generator = get_image_generator(db=db)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid image generator configuration")

        params = GenerationParams(
            size=request.size,
            quality=request.quality,
            style=request.style,
        )

        prompt = request.prompt
        if request.refine_prompt:
            prompt = await generator.refine_prompt(
                original_prompt=request.prompt,
                style=request.style,
                size=request.size,
            )

        if request.source_type == "summary":
            summary = db.query(Summary).filter(Summary.id == request.source_id).first()
            if not summary:
                raise HTTPException(status_code=404, detail="Summary not found")
            try:
                image = await generator.generate_for_summary(summary, prompt, params)
            except Exception:
                logger.exception("Image generation failed for summary %d", request.source_id)
                raise HTTPException(
                    status_code=502,
                    detail="Image generation failed. The provider may be unavailable.",
                )
        else:
            digest = db.query(Digest).filter(Digest.id == request.source_id).first()
            if not digest:
                raise HTTPException(status_code=404, detail="Digest not found")
            try:
                image = await generator.generate_for_digest(request.source_id, prompt, params)
            except Exception:
                logger.exception("Image generation failed for digest %d", request.source_id)
                raise HTTPException(
                    status_code=502,
                    detail="Image generation failed. The provider may be unavailable.",
                )

        db.commit()

        return GenerateResponse(
            image_id=image.id,
            url=generator.storage.get_url(image.storage_path),
            prompt=prompt,
            model=generator.provider.model_name,
            file_size_bytes=image.file_size_bytes or 0,
        )


@router.post(
    "/suggest",
    response_model=SuggestResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def suggest_images(request: SuggestRequest) -> SuggestResponse:
    """Get LLM-powered image suggestions for content.

    Analyzes the provided content using the configurable prompt at
    pipeline.image_generation.suggestion_* and returns structured suggestions
    with prompts, rationale, and placement hints.
    """
    from src.services.image_generator import get_image_generator

    with get_db() as db:
        try:
            generator = get_image_generator(db=db)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid image generator configuration")
        try:
            suggestions = await generator.suggest_images(
                content=request.content,
                content_type=request.content_type,
                max_suggestions=request.max_suggestions,
            )
        except Exception:
            logger.exception("Image suggestion failed")
            # Graceful degradation — suggestions are advisory, not critical
            return SuggestResponse(suggestions=[])

        return SuggestResponse(
            suggestions=[
                SuggestionItem(
                    prompt=s.prompt,
                    rationale=s.rationale,
                    style=s.style,
                    placement=s.placement,
                )
                for s in suggestions
            ]
        )


@router.post(
    "/{image_id}/regenerate",
    response_model=GenerateResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def regenerate_image(image_id: UUID, request: RegenerateRequest) -> GenerateResponse:
    """Regenerate an existing image with the same or modified prompt.

    If no new prompt is provided, uses the original generation prompt.
    The old storage file is cleaned up after the new image is stored.
    """
    from dataclasses import asdict
    from uuid import uuid4

    from src.models.image import Image
    from src.services.image_generator import GenerationParams, get_image_generator

    with get_db() as db:
        existing = db.query(Image).filter(Image.id == image_id).first()
        if not existing:
            raise HTTPException(status_code=404, detail="Image not found")

        if not existing.generation_prompt:
            raise HTTPException(
                status_code=400,
                detail="Image has no generation prompt (not AI-generated)",
            )

        try:
            generator = get_image_generator(db=db)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid image generator configuration")

        prompt = request.prompt or existing.generation_prompt
        old_params = existing.generation_params or {}
        params = GenerationParams(
            size=request.size or old_params.get("size", "1024x1024"),
            quality=request.quality or old_params.get("quality", "standard"),
            style=request.style or old_params.get("style", "natural"),
        )

        # Generate new image bytes
        try:
            image_bytes = await generator.provider.generate(prompt, params)
        except Exception:
            logger.exception("Image regeneration failed for image %s", image_id)
            raise HTTPException(
                status_code=502,
                detail="Image generation failed. The provider may be unavailable.",
            )

        # Store new image
        filename = f"regen_{uuid4().hex[:8]}.png"
        storage_path = await generator.storage.save(image_bytes, filename, "image/png")

        # Clean up old storage file (best-effort)
        old_path = existing.storage_path
        if old_path:
            try:
                await generator.storage.delete(old_path)
            except Exception:
                logger.warning("Failed to delete old image file: %s", old_path)

        # Update existing record
        existing.storage_path = storage_path
        existing.filename = filename
        existing.file_size_bytes = len(image_bytes)
        existing.generation_prompt = prompt
        existing.generation_model = generator.provider.model_name
        existing.generation_params = asdict(params)

        db.commit()

        return GenerateResponse(
            image_id=existing.id,
            url=generator.storage.get_url(storage_path),
            prompt=prompt,
            model=generator.provider.model_name,
            file_size_bytes=len(image_bytes),
        )
