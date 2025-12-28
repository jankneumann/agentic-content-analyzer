"""Base classes for agent implementations."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel

from src.models.newsletter import Newsletter
from src.models.summary import SummaryData


class AgentResponse(BaseModel):
    """Base response from an agent."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: dict[str, Any] = {}


class SummarizationAgent(ABC):
    """Abstract base class for newsletter summarization agents."""

    def __init__(self, model: str, api_key: str) -> None:
        """
        Initialize the agent.

        Args:
            model: Model identifier (e.g., "claude-3-5-sonnet-20241022")
            api_key: API key for the service
        """
        self.model = model
        self.api_key = api_key
        self.framework_name = self.__class__.__name__.replace("Agent", "").lower()

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
            relevance_scores=data.get("relevance_scores", {}),
            agent_framework=self.framework_name,
            model_used=self.model,
        )
