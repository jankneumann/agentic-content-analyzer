"""Factory for Summary model."""

from datetime import UTC, datetime

import factory

from src.models.summary import Summary
from tests.factories.content import ContentFactory


class SummaryFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating Summary instances.

    Summaries are linked to Content records. By default, creates a
    ContentFactory instance for the relationship.

    Examples:
        # Summary with auto-created content
        summary = SummaryFactory()

        # Summary for specific content
        content = ContentFactory()
        summary = SummaryFactory(content=content, content_id=content.id)

        # Summary without content relationship
        summary = SummaryFactory(content=None, content_id=None)
    """

    class Meta:
        model = Summary
        sqlalchemy_session = None  # Set by fixture
        sqlalchemy_session_persistence = "commit"

    # Content relationship
    content = factory.SubFactory(ContentFactory)
    content_id = factory.LazyAttribute(lambda o: o.content.id if o.content else None)

    # Summary content
    executive_summary = factory.Sequence(
        lambda n: (
            f"Executive summary {n}: This article discusses key developments in AI "
            f"technology and their implications for enterprise adoption."
        )
    )

    key_themes = factory.LazyFunction(
        lambda: [
            "Artificial Intelligence",
            "Machine Learning",
            "Enterprise Technology",
            "Automation",
        ]
    )

    strategic_insights = factory.LazyFunction(
        lambda: [
            "AI adoption is accelerating across industries",
            "Cost reduction remains a primary driver for implementation",
            "Data quality is the biggest barrier to success",
        ]
    )

    technical_details = factory.LazyFunction(
        lambda: [
            "Uses transformer architecture for NLP tasks",
            "Requires GPU for optimal inference performance",
            "Supports batch processing for high throughput",
        ]
    )

    actionable_items = factory.LazyFunction(
        lambda: [
            "Evaluate current AI readiness",
            "Identify high-value automation opportunities",
            "Build data pipeline infrastructure",
        ]
    )

    notable_quotes = factory.LazyFunction(
        lambda: [
            '"AI will transform every industry" - Tech CEO',
            '"The future is already here" - Industry Analyst',
        ]
    )

    relevant_links = factory.LazyFunction(
        lambda: [
            {"title": "AI Best Practices Guide", "url": "https://example.com/guide"},
            {"title": "Case Study", "url": "https://example.com/case-study"},
        ]
    )

    # Relevance scoring
    relevance_scores = factory.LazyFunction(
        lambda: {
            "technical_leadership": 0.85,
            "strategic_planning": 0.72,
            "product_development": 0.65,
            "overall": 0.74,
        }
    )

    # Unified content model fields
    markdown_content = factory.LazyAttribute(
        lambda o: (
            f"# Summary\n\n{o.executive_summary}\n\n"
            f"## Key Themes\n\n" + "\n".join(f"- {t}" for t in o.key_themes)
        )
    )
    theme_tags = factory.LazyFunction(lambda: ["ai", "ml", "enterprise", "automation"])

    # Metadata
    agent_framework = "anthropic"
    model_used = "claude-sonnet-4-5"
    model_version = "20250514"
    created_at = factory.LazyFunction(lambda: datetime.now(UTC))
    token_usage = factory.Faker("random_int", min=500, max=2000)
    processing_time_seconds = factory.Faker("pyfloat", min_value=1.0, max_value=10.0)

    # --- Traits ---

    class Params:
        minimal = factory.Trait(
            key_themes=factory.LazyFunction(lambda: ["AI"]),
            strategic_insights=factory.LazyFunction(lambda: ["Key insight"]),
            technical_details=factory.LazyFunction(lambda: []),
            actionable_items=factory.LazyFunction(lambda: []),
            notable_quotes=factory.LazyFunction(lambda: []),
            relevant_links=factory.LazyFunction(lambda: []),
        )
        openai = factory.Trait(
            agent_framework="openai",
            model_used="gpt-4o",
            model_version="2024-08-06",
        )
        high_relevance = factory.Trait(
            relevance_scores=factory.LazyFunction(
                lambda: {
                    "technical_leadership": 0.95,
                    "strategic_planning": 0.92,
                    "product_development": 0.88,
                    "overall": 0.92,
                }
            )
        )
        low_relevance = factory.Trait(
            relevance_scores=factory.LazyFunction(
                lambda: {
                    "technical_leadership": 0.25,
                    "strategic_planning": 0.30,
                    "product_development": 0.20,
                    "overall": 0.25,
                }
            )
        )
