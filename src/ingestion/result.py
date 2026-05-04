"""Canonical ingestion response envelope.

Used by all `aca ingest *` commands and the corresponding HTTP / MCP
endpoints to produce a consistent JSON response shape across transports.

This is distinct from the per-source orchestrator outcome dataclasses
(``RSSFetchOutcome``, ``BlogFetchOutcome``, ``HFPapersFetchOutcome``)
which are internal to ``on_result`` callbacks during ingestion.

Design notes
------------
- ``model_config = ConfigDict(extra="ignore")`` — Postel's law for
  forward compatibility: emitters write the full envelope; consumers
  ignore unknown fields. Drift detection is opt-in via the strict
  fixture ``IngestionResponse.model_validate_strict`` (see below) used
  in cross-transport contract tests. Without ``extra="ignore"`` the
  ``success`` computed field would prevent ``model_dump → model_validate``
  round-trips, breaking the very testing pattern the envelope exists to
  support.

- ``status`` is the canonical success/failure signal. ``success`` is
  exposed as a ``@computed_field`` derived from ``status != "error"``
  for backward compatibility with consumers keying on the boolean.
  Removal planned for ``schema_version`` 2.

- ``items_ingested`` / ``items_skipped`` / ``items_failed`` are mutually
  exclusive categories. Their sum equals the total items the orchestrator
  *attempted* to process. ``_validate_status_invariants`` enforces:
    - ``status="ok"`` ⇒ ``errors == []`` AND ``items_failed == 0``
    - ``status="error"`` ⇒ ``items_ingested == 0`` AND ``len(errors) > 0``
    - ``status="partial"`` ⇒ ``items_ingested > 0`` AND ``len(errors) > 0``

  Categorization policy:
    - ``items_ingested``: items successfully persisted to the DB.
    - ``items_skipped``: items intentionally not persisted — deduplicated,
      filtered out, paywalled without auth, blocked by robots.txt.
    - ``items_failed``: items that errored mid-processing — parse failure,
      LLM call failure, persistence error. Each typically warrants a
      corresponding ``IngestionError`` entry pointing at the offending URL.
    - Source-level failures (a feed returned HTTP 5xx, OAuth expired,
      RSS XML malformed before any item parse) belong in ``errors`` with
      no ``items_failed`` increment — there were no items to fail.

  KNOWN GAP (tracked for service-by-service migration): the three currently
  envelope-returning services (rss, blog, huggingface_papers) do not yet
  track per-item failures. They surface source-level errors via
  ``build_response_from_source_results`` but report ``items_failed=0``
  even when individual items inside a successfully-fetched source failed
  to parse. Closing this gap requires per-service instrumentation and is
  out of scope for the harmonization PR.

- ``schema_version`` is a MAJOR version integer. Minor / additive field
  additions do NOT bump it (consumers ignore unknown fields). Bump only
  on breaking changes (renamed fields, removed fields, semantic changes
  to existing fields). Currently 1; planned bump to 2 when ``success``
  computed field is removed.

- ``details`` is the per-command escape hatch for command-specific extras.
  Reserved key names (every command MUST use these names if it carries
  the corresponding signal):
    - ``citations`` — list of citation/source URLs (xsearch, perplexity)
    - ``query_echo`` — string of the resolved search query (xsearch, perplexity)
    - ``dry_run`` — bool flag (scholar-refs --dry-run mode)
    - ``papers_ingested`` — int subset of items_ingested counted as papers (scholar-refs)
  Per-command typed sub-models may follow in a later PR; reserving the
  names now prevents 11 commands from inventing 11 different keys for
  the same concept. Source-level redirects/failures should use top-level
  ``warnings`` / ``errors`` rather than ``details``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

IngestionStatus = Literal["ok", "partial", "error"]

# Closed registry of canonical ``command`` values. New transports/services
# adding an ingest path MUST add their identifier here so cross-transport
# contract tests can assert agreement. Subcommand naming uses hyphen-case;
# command identifier is always ``ingest.<subcommand>``.
IngestionCommandLiteral = Literal[
    "ingest.gmail",
    "ingest.rss",
    "ingest.blog",
    "ingest.substack",
    "ingest.youtube",
    "ingest.youtube-rss",
    "ingest.youtube-playlist",
    "ingest.podcast",
    "ingest.xsearch",
    "ingest.perplexity-search",
    "ingest.huggingface-papers",
    "ingest.scholar",
    "ingest.scholar-refs",
    "ingest.arxiv",
    "ingest.arxiv-paper",
    "ingest.files",
    "ingest.url",
]

# Closed registry of canonical ``source`` identifiers. Note the two
# inconsistencies the ingestion subsystem inherited from history and which
# this Literal codifies (rather than silently letting them drift further):
#   - ``perplexity-search`` subcommand emits ``source: "perplexity"``
#   - Multi-word sources use ``snake_case`` (``huggingface_papers``,
#     ``arxiv_paper``) while compound subcommands keep ``hyphen-case``
#     (``scholar-refs``, ``youtube-rss``)
IngestionSourceLiteral = Literal[
    "gmail",
    "rss",
    "blog",
    "substack",
    "youtube",
    "youtube-rss",
    "youtube-playlist",
    "podcast",
    "xsearch",
    "perplexity",
    "huggingface_papers",
    "scholar",
    "scholar-refs",
    "arxiv",
    "arxiv_paper",
    "files",
    "url",
]


class IngestionError(BaseModel):
    """Structured error entry on the response envelope."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    url: str | None = None


class IngestionWarning(BaseModel):
    """Structured warning entry — non-fatal signal (redirects, deprecations, quota)."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    url: str | None = None
    redirected_to: str | None = None


class IngestionResponse(BaseModel):
    """Canonical envelope for ingest command responses (CLI / HTTP / MCP)."""

    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    """Major version. Additive field changes do not bump this; consumers
    ignore unknown fields. Bump only on breaking changes."""

    command: IngestionCommandLiteral
    """Fully-qualified command identifier, e.g. ``ingest.gmail``. Closed
    registry — see ``IngestionCommandLiteral``. New commands must register."""

    source: IngestionSourceLiteral
    """Source identifier — typically matches the subcommand, but may differ
    (e.g. ``perplexity-search`` subcommand emits ``source: "perplexity"``).
    Closed registry — see ``IngestionSourceLiteral``."""

    status: IngestionStatus

    items_ingested: int = 0
    """Items successfully persisted. Mutually exclusive with skipped/failed."""

    items_skipped: int = 0
    """Items deduplicated, filtered out, or otherwise not persisted by design.
    Mutually exclusive with ingested/failed."""

    items_failed: int = 0
    """Items that errored during processing. Mutually exclusive with
    ingested/skipped. Note: source-level failures (e.g. a feed that 500'd
    before any items could be parsed) belong in ``errors``, not here."""

    duration_ms: int | None = None
    """Wall-clock duration in milliseconds, or None if not measured.
    For CLI direct mode: orchestrator runtime. For HTTP mode: end-to-end
    request including queueing. Consumers needing finer-grained timing
    should query Langfuse via ``trace_id``."""

    started_at: datetime | None = None
    """When the command began executing, in UTC. Combined with ``duration_ms``,
    enables timeline plotting and Langfuse correlation."""

    trace_id: str | None = None
    """Langfuse / OTel trace ID for correlating this command with backend
    observability. Populated by the CLI from env / generated UUID; HTTP
    transport reads from the ``traceparent`` request header."""

    errors: list[IngestionError] = Field(default_factory=list)
    warnings: list[IngestionWarning] = Field(default_factory=list)

    details: dict[str, Any] = Field(default_factory=dict)
    """Command-specific extras. See module docstring for reserved key names."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success(self) -> bool:
        """Backward-compatibility boolean derived from ``status``.

        Consumers should prefer ``status`` (three-state) for richer signal.
        Retained for one major version to ease migration of downstream
        consumers (web UI, agentic-assistant); planned for removal when
        ``schema_version`` bumps to 2.
        """
        # TODO(schema_v2): remove this computed field; bump schema_version=2
        return self.status != "error"

    @model_validator(mode="after")
    def _validate_status_invariants(self) -> Self:
        """Enforce status / items / errors consistency per docstring contract."""
        if self.status == "ok":
            if self.errors:
                raise ValueError(
                    "status='ok' incompatible with non-empty errors; "
                    "use 'partial' if some items succeeded, 'error' if none did"
                )
            if self.items_failed > 0:
                raise ValueError(
                    "status='ok' incompatible with items_failed > 0; "
                    "use 'partial' if some items succeeded despite failures"
                )
        elif self.status == "error":
            if self.items_ingested > 0:
                raise ValueError(
                    "status='error' requires items_ingested == 0; "
                    "use 'partial' when some items landed despite errors"
                )
            if not self.errors:
                raise ValueError(
                    "status='error' requires non-empty errors; "
                    "consumers need at least one diagnostic entry"
                )
        elif self.status == "partial":
            if self.items_ingested == 0:
                raise ValueError(
                    "status='partial' requires items_ingested > 0; "
                    "use 'error' when nothing was persisted"
                )
            if not self.errors:
                raise ValueError(
                    "status='partial' requires non-empty errors; use 'ok' when no failures occurred"
                )
        return self

    def with_timing(self, *, duration_ms: int, started_at: datetime) -> Self:
        """Return a copy with transport-side timing fields populated, re-validated.

        Use this at transport boundaries (CLI direct mode, HTTP handler, MCP
        tool wrapper) to augment a service-built envelope with wall-clock
        timing measured at the transport. Unlike raw ``model_copy(update=...)``
        which skips validators by design, ``with_timing`` re-runs the full
        validator chain so future schema changes that introduce timing-aware
        invariants (e.g. "duration_ms > 0 if status='ok'") cannot be silently
        bypassed.

        Today the validator does not depend on either field, so the cost is
        a small Pydantic round-trip; the value is forward compatibility.
        """
        return self.model_validate(
            {**self.model_dump(), "duration_ms": duration_ms, "started_at": started_at}
        )

    @classmethod
    def model_validate_strict(cls, payload: dict[str, Any]) -> Self:
        """Strict validation for cross-transport drift detection.

        Unlike ``model_validate``, this rejects unknown top-level fields.
        Use in contract tests that assert the envelope is exactly the
        documented shape (no transport has silently added a field).
        """
        unknown = set(payload.keys()) - set(cls.model_fields.keys()) - {"success"}
        if unknown:
            raise ValueError(
                f"Unknown fields in IngestionResponse payload: {sorted(unknown)}. "
                f"Either add them to the model or remove from the emitter."
            )
        return cls.model_validate(payload)


def build_response_from_source_results(
    *,
    command: IngestionCommandLiteral,
    source: IngestionSourceLiteral,
    items_ingested: int,
    source_results: list[Any],
) -> IngestionResponse:
    """Construct an IngestionResponse from an ingestion service's per-source diagnostics.

    Shared helper for ingestion services (RSS, blog, HuggingFace papers, etc.)
    to convert their internal ``SourceFetchResult`` accumulator into the
    canonical envelope. Source-level failures map to ``errors``, redirects
    map to ``warnings`` with code ``feed_redirected``, and ``status`` is
    derived from the items_ingested vs. error count.

    Each ``source_results`` entry is duck-typed: it must have ``url``, ``success``,
    and (for failures) ``error`` / ``error_type``. RSS-style sources also
    expose ``redirected_to``; non-RSS sources may omit it.
    """
    errors: list[IngestionError] = []
    warnings: list[IngestionWarning] = []

    for r in source_results:
        if not getattr(r, "success", True):
            errors.append(
                IngestionError(
                    code=getattr(r, "error_type", None) or "fetch_error",
                    message=getattr(r, "error", None) or "unknown fetch error",
                    url=getattr(r, "url", None),
                )
            )
        redirected_to = getattr(r, "redirected_to", None)
        if redirected_to:
            warnings.append(
                IngestionWarning(
                    code="feed_redirected",
                    message=f"Source redirected to {redirected_to}",
                    url=getattr(r, "url", None),
                    redirected_to=redirected_to,
                )
            )

    if not errors:
        status: IngestionStatus = "ok"
    elif items_ingested > 0:
        status = "partial"
    else:
        status = "error"

    return IngestionResponse(
        command=command,
        source=source,
        status=status,
        items_ingested=items_ingested,
        errors=errors,
        warnings=warnings,
    )
