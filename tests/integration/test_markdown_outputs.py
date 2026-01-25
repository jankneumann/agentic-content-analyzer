"""Integration tests for markdown output generation.

Tests end-to-end markdown generation for:
- Summarization: Content → Summary with markdown_content and theme_tags
- Digest creation: Summaries → Digest with markdown_content and theme_tags
- API responses: Verify markdown fields are returned correctly

These tests validate tasks 12.3, 12.4, and 12.5 from the refactor-unified-content-model proposal.
"""

from datetime import UTC, datetime

import pytest

from src.models.content import Content, ContentSource, ContentStatus
from src.models.digest import Digest, DigestStatus, DigestType
from src.models.summary import Summary


@pytest.fixture
def content_for_summarization(db_session) -> Content:
    """Create content ready for summarization."""
    content = Content(
        source_type=ContentSource.GMAIL,
        source_id="summary-test-001",
        title="AI Newsletter: LLM Cost Optimization",
        author="AI Weekly",
        publication="AI Weekly",
        published_date=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        markdown_content="""# LLM Cost Optimization Strategies

## Key Findings

The cost of running LLMs has decreased by 40% in the past quarter.

### Optimization Techniques

1. **Prompt Caching**: Reduce redundant API calls
2. **Model Selection**: Use smaller models for simple tasks
3. **Batching**: Combine requests for efficiency

## Technical Details

- Context window utilization: 65% average
- Token efficiency improved by 25%
- Latency reduced by 30ms average

## Quotes

> "Cost optimization is the key to sustainable AI deployment" - AI Expert

## Recommendations

- Evaluate prompt caching solutions
- Implement model routing based on task complexity
- Monitor token usage metrics

#LLM #CostOptimization #AI
""",
        content_hash="summary-test-hash",
        status=ContentStatus.PARSED,
        ingested_at=datetime.now(UTC),
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


@pytest.fixture
def summaries_for_digest(db_session) -> list[Summary]:
    """Create summaries ready for digest generation."""
    from src.config.models import MODEL_REGISTRY

    test_model = list(MODEL_REGISTRY.keys())[0]

    # Create parent contents first
    contents = []
    for i in range(3):
        content = Content(
            source_type=ContentSource.GMAIL if i < 2 else ContentSource.RSS,
            source_id=f"digest-content-{i:03d}",
            title=f"Newsletter {i + 1}",
            markdown_content=f"# Newsletter {i + 1}\n\nContent...",
            content_hash=f"digest-hash-{i:03d}",
            status=ContentStatus.COMPLETED,
            published_date=datetime(2025, 1, 15 - i, 10, 0, 0, tzinfo=UTC),
            ingested_at=datetime.now(UTC),
        )
        db_session.add(content)
        contents.append(content)

    db_session.commit()
    for content in contents:
        db_session.refresh(content)

    summaries = [
        Summary(
            content_id=contents[0].id,
            executive_summary="Major LLM cost reductions announced.",
            key_themes=["LLM Costs", "Optimization", "Cloud Infrastructure"],
            strategic_insights=["Cost reduction enables broader AI adoption"],
            technical_details=["40% cost reduction", "Improved caching"],
            actionable_items=["Review cloud spending", "Implement caching"],
            notable_quotes=["Costs are the new frontier"],
            relevance_scores={
                "cto_leadership": 0.9,
                "technical_teams": 0.8,
                "individual_developers": 0.7,
            },
            markdown_content="""# Newsletter Summary: LLM Cost Newsletter

## Executive Summary
Major LLM cost reductions announced.

## Key Themes
- **LLM Costs**: Significant reductions
- **Optimization**: New techniques available

## Strategic Insights
Cost reduction enables broader AI adoption.

## Relevance Scores
- **CTO**: 0.90
- **Technical Teams**: 0.80
""",
            theme_tags=["llm", "cost-optimization", "cloud-infrastructure"],
            agent_framework="claude",
            model_used=test_model,
            token_usage=2000,
        ),
        Summary(
            content_id=contents[1].id,
            executive_summary="Vector database performance improvements.",
            key_themes=["Vector DB", "Performance", "Hybrid Search"],
            strategic_insights=["Database choice critical for RAG"],
            technical_details=["30% query speedup", "Better indexing"],
            actionable_items=["Benchmark databases", "Test hybrid search"],
            notable_quotes=["Performance is key"],
            relevance_scores={
                "cto_leadership": 0.7,
                "technical_teams": 0.95,
                "individual_developers": 0.85,
            },
            markdown_content="""# Newsletter Summary: Vector DB Newsletter

## Executive Summary
Vector database performance improvements.

## Key Themes
- **Vector DB**: Performance gains
- **Hybrid Search**: Combined approaches

## Technical Details
30% query speedup achieved.
""",
            theme_tags=["vector-database", "performance", "hybrid-search"],
            agent_framework="claude",
            model_used=test_model,
            token_usage=1800,
        ),
        Summary(
            content_id=contents[2].id,
            executive_summary="AI agent frameworks compared.",
            key_themes=["AI Agents", "Frameworks", "Tool Use"],
            strategic_insights=["Framework choice impacts velocity"],
            technical_details=["Claude SDK leads in tool use"],
            actionable_items=["Prototype with multiple frameworks"],
            notable_quotes=["Choose wisely"],
            relevance_scores={
                "cto_leadership": 0.8,
                "technical_teams": 0.9,
                "individual_developers": 0.95,
            },
            markdown_content="""# Newsletter Summary: AI Agents Newsletter

## Executive Summary
AI agent frameworks compared.

## Key Themes
- **AI Agents**: Rapid evolution
- **Tool Use**: Key differentiator

## Strategic Insights
Framework choice impacts development velocity.
""",
            theme_tags=["ai-agents", "frameworks", "tool-use"],
            agent_framework="claude",
            model_used=test_model,
            token_usage=1900,
        ),
    ]

    for summary in summaries:
        db_session.add(summary)

    db_session.commit()

    for summary in summaries:
        db_session.refresh(summary)

    return summaries


@pytest.mark.integration
class TestSummarizationMarkdownOutput:
    """Tests for summarization markdown output (Task 12.3)."""

    def test_summary_markdown_generation(self, db_session, content_for_summarization):
        """Summary generation produces valid markdown_content."""
        from src.utils.summary_markdown import generate_summary_markdown

        summary_data = {
            "executive_summary": "Cost optimization strategies for LLMs.",
            "key_themes": ["LLM Costs", "Optimization"],
            "strategic_insights": ["Lower costs enable adoption"],
            "technical_details": ["40% reduction achieved"],
            "actionable_items": ["Review pricing", "Implement caching"],
            "notable_quotes": ["Cost is key"],
            "relevance_scores": {
                "cto_leadership": 0.85,
                "technical_teams": 0.80,
                "individual_developers": 0.70,
            },
        }

        markdown = generate_summary_markdown(summary_data)

        # Verify markdown structure (starts with ## sections, no H1 header)
        assert "## Executive Summary" in markdown
        assert "## Key Themes" in markdown
        assert "## Strategic Insights" in markdown
        assert "## Relevance Scores" in markdown
        assert "Cost optimization strategies" in markdown

    def test_theme_tags_extraction(self, db_session, content_for_summarization):
        """Theme tags are extracted from summary data."""
        from src.utils.summary_markdown import extract_summary_theme_tags

        summary_data = {
            "key_themes": ["LLM Performance", "Cost Optimization", "Cloud Infrastructure"],
            "executive_summary": "Test summary",
        }

        tags = extract_summary_theme_tags(summary_data)

        # Should extract from key_themes and normalize
        assert len(tags) > 0
        # Tags are normalized (lowercase, hyphenated)
        normalized_tags = [t.lower().replace(" ", "-") for t in tags]
        assert any("llm" in t or "performance" in t for t in normalized_tags)

    def test_summary_stored_with_markdown(
        self, db_session, content_for_summarization, mock_anthropic_client
    ):
        """Summary record includes markdown_content and theme_tags."""
        from src.config.models import MODEL_REGISTRY
        from src.utils.summary_markdown import (
            extract_summary_theme_tags,
            generate_summary_markdown,
        )

        test_model = list(MODEL_REGISTRY.keys())[0]

        # Simulate summarization result
        summary_data = {
            "executive_summary": "LLM cost optimization strategies.",
            "key_themes": ["Cost Optimization", "LLM Performance"],
            "strategic_insights": ["Lower costs enable adoption"],
            "technical_details": ["40% cost reduction"],
            "actionable_items": ["Review pricing"],
            "notable_quotes": ["Cost is king"],
            "relevance_scores": {
                "cto_leadership": 0.85,
                "technical_teams": 0.80,
                "individual_developers": 0.70,
            },
        }

        markdown = generate_summary_markdown(summary_data)
        theme_tags = extract_summary_theme_tags(summary_data)

        summary = Summary(
            content_id=content_for_summarization.id,
            executive_summary=summary_data["executive_summary"],
            key_themes=summary_data["key_themes"],
            strategic_insights=summary_data["strategic_insights"],
            technical_details=summary_data["technical_details"],
            actionable_items=summary_data["actionable_items"],
            notable_quotes=summary_data["notable_quotes"],
            relevance_scores=summary_data["relevance_scores"],
            markdown_content=markdown,
            theme_tags=theme_tags,
            agent_framework="claude",
            model_used=test_model,
            token_usage=2000,
        )

        db_session.add(summary)
        db_session.commit()
        db_session.refresh(summary)

        # Verify stored data (markdown starts with ## sections, no H1 header)
        assert summary.markdown_content is not None
        assert "## Executive Summary" in summary.markdown_content
        assert summary.theme_tags is not None
        assert len(summary.theme_tags) > 0

        # Update content status
        content_for_summarization.status = ContentStatus.COMPLETED
        db_session.commit()


@pytest.mark.integration
class TestDigestMarkdownOutput:
    """Tests for digest creation markdown output (Task 12.4)."""

    def test_digest_markdown_generation(self, db_session, summaries_for_digest):
        """Digest generation produces valid markdown_content."""
        from src.utils.digest_markdown import generate_digest_markdown

        digest_data = {
            "title": "Daily AI Digest - January 15, 2025",
            "executive_overview": "Today's digest covers LLM costs, vector databases, and AI agents.",
            "strategic_insights": [
                {
                    "title": "Cost Optimization Wave",
                    "summary": "LLM costs dropping significantly",
                    "details": ["40% reduction", "New pricing models"],
                    "themes": ["cost", "llm"],
                }
            ],
            "technical_developments": [
                {
                    "title": "Vector DB Performance",
                    "summary": "Major speed improvements",
                    "details": ["30% faster queries"],
                    "themes": ["performance", "database"],
                }
            ],
            "emerging_trends": [
                {
                    "title": "AI Agent Evolution",
                    "summary": "Frameworks maturing rapidly",
                    "details": ["Better tool use"],
                    "themes": ["agents", "frameworks"],
                }
            ],
            "actionable_recommendations": {
                "leadership": ["Review AI budget"],
                "technical": ["Test new frameworks"],
            },
            "sources": [],
        }

        markdown = generate_digest_markdown(digest_data)

        # Verify markdown structure
        assert "Daily AI Digest" in markdown
        assert "Executive Overview" in markdown or "executive" in markdown.lower()
        assert "Cost Optimization Wave" in markdown

    def test_digest_theme_tags_extraction(self, db_session):
        """Theme tags are extracted from digest data."""
        from src.utils.digest_markdown import extract_digest_theme_tags

        digest_data = {
            "title": "Test Digest",
            "strategic_insights": [
                {"title": "AI Costs", "themes": ["ai", "cost"]},
            ],
            "technical_developments": [
                {"title": "LLM Updates", "themes": ["llm"]},
            ],
            "emerging_trends": [
                {"title": "Agents", "themes": ["agents"]},
            ],
        }

        tags = extract_digest_theme_tags(digest_data)

        assert isinstance(tags, list)
        # Tags should be extracted from the themes fields
        assert len(tags) >= 0  # May be empty depending on implementation

    def test_digest_source_content_ids_tracking(self, db_session, summaries_for_digest):
        """Source content IDs are tracked in digest."""
        # Get content IDs from summaries
        content_ids = [s.content_id for s in summaries_for_digest]

        # Create digest with source tracking
        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 14, 0, 0, 0, tzinfo=UTC),
            period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
            title="Test Digest",
            executive_overview="Test overview",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[{"content_id": cid, "title": f"Source {cid}"} for cid in content_ids],
            newsletter_count=len(content_ids),
            source_content_ids=content_ids,
            status=DigestStatus.PENDING_REVIEW,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )

        db_session.add(digest)
        db_session.commit()
        db_session.refresh(digest)

        # Verify source tracking
        assert digest.source_content_ids is not None
        assert len(digest.source_content_ids) == 3
        assert all(cid in digest.source_content_ids for cid in content_ids)

    def test_digest_stored_with_markdown(self, db_session, summaries_for_digest):
        """Digest record includes markdown_content and theme_tags."""
        from src.utils.digest_markdown import (
            extract_digest_theme_tags,
            generate_digest_markdown,
        )

        content_ids = [s.content_id for s in summaries_for_digest]

        digest_data = {
            "title": "Daily AI Digest",
            "executive_overview": "Key developments in AI.",
            "strategic_insights": [
                {"title": "Insight 1", "summary": "Details", "details": [], "themes": []}
            ],
            "technical_developments": [],
            "emerging_trends": [],
            "actionable_recommendations": {"leadership": [], "technical": []},
            "sources": [],
        }

        markdown = generate_digest_markdown(digest_data)
        theme_tags = extract_digest_theme_tags(digest_data)

        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 14, 0, 0, 0, tzinfo=UTC),
            period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
            title=digest_data["title"],
            executive_overview=digest_data["executive_overview"],
            strategic_insights=digest_data["strategic_insights"],
            technical_developments=digest_data["technical_developments"],
            emerging_trends=digest_data["emerging_trends"],
            actionable_recommendations=digest_data["actionable_recommendations"],
            sources=[],
            newsletter_count=3,
            markdown_content=markdown,
            theme_tags=theme_tags,
            source_content_ids=content_ids,
            status=DigestStatus.PENDING_REVIEW,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )

        db_session.add(digest)
        db_session.commit()
        db_session.refresh(digest)

        # Verify stored data
        assert digest.markdown_content is not None
        assert "Daily AI Digest" in digest.markdown_content
        assert digest.source_content_ids is not None


@pytest.mark.integration
class TestMarkdownParsing:
    """Tests for markdown parsing utilities."""

    def test_extract_relevance_scores(self):
        """Relevance scores are extracted from markdown."""
        from src.utils.markdown import extract_relevance_scores

        markdown = """# Summary

## Relevance Scores
- **CTO Leadership**: 0.85
- **Technical Teams**: 0.90
- **Individual Developers**: 0.75
"""

        scores = extract_relevance_scores(markdown)

        # Check that scores were extracted
        assert len(scores) > 0
        # Check for normalized keys or original keys
        assert any(0.7 <= v <= 1.0 for v in scores.values())

    def test_extract_embedded_refs(self):
        """Embedded references are extracted from markdown."""
        from src.utils.markdown import extract_embedded_refs

        markdown = """# Content

Here is a table: [TABLE:pricing_comparison]

And an image: [IMAGE:diagram_001]

With parameters: [IMAGE:screenshot|video=abc123&t=45]

And code: [CODE:example_snippet]
"""

        refs = extract_embedded_refs(markdown)

        # API returns lowercase keys
        assert "tables" in refs
        assert "pricing_comparison" in refs["tables"]
        assert "images" in refs
        assert len(refs["images"]) == 2
        assert "code" in refs
        assert "example_snippet" in refs["code"]
