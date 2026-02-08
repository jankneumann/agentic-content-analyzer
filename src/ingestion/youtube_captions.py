"""LLM-based caption proofreading for YouTube transcripts.

Auto-generated YouTube captions frequently misspell proper nouns phonetically
(e.g., "clawd" instead of "Claude"). This module uses a fast, cheap LLM to
proofread transcript segments with domain-specific hint terms.

Uses a sparse-diff output format: the LLM returns only changed segments
(segment_number: corrected_text) to minimize output tokens.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.config.models import ModelStep, get_model_config
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.ingestion.youtube import TranscriptSegment

logger = get_logger(__name__)

# Built-in default hint terms for AI/tech domain
DEFAULT_HINT_TERMS: list[str] = [
    "Claude",
    "Anthropic",
    "OpenAI",
    "LLaMA",
    "Llama",
    "ChatGPT",
    "Gemini",
    "Mistral",
    "GPT-4",
    "GPT-4o",
    "GPT-5",
    "DeepSeek",
    "Hugging Face",
    "LangChain",
    "LlamaIndex",
    "Midjourney",
    "Stable Diffusion",
    "DALL-E",
    "Sora",
    "Whisper",
    "Copilot",
    "PyTorch",
    "TensorFlow",
    "CUDA",
    "NVIDIA",
    "Groq",
    "Perplexity",
    "Cohere",
    "RAG",
    "LoRA",
    "QLoRA",
    "RLHF",
    "GGUF",
    "ONNX",
    "vLLM",
    "Ollama",
    "CrewAI",
    "AutoGen",
    "Cursor",
    "Replit",
    "Vercel",
    "Supabase",
    "Pinecone",
    "Weaviate",
    "ChromaDB",
    "Milvus",
]

# Batch size for LLM calls (segments per batch)
PROOFREAD_BATCH_SIZE = 50

PROOFREAD_SYSTEM_PROMPT = """You are a transcript proofreader specializing in AI/ML content. \
Your ONLY task is to fix misspelled proper nouns in auto-generated YouTube captions.

RULES:
1. ONLY correct proper noun misspellings (company names, product names, technical terms)
2. Do NOT change grammar, punctuation, sentence structure, or any other text
3. Do NOT paraphrase or rephrase anything
4. Use the hint terms list to guide corrections — these are the correct spellings
5. Be conservative: if you're unsure, leave the text unchanged

HINT TERMS (correct spellings):
{hint_terms}

INPUT FORMAT:
Numbered transcript segments, one per line:
1: segment text here
2: another segment here

OUTPUT FORMAT:
Return ONLY the segments you changed, in JSON format:
{{"corrections": {{"segment_number": "corrected text", ...}}}}

If no corrections are needed, return: {{"corrections": {{}}}}

IMPORTANT: Return ONLY valid JSON. No explanations, no markdown."""


@dataclass
class ProofreadResult:
    """Result of proofreading a transcript."""

    segments: list[TranscriptSegment]
    corrections_count: int
    batches_processed: int


async def proofread_transcript(
    segments: list[TranscriptSegment],
    hint_terms: list[str] | None = None,
    is_auto_generated: bool = True,
    model_step: ModelStep = ModelStep.CAPTION_PROOFREADING,
) -> ProofreadResult:
    """Proofread transcript segments using an LLM.

    Sends segments in batches to a fast LLM with hint terms for
    proper noun correction. Only modifies auto-generated captions.

    Args:
        segments: List of transcript segments to proofread.
        hint_terms: Additional hint terms to merge with built-in defaults.
            Per-playlist additions are merged with DEFAULT_HINT_TERMS.
        is_auto_generated: Whether the captions are auto-generated.
            Manual captions are skipped (returned as-is).
        model_step: ModelStep to use for model selection.

    Returns:
        ProofreadResult with corrected segments and stats.
    """
    if not is_auto_generated:
        logger.info("Skipping proofreading for manual captions")
        return ProofreadResult(segments=segments, corrections_count=0, batches_processed=0)

    if not segments:
        return ProofreadResult(segments=[], corrections_count=0, batches_processed=0)

    # Merge hint terms: built-in defaults + per-source additions
    all_hint_terms = list(DEFAULT_HINT_TERMS)
    if hint_terms:
        # Add per-source terms, avoiding duplicates
        existing = {t.lower() for t in all_hint_terms}
        for term in hint_terms:
            if term.lower() not in existing:
                all_hint_terms.append(term)
                existing.add(term.lower())

    # Get the model for proofreading
    model_config = get_model_config()
    model = model_config.get_model_for_step(model_step)

    from src.services.llm_router import LLMRouter

    router = LLMRouter(model_config)

    # Process in batches
    total_corrections = 0
    batches_processed = 0
    corrected_segments = list(segments)  # Copy to avoid mutating input

    for batch_start in range(0, len(segments), PROOFREAD_BATCH_SIZE):
        batch = segments[batch_start : batch_start + PROOFREAD_BATCH_SIZE]
        batch_corrections = await _proofread_batch(
            router, model, batch, all_hint_terms, batch_start
        )

        # Apply corrections to the copied segments
        for seg_idx, corrected_text in batch_corrections.items():
            abs_idx = batch_start + seg_idx
            if 0 <= abs_idx < len(corrected_segments):
                corrected_segments[abs_idx] = corrected_segments[abs_idx].model_copy(
                    update={"text": corrected_text}
                )
                total_corrections += 1

        batches_processed += 1

    logger.info(
        f"Proofreading complete: {total_corrections} corrections "
        f"across {batches_processed} batches ({len(segments)} segments)"
    )

    return ProofreadResult(
        segments=corrected_segments,
        corrections_count=total_corrections,
        batches_processed=batches_processed,
    )


async def _proofread_batch(
    router,
    model: str,
    batch: list[TranscriptSegment],
    hint_terms: list[str],
    batch_offset: int,
) -> dict[int, str]:
    """Proofread a single batch of segments.

    Args:
        router: LLMRouter instance.
        model: Model ID to use.
        batch: Segment batch to proofread.
        hint_terms: Hint terms for the system prompt.
        batch_offset: Offset of this batch in the full segment list (for logging).

    Returns:
        Dict mapping relative segment index -> corrected text.
    """
    # Build numbered input
    numbered_lines = []
    for i, seg in enumerate(batch):
        numbered_lines.append(f"{i + 1}: {seg.text}")

    user_prompt = "\n".join(numbered_lines)
    system_prompt = PROOFREAD_SYSTEM_PROMPT.format(hint_terms=", ".join(hint_terms))

    try:
        response = await router.generate(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2048,
            temperature=0.1,  # Low temperature for consistent corrections
        )

        return _parse_corrections(response.text, len(batch))

    except Exception as e:
        logger.warning(
            f"Proofreading batch at offset {batch_offset} failed: {e}. "
            "Returning segments unchanged."
        )
        return {}


def _parse_corrections(response_text: str, batch_size: int) -> dict[int, str]:
    """Parse LLM correction response into a segment index -> text mapping.

    Args:
        response_text: Raw LLM response text (expected JSON).
        batch_size: Number of segments in the batch (for validation).

    Returns:
        Dict mapping 0-based segment index -> corrected text.
    """
    if not response_text.strip():
        return {}

    try:
        # Try to extract JSON from the response (handle markdown code blocks)
        json_text = response_text.strip()
        json_match = re.search(r"\{.*\}", json_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(0)

        data = json.loads(json_text)
        corrections = data.get("corrections", {})

        if not isinstance(corrections, dict):
            logger.warning(f"Unexpected corrections format: {type(corrections)}")
            return {}

        # Convert 1-based segment numbers to 0-based indices
        result: dict[int, str] = {}
        for seg_num_str, corrected_text in corrections.items():
            try:
                seg_num = int(seg_num_str)
                seg_idx = seg_num - 1  # Convert to 0-based
                if 0 <= seg_idx < batch_size and isinstance(corrected_text, str):
                    result[seg_idx] = corrected_text
            except (ValueError, TypeError):
                continue

        return result

    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"Failed to parse proofreading response: {e}")
        return {}
