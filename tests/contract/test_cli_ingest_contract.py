"""CLI ingest contract tests — bucket A coverage template.

Asserts the JSON output contract of every `aca ingest *` command. Mocks at
`src.ingestion.orchestrator.<func>` (post-PR-#147 pattern); does NOT exercise
real HTTP fetching, real DB writes, or real LLM calls — that belongs in the
integration tier (Hoverfly + test DB).

What this catches
-----------------
- CLI registration regressions (a command stops being callable)
- JSON output shape regressions (a field is renamed or dropped)
- Exit code regressions (errors silently report exit 0)
- Cross-command schema inconsistencies (e.g. `ingested` vs `items_ingested`)

What this does NOT catch
------------------------
- Silent fetch failures inside the orchestrator (real HTTP returns empty,
  CLI reports `ingested: 0` with exit 0). That requires the integration
  tier — see the docstring at the bottom of this file for the sketch.

Extending coverage
------------------
To add a command, append a `pytest.param(...)` entry to `INGEST_CASES`. The
LLM that extends this should consult `src/cli/ingest_commands.py` to confirm
the orchestrator function name and the count field name.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


# (cli_subcommand, orchestrator_func, count_field, extra_args)
INGEST_CASES = [
    pytest.param("gmail", "ingest_gmail", "ingested", [], id="gmail"),
    pytest.param("rss", "ingest_rss", "ingested", [], id="rss"),
    pytest.param("substack", "ingest_substack", "ingested", [], id="substack"),
    pytest.param("youtube", "ingest_youtube", "ingested", [], id="youtube"),
    pytest.param("youtube-rss", "ingest_youtube_rss", "ingested", [], id="youtube-rss"),
    pytest.param(
        "youtube-playlist",
        "ingest_youtube_playlist",
        "ingested",
        [],
        id="youtube-playlist",
    ),
    pytest.param("podcast", "ingest_podcast", "ingested", [], id="podcast"),
    pytest.param(
        "scholar",
        "ingest_scholar",
        "items_ingested",
        [],
        id="scholar",
    ),
    pytest.param(
        "arxiv",
        "ingest_arxiv",
        "items_ingested",
        [],
        id="arxiv",
    ),
]


# Same set, but with xfail markers on commands whose JSON output schema
# deviates from the canonical `ingested` field name. When the harmonization
# PR lands, removing these markers should produce passing tests; if a
# command unexpectedly conforms (xpass), pytest will flag it as a failure
# under strict=True so we know to drop the marker.
_HARMONIZATION_REASON = (
    "deviates from canonical `ingested` field — fix in CLI JSON harmonization PR"
)
CONSISTENCY_CASES = [
    pytest.param("gmail", "ingest_gmail", id="gmail"),
    pytest.param("rss", "ingest_rss", id="rss"),
    pytest.param("substack", "ingest_substack", id="substack"),
    pytest.param("youtube", "ingest_youtube", id="youtube"),
    pytest.param("youtube-rss", "ingest_youtube_rss", id="youtube-rss"),
    pytest.param("youtube-playlist", "ingest_youtube_playlist", id="youtube-playlist"),
    pytest.param("podcast", "ingest_podcast", id="podcast"),
    pytest.param(
        "scholar",
        "ingest_scholar",
        marks=pytest.mark.xfail(reason=_HARMONIZATION_REASON, strict=True),
        id="scholar",
    ),
    pytest.param(
        "arxiv",
        "ingest_arxiv",
        marks=pytest.mark.xfail(reason=_HARMONIZATION_REASON, strict=True),
        id="arxiv",
    ),
]


@pytest.mark.parametrize("subcommand,orch_func,count_field,extra_args", INGEST_CASES)
def test_ingest_command_json_contract(subcommand, orch_func, count_field, extra_args):
    """Every ingest command must emit valid JSON with source + count fields."""
    with patch(f"src.ingestion.orchestrator.{orch_func}") as mock:
        mock.return_value = 7
        result = runner.invoke(app, ["--json", "--direct", "ingest", subcommand, *extra_args])

    assert result.exit_code == 0, (
        f"`aca ingest {subcommand}` exited {result.exit_code}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"`aca ingest {subcommand} --json` did not emit valid JSON.\n"
            f"stdout: {result.stdout!r}\nerror: {exc}"
        )

    assert "source" in payload, f"Missing `source` field in {subcommand} output: {payload}"
    assert count_field in payload, (
        f"Missing `{count_field}` field in {subcommand} output: {payload}"
    )
    assert payload[count_field] == 7, (
        f"Count mismatch for {subcommand}: expected 7, got {payload[count_field]}"
    )


@pytest.mark.parametrize("subcommand,orch_func", CONSISTENCY_CASES)
def test_ingest_commands_use_consistent_count_field(subcommand, orch_func):
    """All ingest commands should expose the count under the same JSON key.

    Currently xfailed for `scholar` and `arxiv`, which use `items_ingested`
    instead of the canonical `ingested`. The harmonization PR should pick
    one canonical name (likely `items_ingested`, since it's more explicit)
    and migrate the others, then remove the xfail markers.
    """
    with patch(f"src.ingestion.orchestrator.{orch_func}") as mock:
        mock.return_value = 1
        result = runner.invoke(app, ["--json", "--direct", "ingest", subcommand])

    payload = json.loads(result.stdout)
    assert "ingested" in payload, (
        f"`{subcommand}` uses non-standard count field. "
        f"Found keys: {sorted(payload.keys())}. Expected: 'ingested'."
    )


def test_ingest_failure_returns_nonzero_exit():
    """Orchestrator exception must surface as exit code 1, not silent success."""
    with patch("src.ingestion.orchestrator.ingest_rss") as mock:
        mock.side_effect = RuntimeError("simulated upstream failure")
        result = runner.invoke(app, ["--json", "--direct", "ingest", "rss"])

    assert result.exit_code == 1, (
        f"Orchestrator raised but CLI exited {result.exit_code} — silent failure!"
    )
    payload = json.loads(result.stdout)
    assert payload.get("success") is False or "error" in payload, (
        f"Failure output missing error signal: {payload}"
    )


# ---------------------------------------------------------------------------
# Integration-tier sketch (NOT IMPLEMENTED — for reference)
# ---------------------------------------------------------------------------
#
# The contract test above will not catch the silent-failure bug class. To
# catch "fetch returns empty, CLI reports ingested: 0 with exit 0", the
# integration test needs:
#
#   1. A real test DB (use `create_test_engine` from tests/helpers/test_db.py)
#   2. A Hoverfly-stubbed feed served on localhost (see
#      tests/integration/fixtures/hoverfly.py and PR #200)
#   3. A pre/post DB row count delta assertion against `content_items`
#   4. An assertion that the delta == claimed `ingested` count
#
# Skeleton:
#
#   def test_ingest_rss_actually_writes_rows(test_engine, hoverfly_feed_3_items):
#       pre = test_engine.execute(
#           text("SELECT count(*) FROM content_items WHERE source_id = :s"),
#           {"s": "rss-test-fixture"},
#       ).scalar()
#       result = subprocess.run(
#           ["aca", "ingest", "rss", "--source", "rss-test-fixture", "--json"],
#           capture_output=True, text=True, check=False,
#       )
#       payload = json.loads(result.stdout)
#       post = test_engine.execute(
#           text("SELECT count(*) FROM content_items WHERE source_id = :s"),
#           {"s": "rss-test-fixture"},
#       ).scalar()
#       assert post - pre == payload["ingested"], (
#           "API claimed success but DB delta doesn't match — silent failure"
#       )
#
# That's the test that catches the bug you're seeing in production.
