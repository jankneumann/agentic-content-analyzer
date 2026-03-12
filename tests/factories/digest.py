"""Factory for Digest model."""

from datetime import UTC, datetime, timedelta

import factory

from src.models.digest import Digest, DigestStatus, DigestType


class DigestFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating Digest instances.

    Traits:
        daily: Creates a daily digest (default)
        weekly: Creates a weekly digest covering 7 days
        pending: Creates digest in PENDING status
        completed: Creates digest in COMPLETED status
        pending_review: Creates digest awaiting review
        approved: Creates approved digest ready for delivery
        delivered: Creates delivered digest
        with_sources: Includes realistic source content IDs

    Examples:
        # Daily digest (default)
        digest = DigestFactory()

        # Weekly digest pending review
        digest = DigestFactory(weekly=True, pending_review=True)

        # Approved daily digest with sources
        digest = DigestFactory(approved=True, with_sources=True)
    """

    class Meta:
        model = Digest
        sqlalchemy_session = None  # Set by fixture
        sqlalchemy_session_persistence = "commit"

    # Digest type
    digest_type = DigestType.DAILY

    # Time period
    period_start = factory.LazyFunction(
        lambda: (
            datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        )
    )
    period_end = factory.LazyFunction(
        lambda: (
            datetime.now(UTC).replace(hour=23, minute=59, second=59, microsecond=0)
            - timedelta(days=1)
        )
    )

    # Content
    title = factory.Sequence(lambda n: f"AI & Data Daily Digest #{n}")
    executive_overview = factory.Sequence(
        lambda n: (
            f"Digest #{n}: Key developments in AI and data technology. "
            f"This digest covers major announcements, technical breakthroughs, "
            f"and strategic implications for technology leaders."
        )
    )

    strategic_insights = factory.LazyFunction(
        lambda: [
            {
                "title": "Enterprise AI Adoption Accelerates",
                "summary": "Organizations are moving from pilots to production deployments.",
                "details": ["Cost reduction", "Efficiency gains", "Competitive advantage"],
                "themes": ["ai", "enterprise"],
            },
            {
                "title": "Data Quality Emerges as Critical Factor",
                "summary": "Data quality issues remain the top barrier to AI success.",
                "details": ["Data governance", "Quality metrics", "Pipeline reliability"],
                "themes": ["data", "quality"],
            },
        ]
    )

    technical_developments = factory.LazyFunction(
        lambda: [
            {
                "title": "New Foundation Models Released",
                "summary": "Major labs released improved language models with enhanced reasoning.",
                "details": ["Better reasoning", "Longer context", "Lower costs"],
                "themes": ["models", "llm"],
            },
        ]
    )

    emerging_trends = factory.LazyFunction(
        lambda: [
            {
                "title": "Agent Frameworks Gaining Traction",
                "summary": "Multi-agent systems show promise for complex task automation.",
                "details": ["Orchestration patterns", "Tool use", "Human-in-the-loop"],
                "themes": ["agents", "automation"],
            },
        ]
    )

    actionable_recommendations = factory.LazyFunction(
        lambda: {
            "immediate": ["Review current AI initiatives", "Assess data quality"],
            "short_term": ["Build evaluation frameworks", "Train teams"],
            "strategic": ["Develop AI roadmap", "Identify high-value use cases"],
        }
    )

    sources = factory.LazyFunction(
        lambda: [
            {"content_id": 1, "title": "Source Article 1", "publication": "Tech Newsletter"},
            {"content_id": 2, "title": "Source Article 2", "publication": "AI Weekly"},
        ]
    )

    # Historical context
    historical_context = factory.LazyFunction(
        lambda: [
            {
                "topic": "Enterprise AI",
                "context": "Continuation of Q4 2024 adoption trends",
                "related_digests": [1, 2, 3],
            }
        ]
    )

    # Unified content model fields
    markdown_content = factory.LazyAttribute(
        lambda o: (
            f"# {o.title}\n\n{o.executive_overview}\n\n"
            f"## Strategic Insights\n\n"
            + "\n".join(f"### {i['title']}\n{i['summary']}" for i in o.strategic_insights)
        )
    )
    theme_tags = factory.LazyFunction(lambda: ["ai", "enterprise", "data", "models"])
    source_content_ids = None

    # Metadata
    newsletter_count = factory.Faker("random_int", min=3, max=15)
    status = DigestStatus.COMPLETED
    created_at = factory.LazyFunction(lambda: datetime.now(UTC))
    completed_at = factory.LazyFunction(lambda: datetime.now(UTC))
    delivered_at = None

    # Generation metadata
    agent_framework = "anthropic"
    model_used = "claude-sonnet-4-5"
    model_version = "20250514"
    token_usage = factory.Faker("random_int", min=2000, max=8000)
    processing_time_seconds = factory.Faker("random_int", min=10, max=60)

    # Review tracking
    reviewed_by = None
    review_notes = None
    reviewed_at = None
    revision_count = 0
    revision_history = None

    # Hierarchical digest support
    parent_digest_id = None
    child_digest_ids = None
    is_combined = False
    source_digest_count = None

    # --- Traits ---

    class Params:
        daily = factory.Trait(
            digest_type=DigestType.DAILY,
            title=factory.Sequence(lambda n: f"AI & Data Daily Digest #{n}"),
        )
        weekly = factory.Trait(
            digest_type=DigestType.WEEKLY,
            title=factory.Sequence(lambda n: f"AI & Data Weekly Digest #{n}"),
            period_start=factory.LazyFunction(
                lambda: (
                    datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
                    - timedelta(days=7)
                )
            ),
            newsletter_count=factory.Faker("random_int", min=15, max=50),
        )
        pending = factory.Trait(
            status=DigestStatus.PENDING,
            completed_at=None,
        )
        completed = factory.Trait(
            status=DigestStatus.COMPLETED,
        )
        pending_review = factory.Trait(
            status=DigestStatus.PENDING_REVIEW,
        )
        approved = factory.Trait(
            status=DigestStatus.APPROVED,
            reviewed_by="reviewer@example.com",
            review_notes="Looks good, approved for delivery.",
            reviewed_at=factory.LazyFunction(lambda: datetime.now(UTC)),
        )
        rejected = factory.Trait(
            status=DigestStatus.REJECTED,
            reviewed_by="reviewer@example.com",
            review_notes="Needs more context on the AI adoption section.",
            reviewed_at=factory.LazyFunction(lambda: datetime.now(UTC)),
        )
        delivered = factory.Trait(
            status=DigestStatus.DELIVERED,
            reviewed_by="reviewer@example.com",
            reviewed_at=factory.LazyFunction(lambda: datetime.now(UTC) - timedelta(hours=2)),
            delivered_at=factory.LazyFunction(lambda: datetime.now(UTC)),
        )
        with_sources = factory.Trait(
            source_content_ids=factory.LazyFunction(lambda: [1, 2, 3, 4, 5]),
            newsletter_count=5,
            sources=factory.LazyFunction(
                lambda: [
                    {"content_id": i, "title": f"Article {i}", "publication": "Newsletter"}
                    for i in range(1, 6)
                ]
            ),
        )
        combined = factory.Trait(
            is_combined=True,
            child_digest_ids=factory.LazyFunction(lambda: [10, 11, 12]),
            source_digest_count=3,
            digest_type=DigestType.WEEKLY,
        )
