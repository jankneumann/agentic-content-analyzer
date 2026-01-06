"""Base classes for agent implementations."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from src.config.models import ModelConfig, ModelStep, Provider
from src.models.newsletter import Newsletter
from src.models.summary import SummaryData


class AgentResponse(BaseModel):
    """Base response from an agent."""

    success: bool
    data: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] = {}


class SummarizationAgent(ABC):
    """Abstract base class for newsletter summarization agents."""

    def __init__(
        self,
        model_config: ModelConfig,
        step: ModelStep = ModelStep.SUMMARIZATION,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """
        Initialize the agent.

        Args:
            model_config: Model configuration instance
            step: Pipeline step this agent is used for (default: SUMMARIZATION)
            model: Optional model override (for backward compatibility)
            api_key: Optional API key override (for backward compatibility)
        """
        self.model_config = model_config
        self.step = step
        self.framework_name = self.__class__.__name__.replace("Agent", "").lower()

        # Get model for this step (or use override)
        self.model = model or model_config.get_model_for_step(step)

        # Backward compatibility: store api_key if provided
        self.api_key = api_key

        # Track provider used (set by subclass during API call)
        self.provider_used: Provider | None = None
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.model_version: str | None = None  # Track model version used

    @abstractmethod
    def summarize_newsletter(self, newsletter: Newsletter) -> AgentResponse:
        """
        Summarize a newsletter.

        Args:
            newsletter: Newsletter to summarize

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

    def _create_summary_prompt(self, newsletter: Newsletter) -> str:
        """
        Create the summarization prompt.

        Args:
            newsletter: Newsletter to summarize

        Returns:
            Formatted prompt string
        """
        # Use text content, fall back to HTML if needed
        content = newsletter.raw_text or newsletter.raw_html or ""

        prompt = f"""You are an expert at summarizing AI and technology newsletters for technical leaders and developers at Comcast.

Your audience ranges from CTOs needing strategic insights to individual developers seeking actionable best practices.

Please analyze this newsletter and provide a structured summary:

**Newsletter Details:**
- Title: {newsletter.title}
- Publication: {newsletter.publication}
- Date: {newsletter.published_date}

**Content:**
{content[:15000]}  # Limit to ~15K chars to avoid token limits

**Required Output (JSON format):**
{{
    "executive_summary": "2-3 sentence summary capturing the essence and why it matters",
    "key_themes": ["theme1", "theme2", "theme3"],  # 3-5 main topics/themes
    "strategic_insights": ["insight1", "insight2"],  # CTO-level implications
    "technical_details": ["detail1", "detail2"],  # Developer-focused specifics
    "actionable_items": ["action1", "action2"],  # What readers should do
    "notable_quotes": ["quote1", "quote2"],  # Important quotes or data points
    "relevant_links": [  # Links to referenced resources for deeper reading
        {{"title": "Resource Title", "url": "https://..."}},
        {{"title": "Another Resource", "url": "https://..."}}
    ],
    "relevance_scores": {{
        "cto_leadership": 0.0-1.0,  # How relevant for C-level
        "technical_teams": 0.0-1.0,  # How relevant for dev teams
        "individual_developers": 0.0-1.0  # How relevant for individuals
    }}
}}

Focus on:
- Strategic implications for AI/Data leadership
- Actionable technical insights
- Trends and patterns in the AI/tech landscape
- Practical applications for enterprise settings
- Best practices and recommendations
- Extract links to referenced papers, articles, or resources (arxiv, research blogs, documentation, etc.)

Provide ONLY the JSON output, no additional commentary."""

        return prompt

    def _validate_summary_data(self, data: dict[str, Any], newsletter_id: int) -> SummaryData:
        """
        Validate and convert response data to SummaryData.

        Args:
            data: Raw response data
            newsletter_id: Newsletter ID

        Returns:
            Validated SummaryData object
        """
        return SummaryData(
            newsletter_id=newsletter_id,
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
