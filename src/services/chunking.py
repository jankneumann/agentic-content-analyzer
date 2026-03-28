"""Pluggable document chunking service for search indexing.

Provides a ChunkingStrategy protocol with built-in strategies for different
content types (PDFs, YouTube transcripts, Gemini summaries, markdown, digests).
Strategy selection is automatic based on Content.parser_used, with optional
per-source overrides via sources.d/ configuration.

Usage:
    service = ChunkingService()
    chunks = service.chunk_content(content, source_config=source_entry)
"""

from __future__ import annotations

import logging
import re
from typing import Protocol, runtime_checkable

from src.config.settings import get_settings
from src.models.chunk import ChunkType, DocumentChunk

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for performance
TABLE_PATTERN = re.compile(r"(\|.+\|[\s\S]*?\|.+\|)", re.MULTILINE)
TIMESTAMP_PATTERN = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]\(([^)]+)\)")
CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```", re.MULTILINE)

# Token encoder for chunk size estimation — lazy-initialized
_encoder = None


def _get_encoder():  # type: ignore[no-untyped-def]
    """Lazy-initialize the tiktoken encoder."""
    global _encoder
    if _encoder is None:
        import tiktoken

        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def _count_tokens(text: str) -> int:
    """Count tokens using tiktoken cl100k_base encoding."""
    return len(_get_encoder().encode(text))


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences at sentence boundaries."""
    # Split on sentence-ending punctuation followed by whitespace
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p for p in parts if p.strip()]


def _split_oversized_chunk(
    text: str,
    chunk_type: str,
    chunk_size: int,
    chunk_overlap: int,
    base_metadata: dict,
) -> list[DocumentChunk]:
    """Split an oversized chunk into smaller pieces at sentence boundaries.

    Used as a fallback when any strategy produces a chunk exceeding the
    configured max size. Tables are allowed to exceed the limit (kept whole).
    """
    if chunk_type == ChunkType.TABLE:
        # Tables kept whole even if oversized
        chunk = DocumentChunk()
        chunk.chunk_text = text
        chunk.chunk_type = chunk_type
        for k, v in base_metadata.items():
            if hasattr(chunk, k):
                setattr(chunk, k, v)
        return [chunk]

    sentences = _split_into_sentences(text)
    if not sentences:
        return []

    chunks = []
    current_sentences: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = _count_tokens(sentence)

        if current_tokens + sentence_tokens > chunk_size and current_sentences:
            # Emit current chunk
            chunk = DocumentChunk()
            chunk.chunk_text = " ".join(current_sentences)
            chunk.chunk_type = chunk_type
            for k, v in base_metadata.items():
                if hasattr(chunk, k):
                    setattr(chunk, k, v)
            chunks.append(chunk)

            # Keep overlap sentences
            overlap_tokens = 0
            overlap_sentences: list[str] = []
            for s in reversed(current_sentences):
                s_tokens = _count_tokens(s)
                if overlap_tokens + s_tokens > chunk_overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_tokens += s_tokens

            current_sentences = overlap_sentences
            current_tokens = overlap_tokens

        current_sentences.append(sentence)
        current_tokens += sentence_tokens

    # Emit final chunk
    if current_sentences:
        chunk = DocumentChunk()
        chunk.chunk_text = " ".join(current_sentences)
        chunk.chunk_type = chunk_type
        for k, v in base_metadata.items():
            if hasattr(chunk, k):
                setattr(chunk, k, v)
        chunks.append(chunk)

    return chunks


@runtime_checkable
class ChunkingStrategy(Protocol):
    """Protocol for pluggable document chunking implementations."""

    @property
    def name(self) -> str: ...

    def chunk(
        self,
        content: str,
        metadata: dict,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> list[DocumentChunk]: ...


class StructuredChunkingStrategy:
    """For DoclingParser output: heading hierarchy, tables, page breaks.

    Splits on H1-H6 boundaries, extracts tables as separate chunks,
    tracks page numbers from metadata, handles oversized sections.
    """

    @property
    def name(self) -> str:
        return "structured"

    def chunk(
        self,
        content: str,
        metadata: dict,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> list[DocumentChunk]:
        if not content or not content.strip():
            return []

        chunks: list[DocumentChunk] = []
        # Split by headings (H1-H6)
        sections = re.split(r"(?=^#{1,6}\s)", content, flags=re.MULTILINE)

        section_path_parts: list[str] = []

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Extract heading if present
            heading_match = re.match(r"^(#{1,6})\s+(.+?)$", section, re.MULTILINE)
            heading_text = None
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                # Update section path
                section_path_parts = section_path_parts[: level - 1]
                section_path_parts.append(f"{'#' * level} {heading_text}")

            section_path = " > ".join(section_path_parts) if section_path_parts else None

            # Check for tables (```table or | header | format)
            tables = TABLE_PATTERN.findall(section)
            non_table_text = TABLE_PATTERN.sub("", section).strip()

            # Chunk non-table text
            if non_table_text:
                tokens = _count_tokens(non_table_text)
                if tokens <= chunk_size:
                    chunk = DocumentChunk()
                    chunk.chunk_text = non_table_text
                    chunk.chunk_type = ChunkType.PARAGRAPH
                    chunk.section_path = section_path
                    chunk.heading_text = heading_text
                    chunk.page_number = metadata.get("page_number")
                    chunks.append(chunk)
                else:
                    sub_chunks = _split_oversized_chunk(
                        non_table_text,
                        ChunkType.PARAGRAPH,
                        chunk_size,
                        chunk_overlap,
                        {
                            "section_path": section_path,
                            "heading_text": heading_text,
                            "page_number": metadata.get("page_number"),
                        },
                    )
                    chunks.extend(sub_chunks)

            # Each table as its own chunk
            for table in tables:
                chunk = DocumentChunk()
                # Prepend heading as context
                if heading_text:
                    chunk.chunk_text = f"{heading_text}\n\n{table.strip()}"
                else:
                    chunk.chunk_text = table.strip()
                chunk.chunk_type = ChunkType.TABLE
                chunk.section_path = section_path
                chunk.heading_text = heading_text
                chunks.append(chunk)

        # Assign chunk_index
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i

        return chunks


class YouTubeTranscriptChunkingStrategy:
    """For youtube_transcript_api output: timestamped paragraph windows.

    Parses markdown with [MM:SS](url&t=N) format, groups into ~30-second
    windows, extracts timestamp metadata and deep-link URLs.
    """

    @property
    def name(self) -> str:
        return "youtube_transcript"

    def chunk(
        self,
        content: str,
        metadata: dict,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> list[DocumentChunk]:
        if not content or not content.strip():
            return []

        chunks: list[DocumentChunk] = []
        # Parse timestamped segments: [MM:SS](url&t=N) or [HH:MM:SS](url)

        # Split by paragraphs (double newline)
        paragraphs = re.split(r"\n\n+", content)

        current_text: list[str] = []
        current_tokens = 0
        current_start_time: float | None = None
        current_end_time: float | None = None
        current_deep_link: str | None = None

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Extract timestamp from paragraph
            ts_match = TIMESTAMP_PATTERN.search(para)
            if ts_match:
                ts_str = ts_match.group(1)
                link = ts_match.group(2)
                parts = ts_str.split(":")
                if len(parts) == 2:
                    seconds = int(parts[0]) * 60 + int(parts[1])
                else:
                    seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

                if current_start_time is None:
                    current_start_time = float(seconds)
                    current_deep_link = link
                current_end_time = float(seconds)

            para_tokens = _count_tokens(para)

            if current_tokens + para_tokens > chunk_size and current_text:
                # Emit chunk
                chunk = DocumentChunk()
                chunk.chunk_text = "\n\n".join(current_text)
                chunk.chunk_type = ChunkType.TRANSCRIPT
                chunk.timestamp_start = current_start_time
                chunk.timestamp_end = current_end_time
                chunk.deep_link_url = current_deep_link
                chunks.append(chunk)

                # Reset with overlap
                current_text = current_text[-1:]  # Keep last paragraph as overlap
                current_tokens = _count_tokens(current_text[0]) if current_text else 0
                current_start_time = current_end_time
                current_deep_link = None

            current_text.append(para)
            current_tokens += para_tokens

        # Emit final chunk
        if current_text:
            chunk = DocumentChunk()
            chunk.chunk_text = "\n\n".join(current_text)
            chunk.chunk_type = ChunkType.TRANSCRIPT
            chunk.timestamp_start = current_start_time
            chunk.timestamp_end = current_end_time
            chunk.deep_link_url = current_deep_link
            chunks.append(chunk)

        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i

        return chunks


class GeminiSummaryChunkingStrategy:
    """For Gemini-processed YouTube content (parser_used='gemini').

    Splits on topic section headers (## Topic N: ...).
    No timestamp handling (Gemini output has no timestamps).
    """

    @property
    def name(self) -> str:
        return "gemini_summary"

    def chunk(
        self,
        content: str,
        metadata: dict,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> list[DocumentChunk]:
        if not content or not content.strip():
            return []

        chunks: list[DocumentChunk] = []
        # Split on ## headers (topic sections)
        sections = re.split(r"(?=^##\s)", content, flags=re.MULTILINE)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            heading_match = re.match(r"^##\s+(.+?)$", section, re.MULTILINE)
            heading_text = heading_match.group(1).strip() if heading_match else None

            tokens = _count_tokens(section)
            if tokens <= chunk_size:
                chunk = DocumentChunk()
                chunk.chunk_text = section
                chunk.chunk_type = ChunkType.SECTION
                chunk.heading_text = heading_text
                chunks.append(chunk)
            else:
                sub_chunks = _split_oversized_chunk(
                    section,
                    ChunkType.SECTION,
                    chunk_size,
                    chunk_overlap,
                    {"heading_text": heading_text},
                )
                chunks.extend(sub_chunks)

        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i

        return chunks


class MarkdownChunkingStrategy:
    """Default strategy for MarkItDownParser and general markdown content.

    Splits on heading boundaries (H1/H2/H3), tracks section path,
    keeps code blocks together, handles list structures.
    """

    @property
    def name(self) -> str:
        return "markdown"

    def chunk(
        self,
        content: str,
        metadata: dict,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> list[DocumentChunk]:
        if not content or not content.strip():
            return []

        chunks: list[DocumentChunk] = []
        # Split on H1/H2/H3 boundaries
        sections = re.split(r"(?=^#{1,3}\s)", content, flags=re.MULTILINE)

        section_path_parts: list[str] = []

        for section in sections:
            section = section.strip()
            if not section:
                continue

            heading_match = re.match(r"^(#{1,3})\s+(.+?)$", section, re.MULTILINE)
            heading_text = None
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                section_path_parts = section_path_parts[: level - 1]
                section_path_parts.append(f"{'#' * level} {heading_text}")

            section_path = " > ".join(section_path_parts) if section_path_parts else None

            # Detect code blocks and keep them together
            code_blocks = CODE_BLOCK_PATTERN.findall(section)
            non_code_text = CODE_BLOCK_PATTERN.sub("", section).strip()

            # Chunk non-code text
            if non_code_text:
                tokens = _count_tokens(non_code_text)
                if tokens <= chunk_size:
                    chunk = DocumentChunk()
                    chunk.chunk_text = non_code_text
                    chunk.chunk_type = ChunkType.PARAGRAPH
                    chunk.section_path = section_path
                    chunk.heading_text = heading_text
                    chunks.append(chunk)
                else:
                    sub_chunks = _split_oversized_chunk(
                        non_code_text,
                        ChunkType.PARAGRAPH,
                        chunk_size,
                        chunk_overlap,
                        {"section_path": section_path, "heading_text": heading_text},
                    )
                    chunks.extend(sub_chunks)

            # Code blocks as separate chunks
            for code in code_blocks:
                chunk = DocumentChunk()
                chunk.chunk_text = code.strip()
                chunk.chunk_type = ChunkType.CODE
                chunk.section_path = section_path
                chunk.heading_text = heading_text
                chunks.append(chunk)

        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i

        return chunks


class SectionChunkingStrategy:
    """For summaries and digests: splits on ## Section headers.

    Preserves section type as chunk metadata.
    """

    @property
    def name(self) -> str:
        return "section"

    def chunk(
        self,
        content: str,
        metadata: dict,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> list[DocumentChunk]:
        if not content or not content.strip():
            return []

        chunks: list[DocumentChunk] = []
        sections = re.split(r"(?=^##\s)", content, flags=re.MULTILINE)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            heading_match = re.match(r"^##\s+(.+?)$", section, re.MULTILINE)
            heading_text = heading_match.group(1).strip() if heading_match else None

            tokens = _count_tokens(section)
            if tokens <= chunk_size:
                chunk = DocumentChunk()
                chunk.chunk_text = section
                chunk.chunk_type = ChunkType.SECTION
                chunk.heading_text = heading_text
                chunks.append(chunk)
            else:
                sub_chunks = _split_oversized_chunk(
                    section,
                    ChunkType.SECTION,
                    chunk_size,
                    chunk_overlap,
                    {"heading_text": heading_text},
                )
                chunks.extend(sub_chunks)

        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i

        return chunks


# --- Strategy Registry and Factory ---

STRATEGY_REGISTRY: dict[str, type[ChunkingStrategy]] = {
    "structured": StructuredChunkingStrategy,
    "youtube_transcript": YouTubeTranscriptChunkingStrategy,
    "gemini_summary": GeminiSummaryChunkingStrategy,
    "markdown": MarkdownChunkingStrategy,
    "section": SectionChunkingStrategy,
}

PARSER_TO_STRATEGY: dict[str, str] = {
    "DoclingParser": "structured",
    "youtube_transcript_api": "youtube_transcript",
    "gemini": "gemini_summary",
    "MarkItDownParser": "markdown",
}


def get_chunking_strategy(
    parser_used: str | None = None,
    strategy_override: str | None = None,
) -> ChunkingStrategy:
    """Resolve chunking strategy from override or parser_used.

    Resolution order:
    1. Explicit strategy_override (from source config)
    2. PARSER_TO_STRATEGY mapping (auto-detect from parser_used)
    3. Default: MarkdownChunkingStrategy

    Args:
        parser_used: Content.parser_used value
        strategy_override: Explicit strategy name from source config

    Returns:
        ChunkingStrategy instance
    """
    if strategy_override:
        name = strategy_override
    else:
        name = PARSER_TO_STRATEGY.get(parser_used or "", "markdown")
        if parser_used and parser_used not in PARSER_TO_STRATEGY:
            logger.warning(
                f"Unknown parser '{parser_used}', falling back to markdown chunking strategy"
            )

    cls = STRATEGY_REGISTRY.get(name, MarkdownChunkingStrategy)
    return cls()


class ChunkingService:
    """Main chunking service that coordinates strategy selection and chunk generation.

    Resolves the appropriate strategy based on content type and source config,
    applies chunk size/overlap from source or global settings.
    """

    def chunk_content(
        self,
        content,  # Content ORM instance — avoid circular import
        source_config=None,  # SourceEntry | None
    ) -> list[DocumentChunk]:
        """Chunk a Content record into DocumentChunks.

        Args:
            content: Content ORM instance with markdown_content and parser_used
            source_config: Optional source configuration with chunking overrides

        Returns:
            List of DocumentChunk instances (not yet persisted).
            Returns empty list with warning for empty/NULL markdown_content.
        """
        if not content.markdown_content or not content.markdown_content.strip():
            logger.warning(f"Content {content.id} has empty markdown_content, skipping chunking")
            return []

        settings = get_settings()

        # Resolve strategy
        strategy_override = None
        if source_config and hasattr(source_config, "chunking_strategy"):
            strategy_override = source_config.chunking_strategy

        strategy = get_chunking_strategy(
            parser_used=content.parser_used,
            strategy_override=strategy_override,
        )

        # Resolve chunk size/overlap: source_config → global settings
        chunk_size = settings.chunk_size_tokens
        chunk_overlap = settings.chunk_overlap_tokens

        if source_config:
            if hasattr(source_config, "chunk_size_tokens") and source_config.chunk_size_tokens:
                chunk_size = source_config.chunk_size_tokens
            if (
                hasattr(source_config, "chunk_overlap_tokens")
                and source_config.chunk_overlap_tokens
            ):
                chunk_overlap = source_config.chunk_overlap_tokens

        metadata = {
            "content_id": content.id,
            "parser_used": content.parser_used,
            "source_type": str(content.source_type) if content.source_type else None,
        }

        # Run chunking
        chunks = strategy.chunk(
            content=content.markdown_content,
            metadata=metadata,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        # Set content_id on all chunks
        for chunk in chunks:
            chunk.content_id = content.id

        logger.info(
            f"Chunked content {content.id} with strategy '{strategy.name}': "
            f"{len(chunks)} chunks (size={chunk_size}, overlap={chunk_overlap})"
        )

        return chunks
