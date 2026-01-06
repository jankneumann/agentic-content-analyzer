"""Tests for token counting utility."""

from src.config.models import ModelConfig, Provider
from src.utils.token_counter import TokenCounter


class TestTokenCounter:
    """Test suite for TokenCounter class."""

    def test_initialization(self):
        """Test TokenCounter initializes correctly."""
        counter = TokenCounter()
        assert counter.encoding is not None
        assert counter.model_config is not None

    def test_estimate_text_tokens_simple(self):
        """Test basic token estimation."""
        counter = TokenCounter()

        # Simple text
        text = "Hello, world!"
        tokens = counter.estimate_text_tokens(text)
        assert tokens > 0
        assert tokens < 100  # Should be a small number

    def test_estimate_text_tokens_empty(self):
        """Test token estimation with empty text."""
        counter = TokenCounter()
        tokens = counter.estimate_text_tokens("")
        assert tokens == 0

    def test_estimate_text_tokens_long(self):
        """Test token estimation with long text."""
        counter = TokenCounter()

        # Long text (approximately 1000 characters)
        text = "AI " * 500
        tokens = counter.estimate_text_tokens(text)
        assert tokens > 0
        assert tokens < 1500  # Should be reasonable for this length

    def test_estimate_newsletter_batch_tokens(self):
        """Test newsletter batch token estimation."""
        counter = TokenCounter()

        newsletters = [
            {"title": "AI Weekly", "publication": "TechCrunch"},
            {"title": "ML Advances", "publication": "ArXiv"},
            {"title": "LLM Updates", "publication": "OpenAI"},
        ]

        tokens = counter.estimate_newsletter_batch_tokens(newsletters)
        assert tokens > 0
        assert tokens < 500  # Should be small for just titles

    def test_estimate_newsletter_batch_tokens_empty(self):
        """Test newsletter batch estimation with empty list."""
        counter = TokenCounter()
        tokens = counter.estimate_newsletter_batch_tokens([])
        assert tokens == 0

    def test_calculate_token_budget_claude(self):
        """Test token budget calculation for Claude models."""
        config = ModelConfig()
        counter = TokenCounter(model_config=config, model_id="claude-sonnet-4-5")

        budget = counter.calculate_token_budget(
            model_id="claude-sonnet-4-5",
            provider=Provider.ANTHROPIC,
            context_window_percentage=0.5,
        )

        # Claude Sonnet 4.5 has 200K context window
        assert budget["total_context"] == 200000
        assert budget["available_for_input"] == 100000  # 50%
        assert budget["newsletter_budget"] == 60000  # 60% of input
        assert budget["theme_budget"] == 30000  # 30% of input
        assert budget["prompt_overhead"] == 10000  # 10% of input
        assert budget["max_output_tokens"] == 64000  # Updated to match model_registry.yaml

    def test_calculate_token_budget_custom_percentage(self):
        """Test token budget calculation with custom percentage."""
        config = ModelConfig()
        counter = TokenCounter(model_config=config, model_id="claude-haiku-4-5")

        budget = counter.calculate_token_budget(
            model_id="claude-haiku-4-5",
            provider=Provider.ANTHROPIC,
            context_window_percentage=0.7,  # 70%
        )

        assert budget["total_context"] == 200000
        assert budget["available_for_input"] == 140000  # 70%
        assert budget["newsletter_budget"] == 84000  # 60% of 140000
        assert budget["theme_budget"] == 42000  # 30% of 140000
        assert budget["prompt_overhead"] == 14000  # 10% of 140000

    def test_calculate_newsletters_that_fit(self):
        """Test calculating newsletter count that fits budget."""
        counter = TokenCounter()

        newsletters = [
            {"title": "Short", "publication": "A"},
            {"title": "Medium length title", "publication": "B"},
            {"title": "Very long title with many words", "publication": "C"},
            {"title": "Another one", "publication": "D"},
        ]

        # Small budget - should fit only 1-2 newsletters
        count = counter.calculate_newsletters_that_fit(newsletters, token_budget=50)
        assert count >= 1
        assert count <= len(newsletters)

        # Large budget - should fit all newsletters
        count = counter.calculate_newsletters_that_fit(newsletters, token_budget=10000)
        assert count == len(newsletters)

    def test_calculate_newsletters_that_fit_zero_budget(self):
        """Test newsletter calculation with zero budget."""
        counter = TokenCounter()

        newsletters = [
            {"title": "Test", "publication": "A"},
        ]

        count = counter.calculate_newsletters_that_fit(newsletters, token_budget=0)
        assert count == 0

    def test_token_estimation_consistency(self):
        """Test that token estimation is consistent for same input."""
        counter = TokenCounter()

        text = "This is a test of token estimation consistency."
        tokens1 = counter.estimate_text_tokens(text)
        tokens2 = counter.estimate_text_tokens(text)

        assert tokens1 == tokens2

    def test_estimate_with_summaries(self):
        """Test newsletter batch estimation with summary objects."""
        counter = TokenCounter()

        newsletters = [
            {"title": "AI Weekly", "publication": "TechCrunch"},
        ]

        # Mock summary object
        class MockSummary:
            def __init__(self):
                self.executive_summary = "This is a comprehensive summary of AI developments."
                self.key_themes = ["AI", "Machine Learning", "LLMs"]
                self.strategic_insights = ["Insight 1", "Insight 2", "Insight 3"]
                self.tactical_insights = ["Tactic 1", "Tactic 2"]

        summaries = [MockSummary()]

        # Estimate with summaries should be much higher than without
        tokens_with_summaries = counter.estimate_newsletter_batch_tokens(
            newsletters, summaries=summaries
        )
        tokens_without_summaries = counter.estimate_newsletter_batch_tokens(
            newsletters, summaries=None
        )

        assert tokens_with_summaries > tokens_without_summaries
        # With summaries should be at least 3x more (summary content is substantial)
        assert tokens_with_summaries > tokens_without_summaries * 3

    def test_model_id_defaults_correctly(self):
        """Test that model_id defaults to DIGEST_CREATION step if not provided."""
        counter = TokenCounter()

        # Should default to digest creation model
        assert counter.model_id is not None
        # Should be one of the configured models
        assert "claude" in counter.model_id.lower() or "gemini" in counter.model_id.lower()
