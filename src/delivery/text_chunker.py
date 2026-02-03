"""Text chunking utility for TTS providers.

Provides a reusable text chunking utility that splits text into
provider-appropriate chunks for text-to-speech synthesis, respecting
character limits while maintaining natural speech boundaries.
"""

import re
from dataclasses import dataclass

from src.utils.logging import get_logger

logger = get_logger(__name__)


# Provider character limits (with safety buffer)
# These are safe targets that leave room for SSML tags and edge cases
PROVIDER_CHAR_LIMITS: dict[str, int] = {
    "openai": 3800,  # Actual: 4096
    "elevenlabs": 4500,  # Actual: 5000
    "google": 4500,  # Actual: 5000
    "aws_polly": 2800,  # Actual: 3000
}

# Average speaking rate for duration estimation
WORDS_PER_MINUTE = 150


@dataclass
class TextChunk:
    """A chunk of text prepared for TTS synthesis.

    Represents a portion of text that fits within provider limits,
    along with metadata about its position in the original text.
    """

    text: str
    """The text content of this chunk"""

    position: int
    """0-based chunk index in the sequence"""

    char_start: int
    """Character offset where this chunk starts in the original text"""

    char_end: int
    """Character offset where this chunk ends in the original text"""

    estimated_duration: float
    """Estimated speech duration in seconds (based on ~150 words/minute)"""


class TextChunker:
    """Text chunking utility for TTS providers.

    Splits text into appropriately-sized chunks for TTS synthesis,
    respecting provider character limits while preserving natural
    speech boundaries (paragraphs, sentences, words).

    Example:
        >>> chunker = TextChunker(provider="openai")
        >>> chunks = chunker.chunk("Long text that needs splitting...")
        >>> for chunk in chunks:
        ...     audio = await tts.synthesize(chunk.text)
    """

    def __init__(self, provider: str = "openai", max_chars: int | None = None):
        """Initialize TextChunker with provider or explicit limit.

        Args:
            provider: TTS provider name (openai, elevenlabs, google, aws_polly).
                     Used to determine character limit if max_chars not specified.
            max_chars: Explicit maximum characters per chunk. Overrides provider limit.

        Raises:
            ValueError: If provider is unknown and max_chars not specified.
        """
        self.provider = provider.lower()

        if max_chars is not None:
            self.max_chars = max_chars
        elif self.provider in PROVIDER_CHAR_LIMITS:
            self.max_chars = PROVIDER_CHAR_LIMITS[self.provider]
        else:
            raise ValueError(
                f"Unknown provider '{provider}'. "
                f"Valid providers: {list(PROVIDER_CHAR_LIMITS.keys())}. "
                f"Or specify max_chars explicitly."
            )

        logger.debug(f"TextChunker initialized: provider={provider}, max_chars={self.max_chars}")

    def chunk(self, text: str) -> list[TextChunk]:
        """Split text into chunks respecting provider limits.

        Splitting strategy:
        1. Try to split at paragraph boundaries (double newline)
        2. If paragraph too long, split at sentence boundaries (. ! ?)
        3. If sentence too long, split at word boundaries
        4. Never split mid-word

        Args:
            text: The text to split into chunks.

        Returns:
            List of TextChunk objects, each containing text that fits
            within the provider's character limit.
        """
        if not text or not text.strip():
            logger.debug("Empty text provided, returning empty chunk list")
            return []

        # Normalize whitespace
        text = text.strip()

        # If text fits in one chunk, return it
        if len(text) <= self.max_chars:
            return [
                TextChunk(
                    text=text,
                    position=0,
                    char_start=0,
                    char_end=len(text),
                    estimated_duration=self.estimate_duration(text),
                )
            ]

        chunks: list[TextChunk] = []
        current_pos = 0

        while current_pos < len(text):
            # Get the next chunk
            chunk_text, chunk_end = self._extract_chunk(text, current_pos)

            if chunk_text:
                chunks.append(
                    TextChunk(
                        text=chunk_text.strip(),
                        position=len(chunks),
                        char_start=current_pos,
                        char_end=chunk_end,
                        estimated_duration=self.estimate_duration(chunk_text),
                    )
                )

            current_pos = chunk_end

            # Skip leading whitespace for next chunk
            while current_pos < len(text) and text[current_pos].isspace():
                current_pos += 1

        logger.debug(
            f"Split {len(text)} chars into {len(chunks)} chunks (max_chars={self.max_chars})"
        )

        return chunks

    def _extract_chunk(self, text: str, start: int) -> tuple[str, int]:
        """Extract a single chunk from text starting at the given position.

        Args:
            text: The full text being chunked.
            start: Starting character position.

        Returns:
            Tuple of (chunk_text, end_position).
        """
        remaining = text[start:]

        # If remaining text fits, take it all
        if len(remaining) <= self.max_chars:
            return remaining, len(text)

        # Try to split at paragraph boundary
        chunk_end = self._find_paragraph_break(remaining)
        if chunk_end is not None:
            return remaining[:chunk_end], start + chunk_end

        # Try to split at sentence boundary
        chunk_end = self._find_sentence_break(remaining)
        if chunk_end is not None:
            return remaining[:chunk_end], start + chunk_end

        # Fall back to word boundary
        chunk_end = self._find_word_break(remaining)
        return remaining[:chunk_end], start + chunk_end

    def _find_paragraph_break(self, text: str) -> int | None:
        """Find the last paragraph break within the character limit.

        Args:
            text: Text to search for paragraph breaks.

        Returns:
            Character position after the paragraph break, or None if not found.
        """
        # Look for double newline patterns
        pattern = r"\n\n+"

        # Find all paragraph breaks within limit
        best_break = None
        for match in re.finditer(pattern, text[: self.max_chars]):
            # Include the paragraph break in the chunk
            best_break = match.end()

        # Only use paragraph break if it gives us a reasonable chunk size
        # (at least 20% of max to avoid tiny chunks)
        if best_break is not None and best_break >= self.max_chars * 0.2:
            return best_break

        return None

    def _find_sentence_break(self, text: str) -> int | None:
        """Find the last sentence break within the character limit.

        Args:
            text: Text to search for sentence breaks.

        Returns:
            Character position after the sentence break, or None if not found.
        """
        # Look for sentence-ending punctuation followed by space or end
        # Handle common cases: periods, exclamation, question marks
        # Also handle quotes after punctuation: ." or !'
        pattern = r'[.!?]["\')\]]?\s+'

        best_break = None
        for match in re.finditer(pattern, text[: self.max_chars]):
            best_break = match.end()

        # Also check for sentence ending at the limit boundary
        if best_break is None:
            # Look for punctuation right before the limit
            for i in range(min(len(text), self.max_chars) - 1, max(0, self.max_chars - 20), -1):
                if text[i] in ".!?" and (
                    i + 1 >= len(text) or text[i + 1].isspace() or text[i + 1] in "\"')"
                ):
                    best_break = i + 1
                    break

        # Only use sentence break if it gives us a reasonable chunk size
        if best_break is not None and best_break >= self.max_chars * 0.2:
            return best_break

        return None

    def _find_word_break(self, text: str) -> int:
        """Find the last word break within the character limit.

        This is the fallback when no paragraph or sentence break is found.
        Never splits mid-word.

        Args:
            text: Text to search for word breaks.

        Returns:
            Character position for the word break.
        """
        # Find the last space within limit
        limit = min(len(text), self.max_chars)

        # Search backwards for a space
        for i in range(limit - 1, 0, -1):
            if text[i].isspace():
                return i + 1

        # No space found - extremely long word, just split at limit
        # This should be rare in normal text
        logger.warning(f"No word break found in first {limit} chars, forcing split")
        return limit

    def estimate_duration(self, text: str) -> float:
        """Estimate speech duration for text.

        Uses an average speaking rate of 150 words per minute,
        which is typical for professional narration.

        Args:
            text: Text to estimate duration for.

        Returns:
            Estimated duration in seconds.
        """
        if not text or not text.strip():
            return 0.0

        # Count words (split on whitespace)
        words = len(text.split())

        # Calculate duration: words / (words_per_minute / 60)
        duration = words / (WORDS_PER_MINUTE / 60)

        return round(duration, 2)

    def add_ssml_breaks(
        self, chunks: list[TextChunk], break_time: str = "500ms"
    ) -> list[TextChunk]:
        """Add SSML break tags between chunks for supported providers.

        Creates new TextChunk objects with SSML <break> tags appended
        to the end of each chunk (except the last one).

        Note: Not all providers support SSML. OpenAI TTS does not support SSML,
        while ElevenLabs and Google Cloud TTS do.

        Args:
            chunks: List of TextChunk objects to add breaks to.
            break_time: Duration of break (e.g., "500ms", "1s", "200ms").

        Returns:
            New list of TextChunk objects with SSML breaks added.
        """
        if not chunks:
            return []

        result = []
        for i, chunk in enumerate(chunks):
            if i < len(chunks) - 1:
                # Add break tag to all but last chunk
                new_text = f'{chunk.text} <break time="{break_time}"/>'
                result.append(
                    TextChunk(
                        text=new_text,
                        position=chunk.position,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                        estimated_duration=chunk.estimated_duration,
                    )
                )
            else:
                # Keep last chunk as-is
                result.append(chunk)

        return result

    def get_total_duration(self, chunks: list[TextChunk]) -> float:
        """Calculate total estimated duration for all chunks.

        Args:
            chunks: List of TextChunk objects.

        Returns:
            Total estimated duration in seconds.
        """
        return sum(chunk.estimated_duration for chunk in chunks)
