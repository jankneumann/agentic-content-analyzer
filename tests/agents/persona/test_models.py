"""Tests for persona configuration models."""

from dataclasses import dataclass

import pytest

from src.agents.persona.models import (
    AnalysisPreferences,
    CommunicationStyle,
    DomainFocus,
    OutputDefaults,
    PersonaConfig,
    RelevanceWeighting,
)
from src.models.approval_request import RiskLevel


@pytest.fixture()
def tech_persona() -> PersonaConfig:
    """A fully-specified tech persona for testing."""
    return PersonaConfig(
        name="AI/ML Technology Analyst",
        role="Senior ML engineer",
        domain_focus=DomainFocus(
            primary=["machine_learning", "deep_learning"],
            secondary=["mlops"],
        ),
        analysis_preferences=AnalysisPreferences(
            depth="exhaustive",
            perspective="tactical",
            time_horizon="3_months",
            novelty_bias=0.8,
        ),
        relevance_weighting=RelevanceWeighting(
            strategic_impact=0.15,
            technical_depth=0.40,
            novelty=0.30,
            cross_domain_relevance=0.15,
        ),
        model_overrides={
            "theme_analysis": "claude-sonnet-4-5",
            "summarization": "claude-haiku-4-5",
        },
        approval_overrides={"store_graph_episode": RiskLevel.MEDIUM},
        restricted_tools=[],
        output_defaults=OutputDefaults(
            default_format="technical_report",
            include_code_examples=True,
            include_architecture_diagrams=True,
            max_insight_length=800,
        ),
        communication_style=CommunicationStyle(
            tone="technical_detailed",
            audience="engineers_and_architects",
        ),
    )


@pytest.fixture()
def leadership_persona() -> PersonaConfig:
    """A leadership persona with tool restrictions."""
    return PersonaConfig(
        name="Leadership Strategist",
        role="VP/CTO advisor",
        restricted_tools=["fetch_url", "search_web"],
        output_defaults=OutputDefaults(
            default_format="executive_briefing",
            max_insight_length=300,
        ),
    )


class TestResolveModel:
    def test_returns_override_when_configured(self, tech_persona: PersonaConfig) -> None:
        assert tech_persona.resolve_model("theme_analysis") == "claude-sonnet-4-5"
        assert tech_persona.resolve_model("summarization") == "claude-haiku-4-5"

    def test_returns_none_for_unconfigured_step(self, tech_persona: PersonaConfig) -> None:
        assert tech_persona.resolve_model("research") is None

    def test_empty_overrides_always_returns_none(self) -> None:
        persona = PersonaConfig(name="test", role="test")
        assert persona.resolve_model("anything") is None


class TestFilterTools:
    def test_no_restrictions_returns_all(self, tech_persona: PersonaConfig) -> None:
        @dataclass
        class FakeTool:
            name: str

        tools = [FakeTool("search"), FakeTool("fetch_url"), FakeTool("analyze")]
        result = tech_persona.filter_tools(tools)
        assert len(result) == 3

    def test_restricted_tools_are_removed(self, leadership_persona: PersonaConfig) -> None:
        @dataclass
        class FakeTool:
            name: str

        tools = [
            FakeTool("search_content"),
            FakeTool("fetch_url"),
            FakeTool("search_web"),
            FakeTool("analyze_themes"),
        ]
        result = leadership_persona.filter_tools(tools)
        names = [t.name for t in result]
        assert "fetch_url" not in names
        assert "search_web" not in names
        assert "search_content" in names
        assert "analyze_themes" in names

    def test_empty_tools_list(self, leadership_persona: PersonaConfig) -> None:
        assert leadership_persona.filter_tools([]) == []


class TestResolveOutput:
    def test_returns_defaults_when_no_schedule_output(self, tech_persona: PersonaConfig) -> None:
        output = tech_persona.resolve_output()
        assert output.default_format == "technical_report"
        assert output.include_code_examples is True
        assert output.max_insight_length == 800

    def test_schedule_output_overrides_format(self, tech_persona: PersonaConfig) -> None:
        output = tech_persona.resolve_output(schedule_output="executive_briefing")
        assert output.default_format == "executive_briefing"
        # Other fields preserved from persona defaults
        assert output.include_code_examples is True
        assert output.max_insight_length == 800

    def test_does_not_mutate_original(self, tech_persona: PersonaConfig) -> None:
        tech_persona.resolve_output(schedule_output="digest")
        # Original output_defaults unchanged
        assert tech_persona.output_defaults.default_format == "technical_report"


class TestPersonaConfigDefaults:
    def test_minimal_config(self) -> None:
        """Only name and role are required — everything else has defaults."""
        persona = PersonaConfig(name="minimal", role="test role")
        assert persona.domain_focus.primary == []
        assert persona.analysis_preferences.depth == "thorough"
        assert persona.model_overrides == {}
        assert persona.approval_overrides == {}
        assert persona.restricted_tools == []
        assert persona.output_defaults.default_format == "digest"

    def test_novelty_bias_bounds(self) -> None:
        with pytest.raises(Exception):
            AnalysisPreferences(novelty_bias=1.5)
        with pytest.raises(Exception):
            AnalysisPreferences(novelty_bias=-0.1)
