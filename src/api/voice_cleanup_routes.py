"""
Voice Transcript Cleanup API Routes

Endpoint for LLM-based cleanup of raw voice transcripts.
Fixes grammar, removes filler words, and structures text.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

CLEANUP_SYSTEM_PROMPT = """\
You are a text cleanup assistant. Your job is to clean up raw voice transcripts \
into polished, well-structured text.

Rules:
- Fix grammar, punctuation, and capitalization
- Remove filler words ("um", "uh", "like", "you know", "basically", "so")
- Remove false starts and repeated words
- Structure the text with appropriate paragraphs
- If the text contains list-like content, format as bullet points
- If the text contains code or technical terms, preserve them exactly
- Preserve the speaker's intent and meaning — do NOT add information
- Return ONLY the cleaned text with no explanations, preamble, or metadata
- If the input is very short (a few words), just clean it up minimally
"""


class CleanupRequest(BaseModel):
    """Request to clean up a voice transcript."""

    text: str = Field(..., min_length=1, max_length=10000)


class CleanupResponse(BaseModel):
    """Cleaned transcript response."""

    cleaned_text: str


@router.post(
    "/cleanup",
    response_model=CleanupResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def cleanup_transcript(request: CleanupRequest) -> CleanupResponse:
    """Clean up a raw voice transcript using an LLM.

    Fixes grammar, removes filler words, and structures the text
    while preserving the speaker's original intent.
    """
    from src.config.models import ModelStep, get_model_config
    from src.services.llm_router import LLMRouter

    model_config = get_model_config()
    model_id = model_config.get_model_for_step(ModelStep.VOICE_CLEANUP)

    router_instance = LLMRouter(model_config)
    response = await router_instance.generate(
        model=model_id,
        system_prompt=CLEANUP_SYSTEM_PROMPT,
        user_prompt=request.text,
        max_tokens=2048,
        temperature=0.3,
    )

    return CleanupResponse(cleaned_text=response.text.strip())
