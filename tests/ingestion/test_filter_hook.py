"""Unit tests for the ingestion filter hook.

These tests exercise the stats/accumulation and enable/disable flow without
touching a real database. The query path is mocked through a fake Session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pytest

from src.ingestion import filter_hook
from src.ingestion.filter_hook import FilterStats, apply_filter_to_recent
from src.services.ingestion_filter import FilterDecision, FilterTier


@dataclass
class _FakeContent:
    id: int = 1
    status: str = "pending"
    filter_decision: Any = None
    ingested_at: datetime = datetime(2026, 4, 19)


class _FakeQuery:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def filter(self, *_args: Any, **_kwargs: Any) -> "_FakeQuery":
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.committed = 0

    def query(self, _model: Any) -> _FakeQuery:
        return _FakeQuery(self._rows)

    def commit(self) -> None:
        self.committed += 1


class _StubService:
    """Drop-in replacement for IngestionFilterService.filter()."""

    def __init__(self, decision: FilterDecision) -> None:
        self._decision = decision
        self.calls: list[int] = []

    def filter(self, content_id: int, *, dry_run: bool = False) -> FilterDecision:
        self.calls.append(content_id)
        return self._decision


def test_filter_stats_records_keep_and_skip() -> None:
    stats = FilterStats()
    stats.record(
        FilterDecision(
            decision="keep", score=0.8, tier=FilterTier.EMBEDDING,
            reason="r", priority_bucket="high",
        )
    )
    stats.record(
        FilterDecision(
            decision="skip", score=0.1, tier=FilterTier.HEURISTIC,
            reason="r", priority_bucket=None,
        )
    )
    out = stats.as_dict()
    assert out["kept"] == 1
    assert out["skipped"] == 1
    assert out["evaluated"] == 2
    assert out["by_tier"]["embedding"] == 1
    assert out["by_tier"]["heuristic"] == 1


def test_run_with_disabled_config_returns_zero_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config.filter_config import FilterConfig

    monkeypatch.setattr(
        filter_hook,
        "_load_persona_config",
        lambda _pid: FilterConfig(enabled=False),
    )
    # We shouldn't even try to open a DB when disabled — pass a dummy one.
    stats = apply_filter_to_recent(
        since=datetime(2026, 4, 19), persona_id="default", db=_FakeSession(rows=[])
    )
    assert stats.evaluated == 0
    assert stats.kept == 0


def test_run_iterates_candidates_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config.filter_config import FilterConfig

    monkeypatch.setattr(
        filter_hook,
        "_load_persona_config",
        lambda _pid: FilterConfig(enabled=True, interest_description="x"),
    )

    stub = _StubService(
        FilterDecision(
            decision="keep", score=0.9, tier=FilterTier.EMBEDDING,
            reason="ok", priority_bucket="high",
        )
    )
    monkeypatch.setattr(
        filter_hook, "IngestionFilterService", lambda *_a, **_kw: stub
    )

    rows = [_FakeContent(id=1), _FakeContent(id=2), _FakeContent(id=3)]
    session = _FakeSession(rows=rows)
    stats = apply_filter_to_recent(
        since=datetime(2026, 4, 19), persona_id="default", db=session
    )
    assert stats.evaluated == 3
    assert stats.kept == 3
    assert session.committed == 1
    assert stub.calls == [1, 2, 3]


def test_run_dry_run_does_not_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config.filter_config import FilterConfig

    monkeypatch.setattr(
        filter_hook,
        "_load_persona_config",
        lambda _pid: FilterConfig(enabled=True, interest_description="x"),
    )
    stub = _StubService(
        FilterDecision(
            decision="skip", score=0.1, tier=FilterTier.HEURISTIC,
            reason="noise", priority_bucket=None,
        )
    )
    monkeypatch.setattr(
        filter_hook, "IngestionFilterService", lambda *_a, **_kw: stub
    )
    session = _FakeSession(rows=[_FakeContent(id=1)])
    apply_filter_to_recent(
        since=datetime(2026, 4, 19), persona_id="default", db=session, dry_run=True
    )
    assert session.committed == 0
