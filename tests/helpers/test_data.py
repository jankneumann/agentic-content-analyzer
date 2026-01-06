"""Test data helpers for loading and ingesting test newsletters."""

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from src.models.newsletter import Newsletter, NewsletterSource, ProcessingStatus

# Path to test data directory
TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"
NEWSLETTERS_DIR = TEST_DATA_DIR / "newsletters"


def load_test_newsletter_data(filename: str) -> dict:
    """
    Load test newsletter data from JSON file.

    Args:
        filename: Name of JSON file in tests/test_data/newsletters/

    Returns:
        Dictionary with newsletter data
    """
    file_path = NEWSLETTERS_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(f"Test newsletter not found: {file_path}")

    with open(file_path) as f:
        data = json.load(f)

    # Convert ISO date string to datetime if needed
    if isinstance(data.get("published_date"), str):
        data["published_date"] = datetime.fromisoformat(
            data["published_date"].replace("Z", "+00:00")
        )

    return data


def create_test_newsletter(
    db: Session, filename: str, status: ProcessingStatus = ProcessingStatus.PENDING
) -> Newsletter:
    """
    Load test newsletter from JSON and insert into database.

    Args:
        db: Database session
        filename: Name of JSON file in tests/test_data/newsletters/
        status: Initial processing status

    Returns:
        Created Newsletter object
    """
    data = load_test_newsletter_data(filename)

    newsletter = Newsletter(
        source=NewsletterSource[data["source"]],
        source_id=data["source_id"],
        sender=data["sender"],
        publication=data["publication"],
        title=data["title"],
        published_date=data["published_date"],
        url=data.get("url"),
        raw_html=data.get("raw_html"),
        raw_text=data.get("raw_text"),
        status=status,
    )

    db.add(newsletter)
    db.commit()
    db.refresh(newsletter)

    return newsletter


def create_test_newsletters_batch(
    db: Session,
    filenames: list[str] | None = None,
    status: ProcessingStatus = ProcessingStatus.PENDING,
) -> list[Newsletter]:
    """
    Load multiple test newsletters and insert into database.

    Args:
        db: Database session
        filenames: List of JSON filenames. If None, loads all newsletters in test_data
        status: Initial processing status

    Returns:
        List of created Newsletter objects
    """
    if filenames is None:
        # Load all JSON files from newsletters directory
        filenames = sorted([f.name for f in NEWSLETTERS_DIR.glob("*.json")])

    newsletters = []
    for filename in filenames:
        newsletter = create_test_newsletter(db, filename, status)
        newsletters.append(newsletter)

    return newsletters


def get_default_test_newsletters() -> list[str]:
    """
    Get list of default test newsletter filenames.

    Returns:
        List of JSON filenames
    """
    return [
        "newsletter_1_llm_advances.json",
        "newsletter_2_vector_databases.json",
        "newsletter_3_agent_frameworks.json",
    ]
