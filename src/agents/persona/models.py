"""Persona configuration models.

Pydantic models that define the full persona schema — a policy bundle
controlling domain focus, analysis style, model selection, tool access,
approval thresholds, output format, and communication style.
"""

from pydantic import BaseModel, Field

from src.models.approval_request import RiskLevel


class DomainFocus(BaseModel):
    """Primary and secondary domain interests for the persona."""

    primary: list[str] = Field(default_factory=list)
    secondary: list[str] = Field(default_factory=list)


class AnalysisPreferences(BaseModel):
    """How deeply and from what angle the persona analyzes content."""

    depth: str = "thorough"  # brief | standard | thorough | exhaustive
    perspective: str = "both"  # tactical | strategic | both
    time_horizon: str = "6_months"  # 1_month | 3_months | 6_months | 1_year
    novelty_bias: float = Field(default=0.5, ge=0.0, le=1.0)


class RelevanceWeighting(BaseModel):
    """Weights for scoring content relevance."""

    strategic_impact: float = 0.3
    technical_depth: float = 0.25
    novelty: float = 0.25
    cross_domain_relevance: float = 0.2


class OutputDefaults(BaseModel):
    """Default output format and style settings."""

    default_format: str = "digest"  # technical_report | executive_briefing | digest | raw_insights
    include_code_examples: bool = False
    include_architecture_diagrams: bool = False
    include_confidence: bool = True
    include_sources: bool = True
    max_insight_length: int = 500


class CommunicationStyle(BaseModel):
    """How the persona writes — applies regardless of output format."""

    tone: str = "professional_concise"
    format: str = "structured_markdown"
    audience: str = "technical_leaders"


class PersonaConfig(BaseModel):
    """Validated persona configuration with inheritance from default.

    A persona is a policy bundle controlling:
    - Domain focus and analysis lens
    - Model selection per pipeline step
    - Tool access restrictions
    - Approval threshold overrides
    - Output format and communication style
    """

    name: str
    role: str
    domain_focus: DomainFocus = Field(default_factory=DomainFocus)
    analysis_preferences: AnalysisPreferences = Field(default_factory=AnalysisPreferences)
    relevance_weighting: RelevanceWeighting = Field(default_factory=RelevanceWeighting)
    model_overrides: dict[str, str] = Field(default_factory=dict)
    approval_overrides: dict[str, RiskLevel] = Field(default_factory=dict)
    restricted_tools: list[str] = Field(default_factory=list)
    output_defaults: OutputDefaults = Field(default_factory=OutputDefaults)
    communication_style: CommunicationStyle = Field(default_factory=CommunicationStyle)

    def resolve_model(self, step: str) -> str | None:
        """Return model override for a pipeline step, or None to use global default."""
        return self.model_overrides.get(step)

    def filter_tools(self, tools: list) -> list:
        """Remove tools that this persona is restricted from using.

        Tools are expected to have a ``name`` attribute. If ``restricted_tools``
        is empty, all tools are returned unchanged.
        """
        if not self.restricted_tools:
            return tools
        return [t for t in tools if t.name not in self.restricted_tools]

    def resolve_output(self, schedule_output: str | None = None) -> OutputDefaults:
        """Merge schedule-level output format with persona's output defaults.

        The schedule specifies *what format* (e.g., ``"executive_briefing"``).
        The persona specifies *how to write it* (e.g., max_insight_length).
        """
        if schedule_output:
            return self.output_defaults.model_copy(
                update={"default_format": schedule_output}
            )
        return self.output_defaults
