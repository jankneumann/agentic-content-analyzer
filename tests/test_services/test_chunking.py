"""Tests for chunking strategies and ChunkingService."""

from unittest.mock import MagicMock, patch

from src.services.chunking import (
    PARSER_TO_STRATEGY,
    STRATEGY_REGISTRY,
    ChunkingService,
    GeminiSummaryChunkingStrategy,
    MarkdownChunkingStrategy,
    SectionChunkingStrategy,
    StructuredChunkingStrategy,
    YouTubeTranscriptChunkingStrategy,
    _count_tokens,
    _split_into_sentences,
    get_chunking_strategy,
)

# --- Helper function tests ---


class TestCountTokens:
    def test_counts_tokens(self):
        count = _count_tokens("Hello world, this is a test sentence.")
        assert count > 0
        assert count < 20  # Should be ~8 tokens

    def test_empty_string(self):
        assert _count_tokens("") == 0


class TestSplitIntoSentences:
    def test_basic_split(self):
        text = "First sentence. Second sentence. Third sentence."
        sentences = _split_into_sentences(text)
        assert len(sentences) == 3
        assert sentences[0].strip() == "First sentence."

    def test_single_sentence(self):
        sentences = _split_into_sentences("Just one sentence.")
        assert len(sentences) == 1

    def test_empty_string(self):
        sentences = _split_into_sentences("")
        assert sentences == [] or sentences == [""]


# --- Strategy registry tests ---


class TestStrategyRegistry:
    def test_all_strategies_registered(self):
        assert "structured" in STRATEGY_REGISTRY
        assert "youtube_transcript" in STRATEGY_REGISTRY
        assert "gemini_summary" in STRATEGY_REGISTRY
        assert "markdown" in STRATEGY_REGISTRY
        assert "section" in STRATEGY_REGISTRY

    def test_parser_mapping(self):
        assert PARSER_TO_STRATEGY["DoclingParser"] == "structured"
        assert PARSER_TO_STRATEGY["youtube_transcript_api"] == "youtube_transcript"
        assert PARSER_TO_STRATEGY["gemini"] == "gemini_summary"
        assert PARSER_TO_STRATEGY["MarkItDownParser"] == "markdown"


class TestGetChunkingStrategy:
    def test_explicit_override(self):
        strategy = get_chunking_strategy(strategy_override="structured")
        assert isinstance(strategy, StructuredChunkingStrategy)

    def test_parser_mapping(self):
        strategy = get_chunking_strategy(parser_used="gemini")
        assert isinstance(strategy, GeminiSummaryChunkingStrategy)

    def test_default_markdown(self):
        strategy = get_chunking_strategy()
        assert isinstance(strategy, MarkdownChunkingStrategy)

    def test_unknown_parser_uses_default(self):
        strategy = get_chunking_strategy(parser_used="unknown_parser")
        assert isinstance(strategy, MarkdownChunkingStrategy)

    def test_override_beats_parser(self):
        strategy = get_chunking_strategy(
            parser_used="gemini",
            strategy_override="section",
        )
        assert isinstance(strategy, SectionChunkingStrategy)


# --- MarkdownChunkingStrategy tests ---


class TestMarkdownChunkingStrategy:
    def setup_method(self):
        self.strategy = MarkdownChunkingStrategy()

    def test_basic_chunking(self):
        content = "# Heading 1\n\nSome paragraph text here.\n\n# Heading 2\n\nMore text."
        chunks = self.strategy.chunk(content, {}, chunk_size=512, chunk_overlap=0)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.chunk_text.strip()

    def test_empty_content(self):
        chunks = self.strategy.chunk("", {}, chunk_size=512, chunk_overlap=0)
        assert chunks == []

    def test_whitespace_only(self):
        chunks = self.strategy.chunk("   \n\n  ", {}, chunk_size=512, chunk_overlap=0)
        assert chunks == []

    def test_code_block_preserved(self):
        content = "# Code\n\n```python\ndef hello():\n    print('world')\n```\n\nText after."
        chunks = self.strategy.chunk(content, {}, chunk_size=512, chunk_overlap=0)
        # Code block should be in one chunk (not split mid-block)
        code_chunks = [c for c in chunks if "def hello" in c.chunk_text]
        assert len(code_chunks) == 1
        assert "print('world')" in code_chunks[0].chunk_text

    def test_chunk_indexes_sequential(self):
        content = "# A\n\nText A.\n\n# B\n\nText B.\n\n# C\n\nText C."
        chunks = self.strategy.chunk(content, {}, chunk_size=512, chunk_overlap=0)
        indexes = [c.chunk_index for c in chunks]
        assert indexes == list(range(len(chunks)))

    def test_section_path_tracking(self):
        content = "# Main\n\nIntro.\n\n## Sub\n\nSub content."
        chunks = self.strategy.chunk(content, {}, chunk_size=512, chunk_overlap=0)
        # At least one chunk should have a section_path
        paths = [c.section_path for c in chunks if c.section_path]
        assert len(paths) > 0


# --- YouTubeTranscriptChunkingStrategy tests ---


class TestYouTubeTranscriptStrategy:
    def setup_method(self):
        self.strategy = YouTubeTranscriptChunkingStrategy()

    def test_timestamp_parsing(self):
        content = "[00:00](https://youtube.com/watch?v=abc&t=0) Hello world.\n\n[00:30](https://youtube.com/watch?v=abc&t=30) More speech here."
        chunks = self.strategy.chunk(content, {}, chunk_size=512, chunk_overlap=0)
        assert len(chunks) >= 1
        # Should have deep_link URLs
        links = [c.deep_link_url for c in chunks if c.deep_link_url]
        assert len(links) > 0

    def test_chunk_type_is_transcript(self):
        content = "Some transcript text without timestamps."
        chunks = self.strategy.chunk(content, {}, chunk_size=512, chunk_overlap=0)
        for chunk in chunks:
            assert chunk.chunk_type == "transcript"


# --- GeminiSummaryChunkingStrategy tests ---


class TestGeminiSummaryStrategy:
    def setup_method(self):
        self.strategy = GeminiSummaryChunkingStrategy()

    def test_splits_on_topic_sections(self):
        content = "## Topic 1: AI Safety\n\nContent about safety.\n\n## Topic 2: LLMs\n\nContent about LLMs."
        chunks = self.strategy.chunk(content, {}, chunk_size=512, chunk_overlap=0)
        assert len(chunks) >= 2
        headings = [c.heading_text for c in chunks if c.heading_text]
        assert len(headings) >= 2

    def test_no_timestamp_metadata(self):
        content = "## Summary\n\nThis is a Gemini summary."
        chunks = self.strategy.chunk(content, {}, chunk_size=512, chunk_overlap=0)
        for chunk in chunks:
            assert chunk.timestamp_start is None
            assert chunk.timestamp_end is None


# --- ChunkingService tests ---


class TestChunkingService:
    @patch("src.services.chunking.get_settings")
    def test_resolves_defaults(self, mock_settings):
        mock_settings.return_value = MagicMock(
            chunk_size_tokens=512,
            chunk_overlap_tokens=64,
        )
        service = ChunkingService()

        mock_content = MagicMock()
        mock_content.markdown_content = "# Test\n\nSome content here."
        mock_content.parser_used = None

        chunks = service.chunk_content(mock_content)
        assert len(chunks) >= 1

    @patch("src.services.chunking.get_settings")
    def test_empty_content_returns_empty(self, mock_settings):
        mock_settings.return_value = MagicMock(
            chunk_size_tokens=512,
            chunk_overlap_tokens=64,
        )
        service = ChunkingService()

        mock_content = MagicMock()
        mock_content.markdown_content = ""
        mock_content.parser_used = None

        chunks = service.chunk_content(mock_content)
        assert chunks == []

    @patch("src.services.chunking.get_settings")
    def test_none_content_returns_empty(self, mock_settings):
        mock_settings.return_value = MagicMock(
            chunk_size_tokens=512,
            chunk_overlap_tokens=64,
        )
        service = ChunkingService()

        mock_content = MagicMock()
        mock_content.markdown_content = None
        mock_content.parser_used = None

        chunks = service.chunk_content(mock_content)
        assert chunks == []

    @patch("src.services.chunking.get_settings")
    def test_source_config_override(self, mock_settings):
        mock_settings.return_value = MagicMock(
            chunk_size_tokens=512,
            chunk_overlap_tokens=64,
        )
        service = ChunkingService()

        mock_content = MagicMock()
        mock_content.markdown_content = "# Test\n\nContent."
        mock_content.parser_used = None

        mock_source = MagicMock()
        mock_source.chunk_size_tokens = 256
        mock_source.chunk_overlap_tokens = 32
        mock_source.chunking_strategy = "markdown"

        chunks = service.chunk_content(mock_content, source_config=mock_source)
        assert len(chunks) >= 1
