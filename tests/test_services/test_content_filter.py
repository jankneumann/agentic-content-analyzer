"""Tests for ContentRelevanceFilter shared utility.

Verifies keyword matching, LLM classification, combined strategies,
edge cases, and the factory function.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.services.content_filter import (
    ContentRelevanceFilter,
    create_content_filter,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ai_topics() -> list[str]:
    return ["AI", "machine learning", "LLM", "neural network", "leadership"]


@pytest.fixture
def keyword_filter(ai_topics):
    return ContentRelevanceFilter(strategy="keyword", topics=ai_topics)


@pytest.fixture
def llm_filter(ai_topics):
    return ContentRelevanceFilter(strategy="llm", topics=ai_topics)


@pytest.fixture
def combined_filter(ai_topics):
    return ContentRelevanceFilter(strategy="keyword+llm", topics=ai_topics)


# ---------------------------------------------------------------------------
# ContentRelevanceFilter.enabled
# ---------------------------------------------------------------------------


class TestEnabled:
    def test_enabled_with_strategy_and_topics(self, keyword_filter):
        assert keyword_filter.enabled is True

    def test_disabled_when_strategy_none(self):
        f = ContentRelevanceFilter(strategy="none", topics=["AI"])
        assert f.enabled is False

    def test_disabled_when_no_topics(self):
        f = ContentRelevanceFilter(strategy="keyword", topics=[])
        assert f.enabled is False

    def test_disabled_when_topics_none(self):
        f = ContentRelevanceFilter(strategy="keyword", topics=None)
        assert f.enabled is False


# ---------------------------------------------------------------------------
# Keyword Strategy
# ---------------------------------------------------------------------------


class TestKeywordStrategy:
    def test_matches_topic_in_title(self, keyword_filter):
        result = keyword_filter.is_relevant(title="New AI Model Released", content="")
        assert result.relevant is True
        assert result.strategy_used == "keyword"
        assert "AI" in result.matched_keywords

    def test_matches_topic_in_content(self, keyword_filter):
        result = keyword_filter.is_relevant(
            title="Tech Update",
            content="This article discusses machine learning trends.",
        )
        assert result.relevant is True
        assert "machine learning" in result.matched_keywords

    def test_matches_multi_word_topic(self, keyword_filter):
        result = keyword_filter.is_relevant(
            title="Neural Network Advances",
            content="New architectures for neural network training.",
        )
        assert result.relevant is True
        assert "neural network" in result.matched_keywords

    def test_no_match_returns_not_relevant(self, keyword_filter):
        result = keyword_filter.is_relevant(
            title="Cooking Recipes for Beginners",
            content="How to make pasta at home.",
        )
        assert result.relevant is False
        assert result.matched_keywords == []

    def test_case_insensitive_matching(self, keyword_filter):
        result = keyword_filter.is_relevant(title="The Future of ai", content="")
        assert result.relevant is True

    def test_word_boundary_prevents_partial_match(self):
        f = ContentRelevanceFilter(strategy="keyword", topics=["AI"])
        result = f.is_relevant(title="AISLE cleanup needed", content="")
        assert result.relevant is False

    def test_multiple_topics_matched(self, keyword_filter):
        result = keyword_filter.is_relevant(
            title="AI and Leadership in ML",
            content="Machine learning leadership skills.",
        )
        assert result.relevant is True
        assert len(result.matched_keywords) >= 2

    def test_empty_title_and_content(self, keyword_filter):
        result = keyword_filter.is_relevant(title="", content="")
        assert result.relevant is False

    def test_excerpt_truncation(self):
        f = ContentRelevanceFilter(strategy="keyword", topics=["secret"], excerpt_chars=10)
        # "secret" is beyond the 10-char excerpt, but title is not truncated
        result = f.is_relevant(title="Boring Title", content="x" * 20 + " secret topic")
        assert result.relevant is False


# ---------------------------------------------------------------------------
# LLM Strategy
# ---------------------------------------------------------------------------


class TestLLMStrategy:
    def _mock_llm_response(self, text: str):
        mock_response = MagicMock()
        mock_response.text = text
        mock_response.input_tokens = 50
        mock_response.output_tokens = 5
        return mock_response

    def _patch_llm_deps(self, llm_response_text: str | None = None, side_effect=None):
        """Return a context-manager stack that patches lazy imports in _call_llm."""
        mock_config = MagicMock()
        mock_config.get_model_for_step.return_value = "gemini-2.5-flash-lite"

        mock_prompt = MagicMock()
        mock_prompt.get_pipeline_prompt.return_value = "system prompt"
        mock_prompt.render.return_value = "user prompt"

        mock_router = MagicMock()
        if side_effect:
            mock_router.generate_sync.side_effect = side_effect
        else:
            mock_router.generate_sync.return_value = self._mock_llm_response(
                llm_response_text or '{"relevant": true}'
            )

        patches = {
            "get_model_config": patch(
                "src.config.models.get_model_config", return_value=mock_config
            ),
            "LLMRouter": patch("src.services.llm_router.LLMRouter", return_value=mock_router),
            "PromptService": patch(
                "src.services.prompt_service.PromptService", return_value=mock_prompt
            ),
        }
        return patches

    def test_llm_returns_relevant(self, llm_filter):
        patches = self._patch_llm_deps('{"relevant": true}')
        with patches["get_model_config"], patches["LLMRouter"], patches["PromptService"]:
            result = llm_filter.is_relevant(
                title="New LLM Paper", content="A paper about transformers."
            )
        assert result.relevant is True
        assert result.strategy_used == "llm"

    def test_llm_returns_not_relevant(self, llm_filter):
        patches = self._patch_llm_deps('{"relevant": false}')
        with patches["get_model_config"], patches["LLMRouter"], patches["PromptService"]:
            result = llm_filter.is_relevant(title="Cooking Show", content="How to make pasta.")
        assert result.relevant is False
        assert result.strategy_used == "llm"

    def test_llm_failure_defaults_to_relevant(self, llm_filter):
        patches = self._patch_llm_deps(side_effect=RuntimeError("API down"))
        with patches["get_model_config"], patches["LLMRouter"], patches["PromptService"]:
            result = llm_filter.is_relevant(title="Some Article", content="Content.")
        assert result.relevant is True
        assert result.strategy_used == "llm"

    def test_model_override(self, ai_topics):
        f = ContentRelevanceFilter(
            strategy="llm", topics=ai_topics, model_override="claude-haiku-4-5"
        )
        assert f.model_override == "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# Combined Strategy (keyword+llm)
# ---------------------------------------------------------------------------


class TestCombinedStrategy:
    def test_keyword_match_skips_llm(self, combined_filter):
        result = combined_filter.is_relevant(
            title="AI Research Paper",
            content="Deep learning advances.",
        )
        assert result.relevant is True
        assert result.strategy_used == "keyword"
        assert "AI" in result.matched_keywords

    def test_no_keyword_falls_through_to_llm(self, combined_filter):
        mock_config = MagicMock()
        mock_config.get_model_for_step.return_value = "gemini-2.5-flash-lite"

        mock_prompt = MagicMock()
        mock_prompt.get_pipeline_prompt.return_value = "system"
        mock_prompt.render.return_value = "user"

        mock_response = MagicMock()
        mock_response.text = '{"relevant": true}'
        mock_response.input_tokens = 50
        mock_response.output_tokens = 5
        mock_router = MagicMock()
        mock_router.generate_sync.return_value = mock_response

        with (
            patch("src.config.models.get_model_config", return_value=mock_config),
            patch("src.services.llm_router.LLMRouter", return_value=mock_router),
            patch("src.services.prompt_service.PromptService", return_value=mock_prompt),
        ):
            result = combined_filter.is_relevant(
                title="Transformer Architecture",
                content="Attention mechanisms in sequence models.",
            )
        assert result.relevant is True
        assert result.strategy_used == "llm"


# ---------------------------------------------------------------------------
# Strategy: none
# ---------------------------------------------------------------------------


class TestNoneStrategy:
    def test_none_strategy_passes_everything(self):
        f = ContentRelevanceFilter(strategy="none", topics=["AI"])
        result = f.is_relevant(title="Anything", content="Whatever")
        assert result.relevant is True
        assert result.strategy_used == "none"

    def test_unknown_strategy_passes_through(self):
        f = ContentRelevanceFilter(strategy="unknown", topics=["AI"])
        result = f.is_relevant(title="Anything", content="Whatever")
        assert result.relevant is True
        assert result.strategy_used == "none"


# ---------------------------------------------------------------------------
# filter_contents()
# ---------------------------------------------------------------------------


class TestFilterContents:
    def test_filters_list_of_content_objects(self, keyword_filter):
        items = [
            MagicMock(title="AI Breakthrough", markdown_content="New model released."),
            MagicMock(title="Cooking Tips", markdown_content="Best pasta recipes."),
            MagicMock(title="ML Pipeline Design", markdown_content="Machine learning ops."),
        ]
        result = keyword_filter.filter_contents(items)
        assert len(result) == 2
        assert result[0].title == "AI Breakthrough"
        assert result[1].title == "ML Pipeline Design"

    def test_returns_all_when_disabled(self):
        f = ContentRelevanceFilter(strategy="none")
        items = [MagicMock(), MagicMock()]
        result = f.filter_contents(items)
        assert len(result) == 2

    def test_empty_list(self, keyword_filter):
        result = keyword_filter.filter_contents([])
        assert result == []


# ---------------------------------------------------------------------------
# _parse_llm_response()
# ---------------------------------------------------------------------------


class TestParseLLMResponse:
    def test_parses_json_true(self):
        assert ContentRelevanceFilter._parse_llm_response('{"relevant": true}') is True

    def test_parses_json_false(self):
        assert ContentRelevanceFilter._parse_llm_response('{"relevant": false}') is False

    def test_strips_markdown_code_block(self):
        text = '```json\n{"relevant": false}\n```'
        assert ContentRelevanceFilter._parse_llm_response(text) is False

    def test_strips_code_block_without_language(self):
        text = '```\n{"relevant": true}\n```'
        assert ContentRelevanceFilter._parse_llm_response(text) is True

    def test_handles_whitespace(self):
        assert ContentRelevanceFilter._parse_llm_response('  {"relevant": true}  ') is True

    def test_invalid_json_defaults_to_true(self):
        assert ContentRelevanceFilter._parse_llm_response("not json") is True

    def test_missing_relevant_key_defaults_to_true(self):
        assert ContentRelevanceFilter._parse_llm_response('{"answer": "yes"}') is True


# ---------------------------------------------------------------------------
# create_content_filter() factory
# ---------------------------------------------------------------------------


class TestCreateContentFilter:
    def _mock_source(self, **overrides):
        """Create a mock source object with content_filter_* attributes."""
        defaults = {
            "content_filter_strategy": "keyword",
            "content_filter_topics": ["AI", "ML"],
            "content_filter_excerpt_chars": 500,
        }
        defaults.update(overrides)
        return MagicMock(**defaults)

    def test_reads_from_source_object(self):
        source = self._mock_source()
        f = create_content_filter(source)
        assert f.strategy == "keyword"
        assert f.topics == ["AI", "ML"]
        assert f.excerpt_chars == 500

    def test_explicit_args_override_source(self):
        source = self._mock_source()
        f = create_content_filter(
            source,
            strategy="llm",
            topics=["leadership", "management"],
        )
        assert f.strategy == "llm"
        assert f.topics == ["leadership", "management"]
        assert f.excerpt_chars == 500  # Falls through from source

    def test_no_source_uses_hardcoded_defaults(self):
        f = create_content_filter()
        assert f.strategy == "none"
        assert f.topics == []
        assert f.excerpt_chars == 1000

    def test_source_with_none_fields_uses_defaults(self):
        source = self._mock_source(
            content_filter_strategy=None,
            content_filter_topics=None,
            content_filter_excerpt_chars=None,
        )
        f = create_content_filter(source)
        assert f.strategy == "none"
        assert f.topics == []
        assert f.excerpt_chars == 1000

    def test_explicit_excerpt_chars(self):
        source = self._mock_source()
        f = create_content_filter(source, excerpt_chars=2000)
        assert f.excerpt_chars == 2000
