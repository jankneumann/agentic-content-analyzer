"""Base classes for agent implementations."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from src.config.models import ModelConfig, ModelStep, Provider
from src.models.summary import SummaryData
from src.services.prompt_service import PromptService

if TYPE_CHECKING:
    from src.models.content import Content


class AgentResponse(BaseModel):
    """Base response from an agent."""

    success: bool
    data: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] = {}


class SummarizationAgent(ABC):
    """Abstract base class for content summarization agents."""

    def __init__(
        self,
        model_config: ModelConfig,
        step: ModelStep = ModelStep.SUMMARIZATION,
        model: str | None = None,
        api_key: str | None = None,
        prompt_service: PromptService | None = None,
    ) -> None:
        """
        Initialize the agent.

        Args:
            model_config: Model configuration instance
            step: Pipeline step this agent is used for (default: SUMMARIZATION)
            model: Optional model override (for backward compatibility)
            api_key: Optional API key override (for backward compatibility)
            prompt_service: Optional PromptService for configurable prompts
        """
        self.model_config = model_config
        self.step = step
        self.framework_name = self.__class__.__name__.replace("Agent", "").lower()

        # Get model for this step (or use override)
        self.model = model or model_config.get_model_for_step(step)

        # Backward compatibility: store api_key if provided
        self.api_key = api_key

        # Prompt service for configurable prompts
        self.prompt_service = prompt_service or PromptService()

        # Track provider used (set by subclass during API call)
        self.provider_used: Provider | None = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.model_version: str | None = None  # Track model version used

    @abstractmethod
    def summarize_content(self, content: "Content") -> AgentResponse:
        """
        Summarize content from the unified Content model.

        Args:
            content: Content to summarize

        Returns:
            AgentResponse with SummaryData
        """
        pass

    def calculate_cost(self) -> float:
        """
        Calculate the cost of the last API call.

        Returns:
            Cost in USD based on actual provider used and token counts
        """
        if not self.provider_used or not (self.input_tokens or self.output_tokens):
            return 0.0

        return self.model_config.calculate_cost(
            model_id=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            provider=self.provider_used,
        )

    def _validate_summary_data(
        self,
        data: dict[str, Any],
        content_id: int | None = None,
    ) -> SummaryData:
        """
        Validate and convert response data to SummaryData.

        Args:
            data: Raw response data
            content_id: Content ID

        Returns:
            Validated SummaryData object
        """
        return SummaryData(
            content_id=content_id,
            executive_summary=data.get("executive_summary", ""),
            key_themes=data.get("key_themes", []),
            strategic_insights=data.get("strategic_insights", []),
            technical_details=data.get("technical_details", []),
            actionable_items=data.get("actionable_items", []),
            notable_quotes=data.get("notable_quotes", []),
            relevant_links=data.get("relevant_links", []),
            relevance_scores=data.get("relevance_scores", {}),
            agent_framework=self.framework_name,
            model_used=self.model,
            model_version=self.model_version,
        )

    def _create_content_prompt(self, content: "Content") -> str:
        """
        Create the summarization prompt for Content model.

        Uses Content's markdown_content which is already in optimal format for LLMs.
        Loads the prompt template from PromptService for customizability.

        Args:
            content: Content to summarize

        Returns:
            Formatted prompt string
        """
        # Use markdown content (primary) - already optimized for LLM consumption
        markdown_content = content.markdown_content or ""

        # Truncate for token limits (markdown is more efficient than HTML)
        max_chars = 20000  # Higher limit since markdown is more compact
        if len(markdown_content) > max_chars:
            markdown_content = markdown_content[:max_chars] + "\n\n[Content truncated...]"

        return self.prompt_service.render(
            "pipeline.summarization.user_template",
            title=content.title,
            publication=content.publication or "Unknown",
            author=content.author or "Unknown",
            published_date=str(content.published_date),
            source_type=content.source_type.value if content.source_type else "Unknown",
            markdown_content=markdown_content,
        )
