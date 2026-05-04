"""Canonical ingestion response envelope.

Used by all `aca ingest *` commands and the corresponding HTTP / MCP
endpoints to produce a consistent JSON response shape across transports.

This is distinct from ``RSSFetchOutcome`` in ``src.ingestion.rss``, which
is the orchestrator-internal aggregate fed to the ``on_result`` callback
during RSS ingestion.

Design notes
------------
- ``model_config = ConfigDict(extra="forbid")`` — when consumers (HTTP
  client, MCP wrapper, contract tests) call ``IngestionResponse.model_validate``,
  unknown fields raise. This makes "the API silently returned a new field"
  detectable, which is the main lever for cross-transport schema drift.
  Forward compatibility is preserved by ``schema_version``: minor versions
  add fields, consumers MUST relax to ``extra="ignore"`` when reading
  responses with a higher minor than they were built against.

- ``status`` is the primary success/failure signal. ``success`` is exposed
  as a computed field for backward compatibility with consumers that key
  on a boolean — but the canonical signal is ``status``.

- ``items_ingested`` / ``items_skipped`` / ``items_failed`` are mutually
  exclusive categories. Their sum equals the total items the orchestrator
  *attempted* to process. A model_validator enforces:
  - ``status="ok"`` ⇒ no errors, items_failed == 0
  - ``status="error"`` ⇒ items_ingested == 0, errors non-empty
  - ``status="partial"`` ⇒ items_ingested > 0 AND errors non-empty

- ``details`` is the per-command escape hatch for command-specific extras.
  Its contents are NOT contract — consumers must not assume any specific
  keys. Per-command typed schemas may follow in a later PR.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

IngestionStatus = Literal["ok", "partial", "error"]


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

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    """Envelope version. Bump major on breaking changes; minor versions add
    fields. Consumers must read with ``extra="ignore"`` when reading responses
    with a higher minor version than they were built against."""

    command: str
    """Fully-qualified command identifier, e.g. ``ingest.gmail``."""

    source: str
    """Source identifier — typically matches the subcommand, but may differ
    (e.g. ``perplexity-search`` subcommand emits ``source: "perplexity"``)."""

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
    """Command-specific extras (e.g. citations, redirected_to URLs).
    Opaque — not part of the cross-transport contract. Per-command typed
    schemas may follow in a later PR."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success(self) -> bool:
        """Backward-compatibility boolean derived from ``status``.

        Consumers should prefer ``status`` (three-state) for richer signal.
        Retained for one minor version to ease migration of downstream
        consumers (web UI, agentic-assistant); planned for removal in v2.
        """
        return self.status != "error"

    @model_validator(mode="after")
    def _validate_status_invariants(self) -> Self:
        """Enforce status / items / errors consistency."""
        if self.status == "ok" and self.errors:
            raise ValueError(
                "status='ok' incompatible with non-empty errors; "
                "use status='partial' if some items succeeded, 'error' if none did"
            )
        if self.status == "error" and self.items_ingested > 0:
            raise ValueError(
                "status='error' requires items_ingested == 0; "
                "use status='partial' when some items landed despite errors"
            )
        if self.status == "partial" and not (self.errors and self.items_ingested > 0):
            raise ValueError(
                "status='partial' requires both non-empty errors AND items_ingested > 0"
            )
        return self
