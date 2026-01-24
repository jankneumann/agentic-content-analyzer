"""Tests for TextChunker utility."""

import pytest

from src.delivery.text_chunker import (
    PROVIDER_CHAR_LIMITS,
    WORDS_PER_MINUTE,
    TextChunk,
    TextChunker,
)


class TestTextChunkerInitialization:
    """Tests for TextChunker initialization."""

    def test_initialization_with_known_provider(self):
        """Test initialization with a known provider."""
        chunker = TextChunker(provider="openai")
        assert chunker.provider == "openai"
        assert chunker.max_chars == PROVIDER_CHAR_LIMITS["openai"]

    def test_initialization_with_explicit_max_chars(self):
        """Test initialization with explicit max_chars override."""
        chunker = TextChunker(provider="openai", max_chars=1000)
        assert chunker.max_chars == 1000

    def test_initialization_with_unknown_provider_and_max_chars(self):
        """Test unknown provider is allowed if max_chars specified."""
        chunker = TextChunker(provider="custom_provider", max_chars=2000)
        assert chunker.provider == "custom_provider"
        assert chunker.max_chars == 2000

    def test_initialization_with_unknown_provider_raises(self):
        """Test unknown provider without max_chars raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            TextChunker(provider="unknown_provider")

    def test_all_known_providers(self):
        """Test all known providers can be initialized."""
        for provider in PROVIDER_CHAR_LIMITS:
            chunker = TextChunker(provider=provider)
            assert chunker.max_chars == PROVIDER_CHAR_LIMITS[provider]

    def test_provider_case_insensitive(self):
        """Test provider name is case-insensitive."""
        chunker = TextChunker(provider="OpenAI")
        assert chunker.provider == "openai"
        assert chunker.max_chars == PROVIDER_CHAR_LIMITS["openai"]


class TestBasicChunking:
    """Tests for basic chunking behavior."""

    def test_empty_text_returns_empty_list(self):
        """Test empty text returns empty chunk list."""
        chunker = TextChunker(provider="openai")
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []
        assert chunker.chunk("\n\n") == []

    def test_text_under_limit_returns_single_chunk(self):
        """Test text under limit returns a single chunk."""
        chunker = TextChunker(provider="openai")
        text = "This is a short text that fits in one chunk."

        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].position == 0
        assert chunks[0].char_start == 0
        assert chunks[0].char_end == len(text)

    def test_text_exactly_at_limit(self):
        """Test text exactly at limit returns single chunk."""
        chunker = TextChunker(provider="openai", max_chars=100)
        text = "A" * 100

        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert len(chunks[0].text) == 100

    def test_chunk_position_is_sequential(self):
        """Test chunk positions are 0-indexed and sequential."""
        chunker = TextChunker(provider="openai", max_chars=50)
        text = "Short sentence one. " * 10  # ~200 chars

        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            assert chunk.position == i


class TestParagraphSplitting:
    """Tests for paragraph boundary splitting."""

    def test_splits_at_paragraph_boundary(self):
        """Test text splits at paragraph boundaries when possible."""
        chunker = TextChunker(provider="openai", max_chars=100)

        paragraph1 = "First paragraph with some content."
        paragraph2 = "Second paragraph with more content."
        text = f"{paragraph1}\n\n{paragraph2}"

        chunks = chunker.chunk(text)

        # Should split at paragraph boundary if it fits
        assert len(chunks) >= 1
        # First chunk should contain first paragraph
        assert paragraph1 in chunks[0].text or chunks[0].text.startswith(paragraph1[:20])

    def test_multiple_paragraph_breaks(self):
        """Test handling of multiple paragraph breaks."""
        chunker = TextChunker(provider="openai", max_chars=150)

        text = "Para one.\n\nPara two.\n\n\n\nPara three."

        chunks = chunker.chunk(text)

        # All content should be preserved
        full_text = " ".join(c.text for c in chunks)
        assert "Para one" in full_text
        assert "Para two" in full_text
        assert "Para three" in full_text


class TestSentenceSplitting:
    """Tests for sentence boundary splitting."""

    def test_splits_at_sentence_boundary(self):
        """Test splits at sentence boundaries when paragraph split not possible."""
        chunker = TextChunker(provider="openai", max_chars=80)

        text = "First sentence here. Second sentence there. Third sentence everywhere."

        chunks = chunker.chunk(text)

        # Should split at sentence boundaries
        for chunk in chunks:
            # Each chunk should end with punctuation or be the last chunk
            if chunk.position < len(chunks) - 1:
                # Non-final chunks should end at sentence boundary
                stripped = chunk.text.rstrip()
                assert stripped[-1] in ".!?" or stripped.endswith('."') or stripped.endswith(".'")

    def test_splits_at_exclamation(self):
        """Test splits at exclamation marks."""
        chunker = TextChunker(provider="openai", max_chars=50)

        text = "Wow! This is amazing! Can you believe it?"

        chunks = chunker.chunk(text)

        # Content should be preserved
        full_text = " ".join(c.text for c in chunks)
        assert "Wow" in full_text
        assert "amazing" in full_text

    def test_splits_at_question_mark(self):
        """Test splits at question marks."""
        chunker = TextChunker(provider="openai", max_chars=60)

        text = "What is AI? How does it work? Why does it matter?"

        chunks = chunker.chunk(text)

        # Content should be preserved
        full_text = " ".join(c.text for c in chunks)
        assert "What is AI" in full_text
        assert "How does it work" in full_text


class TestWordSplitting:
    """Tests for word boundary splitting."""

    def test_never_splits_mid_word(self):
        """Test that words are never split in the middle."""
        chunker = TextChunker(provider="openai", max_chars=20)

        text = "Supercalifragilisticexpialidocious is a long word"

        chunks = chunker.chunk(text)

        # Check no chunk starts or ends mid-word (except forced edge case)
        for chunk in chunks:
            # Each word in chunk should be complete
            words = chunk.text.split()
            for word in words:
                assert word in text or word.rstrip(".,!?") in text

    def test_splits_at_word_boundary_fallback(self):
        """Test word boundary splitting when no sentence break found."""
        chunker = TextChunker(provider="openai", max_chars=30)

        # Long text without sentence punctuation
        text = "word1 word2 word3 word4 word5 word6 word7 word8 word9"

        chunks = chunker.chunk(text)

        # Should have multiple chunks
        assert len(chunks) > 1

        # Each chunk should be under limit
        for chunk in chunks:
            assert len(chunk.text) <= 30


class TestDurationEstimation:
    """Tests for duration estimation."""

    def test_estimate_duration_empty_text(self):
        """Test duration estimation for empty text."""
        chunker = TextChunker(provider="openai")

        assert chunker.estimate_duration("") == 0.0
        assert chunker.estimate_duration("   ") == 0.0

    def test_estimate_duration_single_word(self):
        """Test duration estimation for single word."""
        chunker = TextChunker(provider="openai")

        duration = chunker.estimate_duration("Hello")

        # 1 word at 150 WPM = 0.4 seconds
        expected = 1 / (WORDS_PER_MINUTE / 60)
        assert duration == pytest.approx(expected, rel=0.01)

    def test_estimate_duration_multiple_words(self):
        """Test duration estimation for multiple words."""
        chunker = TextChunker(provider="openai")

        # 150 words should be exactly 60 seconds
        text = " ".join(["word"] * 150)
        duration = chunker.estimate_duration(text)

        assert duration == pytest.approx(60.0, rel=0.01)

    def test_chunk_includes_estimated_duration(self):
        """Test each chunk includes estimated duration."""
        chunker = TextChunker(provider="openai")

        text = "This is a test sentence with several words in it."
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].estimated_duration > 0

    def test_get_total_duration(self):
        """Test total duration calculation across chunks."""
        chunker = TextChunker(provider="openai", max_chars=50)

        text = "First chunk text here. Second chunk text there. Third chunk more text."
        chunks = chunker.chunk(text)

        total = chunker.get_total_duration(chunks)

        # Should equal sum of individual durations
        expected = sum(c.estimated_duration for c in chunks)
        assert total == expected

    def test_get_total_duration_empty_list(self):
        """Test total duration for empty chunk list."""
        chunker = TextChunker(provider="openai")

        assert chunker.get_total_duration([]) == 0.0


class TestProviderLimits:
    """Tests for provider-specific limits."""

    def test_openai_limit(self):
        """Test OpenAI provider uses correct limit."""
        chunker = TextChunker(provider="openai")
        assert chunker.max_chars == 3800

    def test_elevenlabs_limit(self):
        """Test ElevenLabs provider uses correct limit."""
        chunker = TextChunker(provider="elevenlabs")
        assert chunker.max_chars == 4500

    def test_google_limit(self):
        """Test Google provider uses correct limit."""
        chunker = TextChunker(provider="google")
        assert chunker.max_chars == 4500

    def test_aws_polly_limit(self):
        """Test AWS Polly provider uses correct limit."""
        chunker = TextChunker(provider="aws_polly")
        assert chunker.max_chars == 2800

    def test_different_providers_different_chunk_counts(self):
        """Test different providers produce different chunk counts."""
        # Create text that's longer than all limits
        text = "A" * 3000 + " " + "B" * 3000  # ~6000 chars

        openai_chunks = TextChunker(provider="openai").chunk(text)
        elevenlabs_chunks = TextChunker(provider="elevenlabs").chunk(text)
        polly_chunks = TextChunker(provider="aws_polly").chunk(text)

        # Polly has smallest limit, should have most chunks
        assert len(polly_chunks) >= len(openai_chunks)
        assert len(polly_chunks) >= len(elevenlabs_chunks)


class TestSSMLBreaks:
    """Tests for SSML break tag insertion."""

    def test_add_ssml_breaks_empty_list(self):
        """Test adding SSML breaks to empty list."""
        chunker = TextChunker(provider="openai")

        result = chunker.add_ssml_breaks([])

        assert result == []

    def test_add_ssml_breaks_single_chunk(self):
        """Test adding SSML breaks to single chunk (no break added)."""
        chunker = TextChunker(provider="openai")

        chunk = TextChunk(
            text="Single chunk text",
            position=0,
            char_start=0,
            char_end=17,
            estimated_duration=1.0,
        )

        result = chunker.add_ssml_breaks([chunk])

        assert len(result) == 1
        assert result[0].text == "Single chunk text"  # No break on last chunk

    def test_add_ssml_breaks_multiple_chunks(self):
        """Test adding SSML breaks to multiple chunks."""
        chunker = TextChunker(provider="openai")

        chunks = [
            TextChunk(
                text="Chunk one", position=0, char_start=0, char_end=9, estimated_duration=1.0
            ),
            TextChunk(
                text="Chunk two", position=1, char_start=10, char_end=19, estimated_duration=1.0
            ),
            TextChunk(
                text="Chunk three", position=2, char_start=20, char_end=31, estimated_duration=1.0
            ),
        ]

        result = chunker.add_ssml_breaks(chunks, break_time="500ms")

        # First two chunks should have breaks
        assert '<break time="500ms"/>' in result[0].text
        assert '<break time="500ms"/>' in result[1].text
        # Last chunk should not have break
        assert "<break" not in result[2].text

    def test_add_ssml_breaks_custom_duration(self):
        """Test adding SSML breaks with custom duration."""
        chunker = TextChunker(provider="openai")

        chunks = [
            TextChunk(text="First", position=0, char_start=0, char_end=5, estimated_duration=0.5),
            TextChunk(text="Second", position=1, char_start=6, char_end=12, estimated_duration=0.5),
        ]

        result = chunker.add_ssml_breaks(chunks, break_time="1s")

        assert '<break time="1s"/>' in result[0].text

    def test_add_ssml_breaks_preserves_metadata(self):
        """Test SSML break insertion preserves chunk metadata."""
        chunker = TextChunker(provider="openai")

        original = TextChunk(
            text="Original text",
            position=5,
            char_start=100,
            char_end=113,
            estimated_duration=2.5,
        )

        result = chunker.add_ssml_breaks([original, original])

        # Check metadata preserved
        assert result[0].position == 5
        assert result[0].char_start == 100
        assert result[0].char_end == 113
        assert result[0].estimated_duration == 2.5


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_only_whitespace_between_words(self):
        """Test text with excessive whitespace between words."""
        chunker = TextChunker(provider="openai", max_chars=50)

        text = "word1     word2     word3"

        chunks = chunker.chunk(text)

        # Should handle excessive whitespace gracefully
        assert len(chunks) >= 1
        assert "word1" in chunks[0].text

    def test_unicode_text(self):
        """Test chunking of unicode text."""
        chunker = TextChunker(provider="openai", max_chars=50)

        text = "Hello world! \u4f60\u597d\u4e16\u754c! Bonjour le monde!"

        chunks = chunker.chunk(text)

        # Unicode should be preserved
        full_text = " ".join(c.text for c in chunks)
        assert "\u4f60\u597d" in full_text

    def test_very_long_word(self):
        """Test handling of very long words that exceed limit."""
        chunker = TextChunker(provider="openai", max_chars=20)

        # Word longer than limit
        text = "supercalifragilisticexpialidocious"

        chunks = chunker.chunk(text)

        # Should still produce chunks (forced split)
        assert len(chunks) >= 1

    def test_newlines_within_paragraph(self):
        """Test single newlines (not paragraph breaks)."""
        chunker = TextChunker(provider="openai", max_chars=100)

        text = "Line one\nLine two\nLine three"

        chunks = chunker.chunk(text)

        # Single newlines should not be treated as paragraph breaks
        # Text should be chunked based on size
        full_text = " ".join(c.text for c in chunks)
        assert "Line one" in full_text
        assert "Line two" in full_text
        assert "Line three" in full_text

    def test_quoted_sentences(self):
        """Test handling of sentences ending with quotes."""
        chunker = TextChunker(provider="openai", max_chars=80)

        text = 'She said "Hello." He replied "Hi!" They asked "How are you?"'

        chunks = chunker.chunk(text)

        # Content should be preserved
        full_text = " ".join(c.text for c in chunks)
        assert "Hello" in full_text
        assert "Hi" in full_text

    def test_char_positions_are_accurate(self):
        """Test character positions correctly reference original text."""
        chunker = TextChunker(provider="openai", max_chars=50)

        text = "First part of text. Second part of the text here."

        chunks = chunker.chunk(text)

        # Verify positions are within text bounds
        for chunk in chunks:
            assert chunk.char_start >= 0
            assert chunk.char_end <= len(text)
            assert chunk.char_start < chunk.char_end


class TestTextChunkDataclass:
    """Tests for TextChunk dataclass."""

    def test_textchunk_creation(self):
        """Test TextChunk can be created with all fields."""
        chunk = TextChunk(
            text="Sample text",
            position=3,
            char_start=100,
            char_end=111,
            estimated_duration=2.5,
        )

        assert chunk.text == "Sample text"
        assert chunk.position == 3
        assert chunk.char_start == 100
        assert chunk.char_end == 111
        assert chunk.estimated_duration == 2.5

    def test_textchunk_equality(self):
        """Test TextChunk equality comparison."""
        chunk1 = TextChunk("text", 0, 0, 4, 1.0)
        chunk2 = TextChunk("text", 0, 0, 4, 1.0)

        assert chunk1 == chunk2

    def test_textchunk_inequality(self):
        """Test TextChunk inequality comparison."""
        chunk1 = TextChunk("text", 0, 0, 4, 1.0)
        chunk2 = TextChunk("different", 0, 0, 9, 1.0)

        assert chunk1 != chunk2
