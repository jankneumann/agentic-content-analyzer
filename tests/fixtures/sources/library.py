"""Network-free commands and content used by the source workflow matrix."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceFixture:
    """One registry command and the canonical content it deterministically emits."""

    command: dict[str, Any]
    title: str


class SourceFixtureRegistryError(RuntimeError):
    """Raised during collection when registry and fixture keys drift."""


def assert_fixture_registry_complete(
    registry_keys: set[str] | frozenset[str], fixture_keys: set[str] | frozenset[str]
) -> None:
    """Fail with actionable missing and extra fixture diagnostics."""

    missing = sorted(registry_keys - fixture_keys)
    extra = sorted(fixture_keys - registry_keys)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        raise SourceFixtureRegistryError(
            "Source fixture registry does not match executable registry: " + ", ".join(details)
        )


SOURCE_FIXTURES: dict[str, SourceFixture] = {
    "gmail": SourceFixture(
        command={"kind": "gmail", "query": "label:ai", "max_items": 2},
        title="Gmail agent update",
    ),
    "rss": SourceFixture(
        command={"kind": "rss", "max_items": 2},
        title="RSS agent update",
    ),
    "blog": SourceFixture(
        command={"kind": "blog", "max_items": 2},
        title="Blog agent update",
    ),
    "substack": SourceFixture(
        command={"kind": "substack", "max_items": 2},
        title="Substack agent update",
    ),
    "youtube_playlist": SourceFixture(
        command={"kind": "youtube_playlist", "max_items": 2, "public_only": True},
        title="YouTube playlist agent update",
    ),
    "youtube_rss": SourceFixture(
        command={"kind": "youtube_rss", "max_items": 2},
        title="YouTube RSS agent update",
    ),
    "podcast": SourceFixture(
        command={"kind": "podcast", "max_items": 2, "transcribe": True},
        title="Podcast agent update",
    ),
    "x_search": SourceFixture(
        command={"kind": "x_search", "prompt": "agent evaluation", "max_threads": 2},
        title="X search agent update",
    ),
    "perplexity_search": SourceFixture(
        command={
            "kind": "perplexity_search",
            "prompt": "agent evaluation",
            "max_items": 2,
        },
        title="Perplexity agent update",
    ),
    "files": SourceFixture(
        command={"kind": "files", "upload_ids": ["00000000-0000-4000-8000-000000000001"]},
        title="Uploaded agent report",
    ),
    "url": SourceFixture(
        command={"kind": "url", "url": "https://example.test/agent-update"},
        title="Web agent update",
    ),
    "scholar_search": SourceFixture(
        command={"kind": "scholar_search", "max_items": 2},
        title="Scholar search agent paper",
    ),
    "scholar_paper": SourceFixture(
        command={"kind": "scholar_paper", "identifier": "CorpusId:123"},
        title="Scholar agent paper",
    ),
    "scholar_references": SourceFixture(
        command={"kind": "scholar_references", "limit": 2},
        title="Scholar reference graph",
    ),
    "arxiv_search": SourceFixture(
        command={"kind": "arxiv_search", "max_items": 2, "extract_pdf": False},
        title="arXiv search agent paper",
    ),
    "arxiv_paper": SourceFixture(
        command={"kind": "arxiv_paper", "identifier": "2607.00001", "extract_pdf": False},
        title="arXiv agent paper",
    ),
    "huggingface_papers": SourceFixture(
        command={"kind": "huggingface_papers", "max_items": 2},
        title="Hugging Face agent paper",
    ),
    "readwise": SourceFixture(
        command={"kind": "readwise", "max_books": 2},
        title="Readwise agent highlight",
    ),
}


URL_VARIANTS: tuple[tuple[str, dict[str, Any], str, str], ...] = (
    (
        "webpage",
        {"kind": "url", "url": "https://example.test/articles/agents"},
        "webpage",
        "webpage",
    ),
    (
        "youtube_video",
        {"kind": "url", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        "youtube_video",
        "youtube",
    ),
    (
        "youtube_playlist",
        {"kind": "url", "url": "https://www.youtube.com/playlist?list=PL1234567890"},
        "youtube_playlist",
        "youtube",
    ),
    (
        "rss",
        {"kind": "url", "url": "https://example.test/feed.xml"},
        "rss_feed",
        "rss",
    ),
    (
        "forced_webpage",
        {
            "kind": "url",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "routing_mode": "webpage",
        },
        "webpage",
        "webpage",
    ),
)
