"""Retention for the rendered change-graph assets.

The rule worth testing is what the pruner refuses to delete. A retention job
that errs towards deleting is one incident away from removing something a
reviewer still needed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from prune_change_graph_assets import load_closed, main, plan

NOW = datetime(2026, 9, 9, tzinfo=UTC)


def _assets(tmp_path: Path, *numbers: int) -> Path:
    root = tmp_path / "assets"
    for number in numbers:
        (root / str(number) / "abc1234").mkdir(parents=True)
        (root / str(number) / "abc1234" / "view.svg").write_text("<svg/>")
    return root


def _closed(**pairs: int) -> dict[int, datetime]:
    """Map pull request number to a closure that many days before NOW."""
    return {int(number): NOW - timedelta(days=days) for number, days in pairs.items()}


def test_a_long_closed_pull_request_is_a_candidate(tmp_path: Path) -> None:
    root = _assets(tmp_path, 42)

    candidates = plan(root, _closed(**{"42": 200}), now=NOW)

    assert [c.number for c in candidates] == [42]
    assert "200 days ago" in candidates[0].reason


def test_a_recently_closed_pull_request_is_kept(tmp_path: Path) -> None:
    root = _assets(tmp_path, 42)

    assert plan(root, _closed(**{"42": 30}), now=NOW) == []


def test_an_open_pull_request_is_kept(tmp_path: Path) -> None:
    root = _assets(tmp_path, 42)

    assert plan(root, {}, now=NOW) == []


def test_a_pull_request_missing_from_the_listing_is_kept(tmp_path: Path) -> None:
    """Absence is not evidence of closure.

    An incomplete listing -- a truncated page, a failed request -- must never
    read as permission to delete.
    """
    root = _assets(tmp_path, 42, 43)

    candidates = plan(root, _closed(**{"42": 200}), now=NOW)

    assert [c.number for c in candidates] == [42]


def test_candidates_come_back_oldest_first(tmp_path: Path) -> None:
    root = _assets(tmp_path, 1, 2, 3)

    candidates = plan(root, _closed(**{"1": 100, "2": 300, "3": 200}), now=NOW)

    assert [c.number for c in candidates] == [2, 3, 1]


def test_stray_entries_are_ignored(tmp_path: Path) -> None:
    root = _assets(tmp_path, 42)
    (root / "README.md").write_text("not a pull request")
    (root / "scratch").mkdir()

    candidates = plan(root, _closed(**{"42": 200}), now=NOW)

    assert [c.path.name for c in candidates] == ["42"]


def test_a_dry_run_deletes_nothing(tmp_path: Path) -> None:
    root = _assets(tmp_path, 42)
    listing = tmp_path / "closed.json"
    listing.write_text(json.dumps([{"number": 42, "closed_at": "2020-01-01T00:00:00Z"}]))

    assert main(["--root", str(root), "--closed", str(listing)]) == 0
    assert (root / "42").exists()


def test_apply_deletes(tmp_path: Path) -> None:
    root = _assets(tmp_path, 42)
    listing = tmp_path / "closed.json"
    listing.write_text(json.dumps([{"number": 42, "closed_at": "2020-01-01T00:00:00Z"}]))

    assert main(["--root", str(root), "--closed", str(listing), "--apply"]) == 0
    assert not (root / "42").exists()


def test_the_listing_is_read_in_the_shape_the_api_returns(tmp_path: Path) -> None:
    listing = tmp_path / "closed.json"
    listing.write_text(
        json.dumps(
            [
                {"number": 7, "closed_at": "2026-01-02T03:04:05Z"},
                {"number": 8, "closed_at": None},
            ]
        )
    )

    closed = load_closed(listing)

    assert closed[7] == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert 8 not in closed, "an open pull request has no closure to age"
