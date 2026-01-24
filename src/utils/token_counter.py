"""Token counting utility for context window management."""

import tiktoken

from src.config.models import ModelConfig, Provider
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TokenCounter:
    """
    Utility for estimating token counts before API calls.

    Uses tiktoken (OpenAI's tokenizer) for pre-call estimation.
    Accurate for GPT models, approximate (within 10-15%) for Claude/Gemini.
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        model_id: str | None = None,
    ):
        """
        Initialize token counter.

        Args:
            model_config: Model configuration (defaults to global config)
            model_id: Model ID for context window lookup (defaults to DIGEST_CREATION model)
        """
        from src.config import settings
        from src.config.models import ModelStep

        self.model_config = model_config or settings.get_model_config()
        # Use provided model_id or get default from config
        self.model_id = model_id or self.model_config.get_model_for_step(ModelStep.DIGEST_CREATION)

        # Use cl100k_base encoding (GPT-4, GPT-3.5-turbo compatible)
        # Approximate for Claude/Gemini but within acceptable range
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.error(f"Failed to load tiktoken encoding: {e}")
            raise RuntimeError(f"TokenCounter initialization failed: {e}")

        logger.debug(f"Initialized TokenCounter with model: {model_id}")

    def estimate_text_tokens(self, text: str) -> int:
        """
        Estimate number of tokens in text.

        Uses tiktoken cl100k_base encoding.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        try:
            tokens = self.encoding.encode(text)
            return len(tokens)
        except Exception as e:
            logger.warning(f"Token estimation failed: {e}. Using character-based fallback.")
            # Fallback: rough approximation (1 token ≈ 4 characters)
            return len(text) // 4

    def estimate_newsletter_batch_tokens(
        self,
        newsletters: list[dict],
        themes: list | None = None,
        prompt_template: str | None = None,
        summaries: list | None = None,
    ) -> int:
        """
        Estimate total tokens for newsletter batch including all context.

        Args:
            newsletters: List of newsletter dicts (with title, publication)
            themes: Optional list of theme objects
            prompt_template: Optional prompt template string
            summaries: Optional list of newsletter summary objects (Summary)

        Returns:
            Total estimated tokens for full context
        """
        total_tokens = 0

        # 1. Newsletter summary tokens (if provided - this is the main content)
        if summaries:
            summary_tokens = 0
            for summary in summaries:
                # Estimate based on summary content
                summary_text = ""
                if hasattr(summary, "executive_summary"):
                    summary_text += summary.executive_summary
                if hasattr(summary, "key_themes"):
                    summary_text += " " + " ".join(summary.key_themes)
                if hasattr(summary, "strategic_insights"):
                    summary_text += " " + " ".join(summary.strategic_insights)
                if hasattr(summary, "tactical_insights"):
                    summary_text += " " + " ".join(summary.tactical_insights)

                summary_tokens += self.estimate_text_tokens(summary_text)

            total_tokens += summary_tokens
            logger.debug(f"Summary tokens: {summary_tokens} for {len(summaries)} summaries")
        else:
            # Fallback: estimate based on newsletter references only
            # (This is just title/publication, not the full summary content)
            for newsletter in newsletters:
                nl_text = f"{newsletter.get('publication', '')} - {newsletter.get('title', '')}"
                total_tokens += self.estimate_text_tokens(nl_text)

            logger.debug(
                f"Newsletter reference tokens: {total_tokens} for {len(newsletters)} newsletters "
                f"(Note: summary content not included, may underestimate)"
            )

        # 2. Theme content tokens (if provided)
        if themes:
            themes_tokens = 0
            for theme in themes:
                # Estimate theme content
                # Themes have: name, description, key_points, continuity_text
                theme_text = ""
                if hasattr(theme, "name"):
                    theme_text += theme.name
                if hasattr(theme, "description"):
                    theme_text += " " + theme.description
                if hasattr(theme, "key_points"):
                    theme_text += " " + " ".join(theme.key_points[:3])  # Top 3 points
                if hasattr(theme, "continuity_text") and theme.continuity_text:
                    theme_text += " " + theme.continuity_text

                themes_tokens += self.estimate_text_tokens(theme_text)

            total_tokens += themes_tokens
            logger.debug(f"Theme tokens: {themes_tokens} for {len(themes)} themes")

        # 3. Prompt template tokens (if provided)
        if prompt_template:
            prompt_tokens = self.estimate_text_tokens(prompt_template)
            total_tokens += prompt_tokens
            logger.debug(f"Prompt template tokens: {prompt_tokens}")

        logger.info(
            f"Total estimated tokens: {total_tokens} "
            f"({len(newsletters)} newsletters, {len(themes or [])} themes)"
        )

        return total_tokens

    def calculate_token_budget(
        self,
        model_id: str,
        provider: Provider,
        context_window_percentage: float = 0.5,
    ) -> dict[str, int]:
        """
        Calculate token budget allocation for digest generation.

        Args:
            model_id: Model ID (e.g., "claude-sonnet-4-5")
            provider: Provider enum value
            context_window_percentage: Percentage of context window to use (default: 0.5 = 50%)

        Returns:
            Dictionary with token budget breakdown:
            {
                "total_context": 200000,
                "available_for_input": 100000,  # 50% of context
                "newsletter_budget": 60000,     # 60% of input budget
                "theme_budget": 30000,          # 30% of input budget
                "prompt_overhead": 10000,       # 10% of input budget
                "max_output_tokens": 8192,      # From model config
            }

        Raises:
            ValueError: If model not found or provider not configured
        """
        logger.debug(
            f"Calculating token budget for model={model_id}, "
            f"provider={provider.value}, "
            f"context_percentage={context_window_percentage}"
        )

        # Get model configuration
        try:
            provider_config = self.model_config.get_provider_model_config(model_id, provider)
        except ValueError as e:
            logger.error(f"Failed to get model config: {e}")
            raise ValueError(
                f"Cannot calculate token budget for model {model_id} "
                f"on provider {provider.value}: {e}"
            )

        total_context = provider_config.context_window
        max_output = provider_config.max_output_tokens

        # Calculate available input tokens (percentage of context window)
        available_for_input = int(total_context * context_window_percentage)

        # Allocate input budget:
        # - 60% for newsletters
        # - 30% for themes
        # - 10% for prompt overhead
        newsletter_budget = int(available_for_input * 0.6)
        theme_budget = int(available_for_input * 0.3)
        prompt_overhead = int(available_for_input * 0.1)

        budget = {
            "total_context": total_context,
            "available_for_input": available_for_input,
            "newsletter_budget": newsletter_budget,
            "theme_budget": theme_budget,
            "prompt_overhead": prompt_overhead,
            "max_output_tokens": max_output,
        }

        logger.info(
            f"Token budget calculated: "
            f"total={total_context}, "
            f"input={available_for_input} ({context_window_percentage * 100:.0f}%), "
            f"newsletters={newsletter_budget}, "
            f"themes={theme_budget}, "
            f"overhead={prompt_overhead}"
        )

        return budget

    def calculate_newsletters_that_fit(
        self,
        newsletters: list[dict],
        token_budget: int,
    ) -> int:
        """
        Calculate how many newsletters fit within token budget.

        Uses greedy approach: count newsletters until budget exceeded.

        Args:
            newsletters: List of newsletter dicts
            token_budget: Maximum tokens allowed

        Returns:
            Number of newsletters that fit in budget
        """
        total_tokens = 0
        count = 0

        for newsletter in newsletters:
            nl_text = f"{newsletter.get('publication', '')} - {newsletter.get('title', '')}"
            nl_tokens = self.estimate_text_tokens(nl_text)

            if total_tokens + nl_tokens > token_budget:
                break

            total_tokens += nl_tokens
            count += 1

        logger.debug(
            f"Calculated {count} newsletters fit in {token_budget} tokens "
            f"(using {total_tokens} tokens)"
        )

        return count
