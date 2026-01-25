"""Test fixtures and fixture utilities.

This module provides utilities for loading sample test data files.

Usage:
    from tests.fixtures import load_fixture, load_markdown, load_html

    # Load by type
    content_md = load_markdown("sample_content.md")
    newsletter_html = load_html("sample_newsletter.html")

    # Load by path
    data = load_fixture("markdown/sample_digest.md")
"""

from pathlib import Path

# Fixtures directory
FIXTURES_DIR = Path(__file__).parent


def load_fixture(relative_path: str) -> str:
    """Load a fixture file by relative path.

    Args:
        relative_path: Path relative to fixtures directory (e.g., "markdown/sample.md")

    Returns:
        File contents as string

    Raises:
        FileNotFoundError: If fixture file doesn't exist
    """
    fixture_path = FIXTURES_DIR / relative_path
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")
    return fixture_path.read_text(encoding="utf-8")


def load_markdown(filename: str) -> str:
    """Load a markdown fixture file.

    Args:
        filename: Name of file in fixtures/markdown/ directory

    Returns:
        Markdown content as string
    """
    return load_fixture(f"markdown/{filename}")


def load_html(filename: str) -> str:
    """Load an HTML fixture file.

    Args:
        filename: Name of file in fixtures/html/ directory

    Returns:
        HTML content as string
    """
    return load_fixture(f"html/{filename}")


def load_json(filename: str) -> str:
    """Load a JSON fixture file.

    Args:
        filename: Name of file in fixtures/json/ directory

    Returns:
        JSON content as string (not parsed)
    """
    return load_fixture(f"json/{filename}")


def list_fixtures(subdir: str = "") -> list[str]:
    """List available fixture files.

    Args:
        subdir: Optional subdirectory to list (e.g., "markdown")

    Returns:
        List of fixture file paths relative to fixtures directory
    """
    search_dir = FIXTURES_DIR / subdir if subdir else FIXTURES_DIR
    fixtures = []
    for path in search_dir.rglob("*"):
        if path.is_file() and not path.name.startswith("__"):
            fixtures.append(str(path.relative_to(FIXTURES_DIR)))
    return sorted(fixtures)


# Export fixture paths for direct access
SAMPLE_CONTENT_MD = FIXTURES_DIR / "markdown" / "sample_content.md"
SAMPLE_SUMMARY_MD = FIXTURES_DIR / "markdown" / "sample_summary.md"
SAMPLE_DIGEST_MD = FIXTURES_DIR / "markdown" / "sample_digest.md"
SAMPLE_NEWSLETTER_HTML = FIXTURES_DIR / "html" / "sample_newsletter.html"
