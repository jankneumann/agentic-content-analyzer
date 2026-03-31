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
    TreeIndexChunkingStrategy,
    YouTubeTranscriptChunkingStrategy,
    _count_tokens,
    _detect_heading_depth,
    _split_into_sentences,
    _thin_chunks,
    get_chunking_strategy,
)
from src.models.chunk import ChunkType, DocumentChunk

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
        assert "tree_index" in STRATEGY_REGISTRY

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
        self._patcher = patch(
            "src.services.chunking.get_settings",
            return_value=MagicMock(min_node_tokens=0),
        )
        self._patcher.start()

    def teardown_method(self):
        self._patcher.stop()

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


def _default_mock_settings(**overrides):
    """Create a MagicMock settings with all required chunking fields."""
    defaults = dict(
        chunk_size_tokens=512,
        chunk_overlap_tokens=64,
        min_node_tokens=0,
        tree_index_min_tokens=999999,
        tree_index_min_heading_depth=99,
        tree_max_depth=10,
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


class TestChunkingService:
    @patch("src.services.chunking.get_settings")
    def test_resolves_defaults(self, mock_settings):
        mock_settings.return_value = _default_mock_settings()
        service = ChunkingService()

        mock_content = MagicMock()
        mock_content.markdown_content = "# Test\n\nSome content here."
        mock_content.parser_used = None

        chunks = service.chunk_content(mock_content)
        assert len(chunks) >= 1

    @patch("src.services.chunking.get_settings")
    def test_empty_content_returns_empty(self, mock_settings):
        mock_settings.return_value = _default_mock_settings()
        service = ChunkingService()

        mock_content = MagicMock()
        mock_content.markdown_content = ""
        mock_content.parser_used = None

        chunks = service.chunk_content(mock_content)
        assert chunks == []

    @patch("src.services.chunking.get_settings")
    def test_none_content_returns_empty(self, mock_settings):
        mock_settings.return_value = _default_mock_settings()
        service = ChunkingService()

        mock_content = MagicMock()
        mock_content.markdown_content = None
        mock_content.parser_used = None

        chunks = service.chunk_content(mock_content)
        assert chunks == []

    @patch("src.services.chunking.get_settings")
    def test_source_config_override(self, mock_settings):
        mock_settings.return_value = _default_mock_settings()
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


# --- Chunk thinning tests ---


def _make_chunk(text: str, chunk_type: str = ChunkType.PARAGRAPH) -> DocumentChunk:
    """Helper to create a DocumentChunk for testing."""
    c = DocumentChunk()
    c.chunk_text = text
    c.chunk_type = chunk_type
    c.section_path = None
    c.heading_text = None
    return c


class TestThinChunks:
    def test_small_chunk_merged_into_preceding(self):
        chunks = [
            _make_chunk("A " * 30),  # ~30 tokens
            _make_chunk("B"),  # 1 token - should merge
        ]
        result = _thin_chunks(chunks, min_tokens=10)
        assert len(result) == 1
        assert "B" in result[0].chunk_text

    def test_small_first_chunk_merged_forward(self):
        chunks = [
            _make_chunk("X"),  # 1 token - undersized, no predecessor
            _make_chunk("Y " * 30),  # ~30 tokens
        ]
        result = _thin_chunks(chunks, min_tokens=10)
        assert len(result) == 1
        assert "X" in result[0].chunk_text
        assert "Y" in result[0].chunk_text

    def test_disabled_when_min_tokens_zero(self):
        chunks = [_make_chunk("A"), _make_chunk("B"), _make_chunk("C")]
        result = _thin_chunks(chunks, min_tokens=0)
        assert len(result) == 3

    def test_single_chunk_below_threshold_preserved(self):
        chunks = [_make_chunk("tiny")]
        result = _thin_chunks(chunks, min_tokens=100)
        assert len(result) == 1
        assert result[0].chunk_text == "tiny"

    def test_chunk_at_threshold_not_merged(self):
        text = "word " * 10  # Exactly at threshold
        token_count = _count_tokens(text)
        chunks = [_make_chunk(text), _make_chunk("after " * 20)]
        result = _thin_chunks(chunks, min_tokens=token_count)
        assert len(result) == 2

    def test_multiple_consecutive_small_chunks_merged(self):
        chunks = [
            _make_chunk("A " * 20),  # big enough
            _make_chunk("B"),  # small
            _make_chunk("C"),  # small
        ]
        result = _thin_chunks(chunks, min_tokens=10)
        assert len(result) == 1
        assert "A" in result[0].chunk_text
        assert "B" in result[0].chunk_text
        assert "C" in result[0].chunk_text

    def test_table_chunk_exempt_from_merging(self):
        chunks = [
            _make_chunk("small", ChunkType.TABLE),
            _make_chunk("big " * 20),
        ]
        result = _thin_chunks(chunks, min_tokens=10)
        assert len(result) == 2
        assert result[0].chunk_type == ChunkType.TABLE

    def test_code_chunk_exempt_from_merging(self):
        chunks = [
            _make_chunk("x = 1", ChunkType.CODE),
            _make_chunk("paragraph " * 20),
        ]
        result = _thin_chunks(chunks, min_tokens=10)
        assert len(result) == 2
        assert result[0].chunk_type == ChunkType.CODE

    def test_small_chunk_not_merged_into_table_predecessor(self):
        chunks = [
            _make_chunk("| col |", ChunkType.TABLE),
            _make_chunk("tiny"),
        ]
        result = _thin_chunks(chunks, min_tokens=10)
        # tiny can't merge into TABLE, stays separate
        assert len(result) == 2


# --- Heading depth detection tests ---


class TestDetectHeadingDepth:
    def test_three_levels(self):
        content = "# H1\n## H2\n### H3\n"
        assert _detect_heading_depth(content) == 3

    def test_single_level(self):
        content = "## Only H2\n## Another H2\n"
        assert _detect_heading_depth(content) == 1

    def test_no_headings(self):
        content = "Just plain text without any headings."
        assert _detect_heading_depth(content) == 0

    def test_six_levels(self):
        content = "# 1\n## 2\n### 3\n#### 4\n##### 5\n###### 6\n"
        assert _detect_heading_depth(content) == 6


# --- TreeIndexChunkingStrategy tests ---


class TestTreeIndexChunkingStrategy:
    def setup_method(self):
        self.strategy = TreeIndexChunkingStrategy()

    @patch("src.services.chunking.get_settings")
    def test_builds_correct_hierarchy(self, mock_settings):
        mock_settings.return_value = MagicMock(tree_max_depth=10)
        content = "# Title\n## Section A\nContent A\n### Sub A.1\nDetail\n## Section B\nContent B"
        chunks = self.strategy.chunk(content, {})

        # Should have: root (Title), internal (Section A), leaf (Sub A.1), leaf (Section B)
        assert len(chunks) >= 3
        roots = [c for c in chunks if c.tree_depth == 0]
        assert len(roots) == 1
        assert roots[0].is_summary is True

    @patch("src.services.chunking.get_settings")
    def test_internal_nodes_are_summaries(self, mock_settings):
        mock_settings.return_value = MagicMock(tree_max_depth=10)
        content = "# Root\n## Child\nLeaf content"
        chunks = self.strategy.chunk(content, {})

        internal = [c for c in chunks if c.is_summary]
        leaves = [c for c in chunks if not c.is_summary]
        for node in internal:
            assert node.chunk_type == ChunkType.SECTION
            assert node.chunk_text == ""  # Placeholder

        for leaf in leaves:
            assert leaf.is_summary is False
            assert leaf.chunk_text != ""

    @patch("src.services.chunking.get_settings")
    def test_tree_depth_correct(self, mock_settings):
        mock_settings.return_value = MagicMock(tree_max_depth=10)
        content = "# H1\n## H2\n### H3\nDeep content"
        chunks = self.strategy.chunk(content, {})

        depths = sorted(set(c.tree_depth for c in chunks))
        assert 0 in depths  # root
        assert max(depths) >= 2  # at least 3 levels

    @patch("src.services.chunking.get_settings")
    def test_flat_chunks_have_null_tree_depth(self, mock_settings):
        """TreeIndexChunkingStrategy returns tree-only chunks (all have tree_depth set)."""
        mock_settings.return_value = MagicMock(tree_max_depth=10)
        content = "# Title\n## Section\nContent"
        chunks = self.strategy.chunk(content, {})

        # All chunks from tree strategy should have tree_depth set (not None)
        for chunk in chunks:
            assert chunk.tree_depth is not None

    @patch("src.services.chunking.get_settings")
    def test_tree_max_depth_enforced(self, mock_settings):
        mock_settings.return_value = MagicMock(tree_max_depth=2)
        content = "# L1\n## L2\n### L3\n#### L4\nDeep content"
        chunks = self.strategy.chunk(content, {})

        max_depth = max(c.tree_depth for c in chunks)
        assert max_depth <= 3  # depth 0, 1, 2, and possibly leaves at 3

    @patch("src.services.chunking.get_settings")
    def test_empty_content_returns_empty(self, mock_settings):
        mock_settings.return_value = MagicMock(tree_max_depth=10)
        assert self.strategy.chunk("", {}) == []
        assert self.strategy.chunk("   ", {}) == []

    @patch("src.services.chunking.get_settings")
    def test_chunk_indexes_sequential(self, mock_settings):
        mock_settings.return_value = MagicMock(tree_max_depth=10)
        content = "# A\n## B\nContent B\n## C\nContent C"
        chunks = self.strategy.chunk(content, {})
        indexes = [c.chunk_index for c in chunks]
        assert indexes == list(range(len(chunks)))

    def test_strategy_name(self):
        assert self.strategy.name == "tree_index"


# --- ChunkingService tree orchestration tests ---


class TestChunkingServiceTreeOrchestration:
    @patch("src.services.chunking.get_settings")
    def test_auto_selects_tree_for_qualifying_content(self, mock_settings):
        mock_settings.return_value = MagicMock(
            chunk_size_tokens=512,
            chunk_overlap_tokens=64,
            min_node_tokens=0,
            tree_index_min_tokens=100,  # Low threshold for testing
            tree_index_min_heading_depth=2,
            tree_max_depth=10,
        )
        service = ChunkingService()

        # Content with enough tokens and heading depth
        long_content = "# Title\n\n" + ("word " * 50 + "\n\n") + "## Section\n\n" + ("text " * 50 + "\n\n") + "### Subsection\n\n" + ("detail " * 50)
        mock_content = MagicMock()
        mock_content.markdown_content = long_content
        mock_content.parser_used = None
        mock_content.id = 1
        mock_content.source_type = None

        chunks = service.chunk_content(mock_content)

        flat_chunks = [c for c in chunks if c.tree_depth is None]
        tree_chunks = [c for c in chunks if c.tree_depth is not None]

        assert len(flat_chunks) > 0, "Should have flat chunks"
        assert len(tree_chunks) > 0, "Should have tree chunks"

    @patch("src.services.chunking.get_settings")
    def test_skips_tree_for_short_content(self, mock_settings):
        mock_settings.return_value = MagicMock(
            chunk_size_tokens=512,
            chunk_overlap_tokens=64,
            min_node_tokens=0,
            tree_index_min_tokens=8000,
            tree_index_min_heading_depth=3,
            tree_max_depth=10,
        )
        service = ChunkingService()

        mock_content = MagicMock()
        mock_content.markdown_content = "# Short\n\nJust a few words."
        mock_content.parser_used = None
        mock_content.id = 1
        mock_content.source_type = None

        chunks = service.chunk_content(mock_content)

        tree_chunks = [c for c in chunks if c.tree_depth is not None]
        assert len(tree_chunks) == 0, "Short content should not get tree index"

    @patch("src.services.chunking.get_settings")
    def test_explicit_tree_index_override(self, mock_settings):
        mock_settings.return_value = MagicMock(
            chunk_size_tokens=512,
            chunk_overlap_tokens=64,
            min_node_tokens=0,
            tree_index_min_tokens=999999,  # Very high - wouldn't auto-select
            tree_index_min_heading_depth=99,
            tree_max_depth=10,
        )
        service = ChunkingService()

        mock_content = MagicMock()
        mock_content.markdown_content = "# Title\n## Section\nContent here."
        mock_content.parser_used = None
        mock_content.id = 1
        mock_content.source_type = None

        mock_source = MagicMock()
        mock_source.chunking_strategy = "tree_index"
        mock_source.chunk_size_tokens = None
        mock_source.chunk_overlap_tokens = None

        chunks = service.chunk_content(mock_content, source_config=mock_source)

        tree_chunks = [c for c in chunks if c.tree_depth is not None]
        assert len(tree_chunks) > 0, "tree_index override should force tree indexing"

    @patch("src.services.chunking.get_settings")
    def test_no_duplicate_flat_chunks(self, mock_settings):
        mock_settings.return_value = MagicMock(
            chunk_size_tokens=512,
            chunk_overlap_tokens=64,
            min_node_tokens=0,
            tree_index_min_tokens=10,
            tree_index_min_heading_depth=2,
            tree_max_depth=10,
        )
        service = ChunkingService()

        mock_content = MagicMock()
        mock_content.markdown_content = "# H1\n\nParagraph.\n\n## H2\n\nMore text.\n\n### H3\n\nDeep."
        mock_content.parser_used = None
        mock_content.id = 1
        mock_content.source_type = None

        chunks = service.chunk_content(mock_content)

        flat_chunks = [c for c in chunks if c.tree_depth is None]
        flat_texts = [c.chunk_text for c in flat_chunks]

        # No duplicates in flat chunks
        assert len(flat_texts) == len(set(flat_texts)), "Flat chunks should not be duplicated"
