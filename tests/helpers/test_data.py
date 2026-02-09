"""Test data helpers for integration tests.

Provides helper functions to create Content test records using Factory Boy.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.models.content import Content, ContentSource, ContentStatus
from tests.factories.content import ContentFactory


def get_default_test_contents() -> list[str]:
    """Return default list of test content titles.

    Returns:
        List of content title strings for test content creation
    """
    return [
        "Latest LLM Advances",
        "Vector Database Performance",
        "AI Agent Frameworks",
    ]


def create_test_contents_batch(
    db_session: Session,
    titles: list[str] | None = None,
    source_type: ContentSource = ContentSource.GMAIL,
    status: ContentStatus = ContentStatus.COMPLETED,
) -> list[Content]:
    """Create a batch of test Content records in the database.

    Uses ContentFactory for consistent test data generation.

    Args:
        db_session: Database session for creating records
        titles: List of content titles (defaults to get_default_test_contents())
        source_type: ContentSource type for all records
        status: ContentStatus for all records (default: COMPLETED for digest tests)

    Returns:
        List of created Content records with IDs assigned
    """
    if titles is None:
        titles = get_default_test_contents()

    # Ensure factory uses the provided session
    ContentFactory._meta.sqlalchemy_session = db_session  # type: ignore[attr-defined]

    contents = []
    for i, title in enumerate(titles, 1):
        content = ContentFactory(
            source_type=source_type,
            source_id=f"test-content-{i:03d}",
            source_url=f"https://example.com/content-{i}",
            title=title,
            author=f"author{i}@example.com",
            publication=f"Publication {i}",
            published_date=datetime(2025, 1, 15 - i, 10, 0, 0, tzinfo=UTC),
            markdown_content=f"# {title}\n\nTest content about {title.lower()}.",
            content_hash=f"hash{i:03d}",
            status=status,
        )
        contents.append(content)

    return contents  # type: ignore[return-value]
