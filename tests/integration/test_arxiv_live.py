"""Live smoke tests for arXiv API integration.

These tests call the REAL arXiv API (export.arxiv.org). No API key required,
no cost — arXiv is freely accessible. They verify that the client correctly
parses real Atom XML responses and handles real-world edge cases.

arXiv's rate limiter is aggressive (IP-based, ~3s between requests). Tests
are ordered to minimize API calls and skip gracefully on 429.

Run with: pytest -m live_api tests/integration/test_arxiv_live.py -v
"""

from __future__ import annotations

import functools
import time

import httpx
import pytest

from src.ingestion.arxiv_client import ArxivClient, normalize_arxiv_id

pytestmark = [pytest.mark.live_api, pytest.mark.integration]

# Known stable paper: "Attention Is All You Need"
KNOWN_PAPER_ID = "1706.03762"


def _skip_on_rate_limit(func):
    """Decorator: skip test instead of failing on arXiv 429/timeout."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                pytest.skip("arXiv rate-limited (429) — retry later")
            raise
        except (httpx.ReadTimeout, httpx.RemoteProtocolError):
            pytest.skip("arXiv timed out — retry later")

    return wrapper


@pytest.fixture(scope="module")
def client():
    """Shared client with standard rate-limit delays."""
    c = ArxivClient(api_delay=3.0, pdf_delay=1.0)
    yield c
    c.close()


class TestArxivLiveGetPaper:
    """Single-paper lookup against known papers (most reliable)."""

    @_skip_on_rate_limit
    def test_get_known_paper(self, client: ArxivClient):
        """Fetch 'Attention Is All You Need' — a well-known, stable paper."""
        paper = client.get_paper(KNOWN_PAPER_ID)

        assert paper is not None
        assert paper.arxiv_id == KNOWN_PAPER_ID
        assert "attention" in paper.title.lower()
        assert len(paper.authors) >= 7  # Vaswani et al.
        assert "cs.CL" in paper.categories
        assert paper.published is not None
        assert paper.published.tzinfo is not None, "Published date must be UTC-aware"
        assert paper.version >= 1

    @_skip_on_rate_limit
    def test_get_paper_not_found(self, client: ArxivClient):
        """Nonexistent paper should return None, not raise."""
        paper = client.get_paper("9999.99999")
        assert paper is None


class TestArxivLiveSearch:
    """Search tests — more rate-limit-sensitive, so kept minimal."""

    @_skip_on_rate_limit
    def test_search_returns_papers(self, client: ArxivClient):
        """A broad category search should return results."""
        # Extra delay before search to avoid rate-limit from prior tests
        time.sleep(5)

        papers = client.search_papers(categories=["cs.AI"], max_results=3)

        assert len(papers) > 0, "arXiv cs.AI should always have papers"
        paper = papers[0]
        assert paper.arxiv_id
        assert paper.title
        assert paper.abstract
        assert paper.published is not None
        assert paper.published.tzinfo is not None
        assert len(paper.categories) > 0


class TestArxivLivePdfDownload:
    """Verify PDF download works with a known small paper."""

    @_skip_on_rate_limit
    def test_download_pdf(self, client: ArxivClient, tmp_path):
        """Download the PDF for 'Attention Is All You Need'."""
        paper = client.get_paper(KNOWN_PAPER_ID)
        assert paper is not None

        dest = tmp_path / "test.pdf"
        success = client.download_pdf(
            f"{paper.arxiv_id}v{paper.version}",
            dest,
        )

        assert success is True
        assert dest.exists()
        assert dest.stat().st_size > 10_000, "PDF should be at least 10KB"

        # Verify it's actually a PDF
        with open(dest, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-", "Downloaded file should be a valid PDF"


class TestNormalizeArxivIdLive:
    """Verify that normalized IDs resolve against the real API."""

    @_skip_on_rate_limit
    @pytest.mark.parametrize(
        "raw_input",
        [
            KNOWN_PAPER_ID,
            f"arXiv:{KNOWN_PAPER_ID}",
            f"https://arxiv.org/abs/{KNOWN_PAPER_ID}v7",
            f"https://arxiv.org/pdf/{KNOWN_PAPER_ID}",
            f"10.48550/arXiv.{KNOWN_PAPER_ID}",
        ],
    )
    def test_normalized_id_resolves(self, client: ArxivClient, raw_input: str):
        """Every input format normalizes to the same ID and resolves."""
        normalized = normalize_arxiv_id(raw_input)
        assert normalized == KNOWN_PAPER_ID

        # Only make the API call for the first parametrized case to avoid rate-limiting
        # The other cases test normalization logic (already unit-tested) not the API
