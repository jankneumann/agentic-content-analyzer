"""Tests for LLM-based caption proofreading."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.ingestion.youtube_captions import (
    DEFAULT_HINT_TERMS,
    PROOFREAD_BATCH_SIZE,
    _parse_corrections,
    proofread_transcript,
)
from src.models.youtube import TranscriptSegment


def _make_segment(
    text: str, start: float = 0.0, duration: float = 5.0, *, is_generated: bool = True
) -> TranscriptSegment:
    return TranscriptSegment(text=text, start=start, duration=duration, is_generated=is_generated)


class TestParseCorrections:
    """Tests for the sparse-diff response parser."""

    def test_empty_response(self):
        assert _parse_corrections("", 5) == {}

    def test_no_corrections(self):
        result = _parse_corrections('{"corrections": {}}', 5)
        assert result == {}

    def test_single_correction(self):
        response = '{"corrections": {"2": "corrected text"}}'
        result = _parse_corrections(response, 5)
        assert result == {1: "corrected text"}  # 1-based → 0-based

    def test_multiple_corrections(self):
        response = '{"corrections": {"1": "first", "3": "third"}}'
        result = _parse_corrections(response, 5)
        assert result == {0: "first", 2: "third"}

    def test_ignores_out_of_range(self):
        response = '{"corrections": {"1": "ok", "10": "out of range"}}'
        result = _parse_corrections(response, 5)
        assert result == {0: "ok"}

    def test_handles_markdown_code_block(self):
        response = '```json\n{"corrections": {"1": "fixed"}}\n```'
        result = _parse_corrections(response, 5)
        assert result == {0: "fixed"}

    def test_handles_invalid_json(self):
        result = _parse_corrections("not json at all", 5)
        assert result == {}

    def test_handles_non_dict_corrections(self):
        result = _parse_corrections('{"corrections": ["a", "b"]}', 5)
        assert result == {}


class TestProofreadTranscript:
    """Tests for the main proofread_transcript function."""

    @pytest.mark.asyncio
    async def test_skip_manual_captions(self):
        """Manual captions should not be proofread."""
        segments = [_make_segment("Hello world")]
        result = await proofread_transcript(
            segments=segments,
            is_auto_generated=False,
        )
        assert result.corrections_count == 0
        assert result.batches_processed == 0
        assert result.segments == segments

    @pytest.mark.asyncio
    async def test_empty_segments(self):
        result = await proofread_transcript(segments=[], is_auto_generated=True)
        assert result.corrections_count == 0
        assert result.segments == []

    @pytest.mark.asyncio
    async def test_hint_terms_merge(self):
        """Per-source hint terms should merge with defaults."""
        segments = [_make_segment("text")]
        custom_terms = ["CustomTerm", "AnotherTerm"]

        mock_response = AsyncMock()
        mock_response.return_value.text = '{"corrections": {}}'
        mock_response.return_value.input_tokens = 0
        mock_response.return_value.output_tokens = 0

        with (
            patch("src.ingestion.youtube_captions.get_model_config") as mock_config,
            patch("src.services.llm_router.LLMRouter") as mock_router_class,
        ):
            mock_config.return_value.get_model_for_step.return_value = "gemini-2.5-flash-lite"
            mock_router = mock_router_class.return_value
            mock_router.generate = mock_response

            result = await proofread_transcript(
                segments=segments,
                hint_terms=custom_terms,
                is_auto_generated=True,
            )

            # Verify hint terms were passed in the system prompt
            call_kwargs = mock_response.call_args[1]
            system_prompt = call_kwargs["system_prompt"]
            assert "CustomTerm" in system_prompt
            assert "AnotherTerm" in system_prompt
            # Built-in defaults should also be present
            assert "Claude" in system_prompt
            assert "Anthropic" in system_prompt

    @pytest.mark.asyncio
    async def test_corrections_applied(self):
        """Corrections from LLM should be applied to segments."""
        segments = [
            _make_segment("cloud is great", start=0.0),
            _make_segment("open ai released", start=5.0),
            _make_segment("unchanged text", start=10.0),
        ]

        # LLM returns corrections for segments 1 and 2
        mock_response = AsyncMock()
        mock_response.return_value.text = json.dumps(
            {
                "corrections": {
                    "1": "Claude is great",
                    "2": "OpenAI released",
                }
            }
        )
        mock_response.return_value.input_tokens = 100
        mock_response.return_value.output_tokens = 50

        with (
            patch("src.ingestion.youtube_captions.get_model_config") as mock_config,
            patch("src.services.llm_router.LLMRouter") as mock_router_class,
        ):
            mock_config.return_value.get_model_for_step.return_value = "gemini-2.5-flash-lite"
            mock_router = mock_router_class.return_value
            mock_router.generate = mock_response

            result = await proofread_transcript(
                segments=segments,
                is_auto_generated=True,
            )

            assert result.corrections_count == 2
            assert result.segments[0].text == "Claude is great"
            assert result.segments[1].text == "OpenAI released"
            assert result.segments[2].text == "unchanged text"

    @pytest.mark.asyncio
    async def test_llm_failure_returns_unchanged(self):
        """If LLM call fails, segments should be returned unchanged."""
        segments = [_make_segment("original text")]

        mock_response = AsyncMock(side_effect=RuntimeError("API error"))

        with (
            patch("src.ingestion.youtube_captions.get_model_config") as mock_config,
            patch("src.services.llm_router.LLMRouter") as mock_router_class,
        ):
            mock_config.return_value.get_model_for_step.return_value = "gemini-2.5-flash-lite"
            mock_router = mock_router_class.return_value
            mock_router.generate = mock_response

            result = await proofread_transcript(
                segments=segments,
                is_auto_generated=True,
            )

            assert result.corrections_count == 0
            assert result.segments[0].text == "original text"

    def test_default_hint_terms_not_empty(self):
        """Verify the built-in hint terms list is populated."""
        assert len(DEFAULT_HINT_TERMS) > 20
        assert "Claude" in DEFAULT_HINT_TERMS
        assert "Anthropic" in DEFAULT_HINT_TERMS

    def test_batch_size_is_reasonable(self):
        assert PROOFREAD_BATCH_SIZE == 50
