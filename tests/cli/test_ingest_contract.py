"""CLI ingest contract tests — bucket A coverage.

Asserts the JSON output contract of every `aca ingest *` command. Mocks at
`src.ingestion.orchestrator.<func>` (post-PR-#147 pattern); does NOT exercise
real HTTP fetching, real DB writes, or real LLM calls — that belongs in the
integration tier (Hoverfly + test DB) tracked separately.

Canonical envelope (target post-harmonization PR #2)
----------------------------------------------------
- `source`: string identifier matching the subcommand name where possible
- `items_ingested`: integer count (canonical name; deviations xfailed below)

What this catches
-----------------
- CLI registration regressions (a command stops being callable)
- JSON output shape regressions (a field is renamed or dropped)
- Source identifier drift (e.g. `huggingface_papers` underscore vs hyphen)
- Exit code regressions (errors silently report exit 0)
- Cross-command schema inconsistencies (deviating count field names)

What this does NOT catch
------------------------
- Silent fetch failures inside the orchestrator (real HTTP returns empty,
  CLI reports `items_ingested: 0` with exit 0). See the skipped placeholder
  `test_ingest_actually_writes_to_db` at the bottom of this file.

Extending coverage
------------------
To add a command, append a `pytest.param(...)` entry to `INGEST_CASES`. The
LLM that extends this should consult `src/cli/ingest_commands.py` for the
exact `output_result(...)` payload shape — `source` value, `count_field`
name — and `src/ingestion/orchestrator.py` for the function name.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()

# Canonical name for the count field post-harmonization. Chosen over `ingested`
# because it's unambiguous (vs. boolean reading) and already used by the
# academic-source commands.
CANONICAL_COUNT_FIELD = "items_ingested"


# Orchestrator functions migrated to return IngestionResponse (commit 4ee2c7f).
# Mocks for these MUST mimic the real return type — returning int from the mock
# masks production bugs where the consumer treats a Pydantic model as if it were
# an int. Pre-fix, _blog_direct silently emitted JSON like
# {"ingested": "<IngestionResponse object>"} in production but the contract test
# stayed green because the mock returned 7 (int).
MIGRATED_ORCHESTRATOR_META = {
    "ingest_rss": ("ingest.rss", "rss"),
    "ingest_blog": ("ingest.blog", "blog"),
    "ingest_huggingface_papers": ("ingest.huggingface-papers", "huggingface_papers"),
    "ingest_substack": ("ingest.substack", "substack"),
    "ingest_xsearch": ("ingest.xsearch", "xsearch"),
    "ingest_perplexity_search": ("ingest.perplexity-search", "perplexity"),
    "ingest_youtube": ("ingest.youtube", "youtube"),
    "ingest_youtube_rss": ("ingest.youtube-rss", "youtube-rss"),
    "ingest_youtube_playlist": ("ingest.youtube-playlist", "youtube-playlist"),
    "ingest_podcast": ("ingest.podcast", "podcast"),
}


def _mock_orchestrator_return(orch_func: str, count: int) -> Any:
    """Build the mock return value matching the orchestrator's real return type.

    For migrated functions returns an IngestionResponse with the requested
    item count; for legacy functions returns the bare int.
    """
    if orch_func not in MIGRATED_ORCHESTRATOR_META:
        return count
    from src.ingestion.result import IngestionResponse

    command, source = MIGRATED_ORCHESTRATOR_META[orch_func]
    return IngestionResponse(
        command=command,
        source=source,
        status="ok",
        items_ingested=count,
    )


# (cli_subcommand, orchestrator_func, expected_source, count_field, extra_args)
#
# `expected_source` is asserted explicitly because the CLI today has at least
# one case where source identifier differs from the subcommand name:
#   - perplexity-search subcommand → source: "perplexity"
#   - huggingface-papers subcommand → source: "huggingface_papers" (underscore)
#
# `count_field` records the CURRENT shape per command. The consistency test
# below uses xfail markers to track which commands deviate from canonical.
INGEST_CASES = [
    pytest.param("gmail", "ingest_gmail", "gmail", "items_ingested", [], id="gmail"),
    pytest.param("rss", "ingest_rss", "rss", "items_ingested", [], id="rss"),
    pytest.param("blog", "ingest_blog", "blog", "items_ingested", [], id="blog"),
    pytest.param("substack", "ingest_substack", "substack", "items_ingested", [], id="substack"),
    pytest.param("youtube", "ingest_youtube", "youtube", "items_ingested", [], id="youtube"),
    pytest.param(
        "youtube-rss",
        "ingest_youtube_rss",
        "youtube-rss",
        "items_ingested",
        [],
        id="youtube-rss",
    ),
    pytest.param(
        "youtube-playlist",
        "ingest_youtube_playlist",
        "youtube-playlist",
        "items_ingested",
        [],
        id="youtube-playlist",
    ),
    pytest.param("podcast", "ingest_podcast", "podcast", "items_ingested", [], id="podcast"),
    pytest.param("xsearch", "ingest_xsearch", "xsearch", "items_ingested", [], id="xsearch"),
    pytest.param(
        "perplexity-search",
        "ingest_perplexity_search",
        "perplexity",
        "items_ingested",
        [],
        id="perplexity-search",
    ),
    pytest.param(
        "huggingface-papers",
        "ingest_huggingface_papers",
        "huggingface_papers",
        "items_ingested",
        [],
        id="huggingface-papers",
    ),
    pytest.param("scholar", "ingest_scholar", "scholar", "items_ingested", [], id="scholar"),
    pytest.param(
        "scholar-refs",
        "ingest_scholar_refs",
        "scholar-refs",
        "papers_ingested",
        [],
        id="scholar-refs",
    ),
    pytest.param("arxiv", "ingest_arxiv", "arxiv", "items_ingested", [], id="arxiv"),
]


# Same parameter set, but xfail-marked for commands whose count field deviates
# from `CANONICAL_COUNT_FIELD`. When the harmonization PR (#2) lands, removing
# these markers should produce passing tests; if a command unexpectedly
# conforms (xpass), pytest flags it as a failure under strict=True so we know
# to drop the marker.
def _build_consistency_cases() -> list:
    cases = []
    for case in INGEST_CASES:
        # case.values is a tuple of the raw param values
        subcommand, orch_func, _expected_source, count_field, _ = case.values
        kwargs = {"id": case.id}
        if count_field != CANONICAL_COUNT_FIELD:
            kwargs["marks"] = pytest.mark.xfail(
                reason=(
                    f"emits `{count_field}` instead of canonical `{CANONICAL_COUNT_FIELD}` "
                    f"— fix in CLI JSON harmonization PR"
                ),
                strict=True,
            )
        cases.append(pytest.param(subcommand, orch_func, **kwargs))
    return cases


CONSISTENCY_CASES = _build_consistency_cases()


@pytest.mark.parametrize(
    "subcommand,orch_func,expected_source,count_field,extra_args", INGEST_CASES
)
def test_ingest_command_json_contract(
    subcommand, orch_func, expected_source, count_field, extra_args
):
    """Every ingest command must emit valid JSON with source + count fields."""
    with patch(f"src.ingestion.orchestrator.{orch_func}") as mock:
        mock.return_value = _mock_orchestrator_return(orch_func, 7)
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

    assert payload.get("source") == expected_source, (
        f"`{subcommand}` source mismatch: expected {expected_source!r}, "
        f"got {payload.get('source')!r}. Full payload: {payload}"
    )
    assert count_field in payload, (
        f"Missing `{count_field}` field in {subcommand} output: {payload}"
    )
    assert payload[count_field] == 7, (
        f"Count mismatch for {subcommand}: expected 7, got {payload[count_field]}"
    )

    # Confirm the patched callable was actually invoked — guards against
    # the test path bypassing the direct-mode codepath we think we're testing.
    assert mock.called, f"Orchestrator function `{orch_func}` was not invoked"


@pytest.mark.parametrize("subcommand,orch_func", CONSISTENCY_CASES)
def test_ingest_commands_use_canonical_count_field(subcommand, orch_func):
    """All ingest commands should expose the count under `items_ingested`.

    Currently xfailed for the 11 commands using `ingested` and the one using
    `papers_ingested`. The harmonization PR migrates them all to the canonical
    name, then removes the xfail markers — `strict=True` ensures any premature
    fix surfaces as XPASS → CI red.
    """
    with patch(f"src.ingestion.orchestrator.{orch_func}") as mock:
        mock.return_value = _mock_orchestrator_return(orch_func, 1)
        result = runner.invoke(app, ["--json", "--direct", "ingest", subcommand])

    payload = json.loads(result.stdout)
    assert CANONICAL_COUNT_FIELD in payload, (
        f"`{subcommand}` uses non-canonical count field. "
        f"Found keys: {sorted(payload.keys())}. Expected: {CANONICAL_COUNT_FIELD!r}."
    )


def test_ingest_gmail_envelope_validates_through_pydantic():
    """gmail --json output must round-trip through IngestionResponse validation.

    Catches schema drift that string-match assertions miss: missing fields,
    type mismatches, computed-field round-trip breakage, or unknown fields
    drifted in. This is the cross-transport contract primitive — when HTTP
    and MCP transports migrate, the same payload-validation pattern asserts
    each transport produces the canonical envelope shape.
    """
    from src.ingestion.result import IngestionResponse

    with patch("src.ingestion.orchestrator.ingest_gmail") as mock:
        mock.return_value = 5
        result = runner.invoke(app, ["--json", "--direct", "ingest", "gmail"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)

    # Loose: round-trip works despite computed `success` field
    response = IngestionResponse.model_validate(payload)
    assert response.command == "ingest.gmail"
    assert response.source == "gmail"
    assert response.status == "ok"
    assert response.items_ingested == 5
    assert response.success is True  # computed from status

    # Strict: no unknown fields drifted in (drift detection layer)
    IngestionResponse.model_validate_strict(payload)


def test_with_timing_preserves_invariants_and_runs_validators():
    """``with_timing`` augments timing fields through the validator chain.

    Unlike ``model_copy(update=...)`` which skips validators, ``with_timing``
    does a full ``model_validate`` round-trip. Asserting the post-augmentation
    response is still a valid IngestionResponse (and that an invariant
    violation in the BASE response would propagate, not be silently kept)
    proves the helper can't be used to bypass status/items invariants.
    """
    from datetime import UTC, datetime as dt

    from src.ingestion.result import IngestionResponse

    base = IngestionResponse(command="ingest.rss", source="rss", status="ok", items_ingested=5)

    augmented = base.with_timing(duration_ms=1234, started_at=dt(2026, 5, 4, tzinfo=UTC))

    assert augmented.duration_ms == 1234
    assert augmented.started_at == dt(2026, 5, 4, tzinfo=UTC)
    assert augmented.items_ingested == 5
    assert augmented.success is True  # computed from status
    # Original instance untouched (immutability via model_validate copy)
    assert base.duration_ms is None


def test_ingest_response_rejects_unregistered_command_or_source():
    """The Literal registry catches drift: an unregistered command/source raises.

    Without this gate, a new transport could silently emit an envelope with
    a typoed source identifier (e.g. ``"hugging_face_papers"``) that string
    matchers would never catch but which would break cross-transport
    aggregation downstream. Proves the closed registry actually closes.
    """
    from pydantic import ValidationError

    from src.ingestion.result import IngestionResponse

    with pytest.raises(ValidationError):
        IngestionResponse(command="ingest.gmail", source="unknown_source", status="ok")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        IngestionResponse(command="ingest.unknown", source="gmail", status="ok")  # type: ignore[arg-type]


def test_ingest_failure_returns_nonzero_exit():
    """Orchestrator exception must surface as exit code 1, not silent success."""
    with patch("src.ingestion.orchestrator.ingest_rss") as mock:
        mock.side_effect = RuntimeError("simulated upstream failure")
        result = runner.invoke(app, ["--json", "--direct", "ingest", "rss"])

    assert result.exit_code == 1, (
        f"Orchestrator raised but CLI exited {result.exit_code} — silent failure!"
    )
    payload = json.loads(result.stdout)
    # New envelope: failures emit status="error" with at least one entry in errors[]
    assert payload.get("status") == "error", (
        f"Failure envelope missing `status: 'error'`: {payload}"
    )
    assert payload.get("errors"), f"Failure envelope missing populated errors: {payload}"


def test_ingest_failure_pins_status_error_envelope():
    """The failure envelope must include `status: 'error'`.

    Tracks the harmonization rollout: each migrated command's failure path
    emits the canonical IngestionResponse envelope which uses ``status: "error"``
    (not the legacy ``success: false`` boolean). Re-pointed in PR #2 to assert
    the chosen contract — the previous version asserted ``success: false`` and
    would have stayed silently xfailed forever once the envelope dropped that
    field.
    """
    with patch("src.ingestion.orchestrator.ingest_rss") as mock:
        mock.side_effect = RuntimeError("simulated upstream failure")
        result = runner.invoke(app, ["--json", "--direct", "ingest", "rss"])

    payload = json.loads(result.stdout)
    assert payload.get("status") == "error", (
        f"Failure envelope missing `status: 'error'`: {payload}"
    )


@pytest.mark.skip(
    reason=(
        "Integration tier placeholder — requires Hoverfly stub + test DB to "
        "catch the silent-failure bug class (orchestrator returns 0, CLI "
        "reports success). Track via coordinator issue when prioritized."
    )
)
def test_ingest_actually_writes_to_db():
    """Pre/post DB row count delta must equal claimed `items_ingested`.

    Required infrastructure (none implemented yet):
      1. Hoverfly simulation serving a deterministic feed on localhost:8500
      2. Test DB engine via `tests.helpers.test_db.create_test_engine()`
      3. A real subprocess invocation of `aca ingest rss` (not CliRunner) so
         the full module load + HTTP path is exercised

    Skeleton:
      pre = engine.execute(SELECT count(*) FROM content_items WHERE ...).scalar()
      result = subprocess.run(["aca", "ingest", "rss", "--json"], ...)
      payload = json.loads(result.stdout)
      post = engine.execute(SELECT count(*) FROM content_items WHERE ...).scalar()
      assert post - pre == payload["items_ingested"], (
          "API claimed success but DB delta doesn't match — silent failure"
      )
    """
