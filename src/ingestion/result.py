"""Canonical ingestion response envelope.

Used by all `aca ingest *` commands and the corresponding HTTP / MCP
endpoints to produce a consistent JSON response shape across transports.

This is distinct from the RSS-internal ``IngestionResult`` dataclass in
``src.ingestion.rss``, which tracks per-source fetch outcomes for the
orchestrator's ``on_result`` callback. The two may be unified in a
follow-up; for now ``IngestionResponse`` is the user-facing envelope and
``IngestionResult`` stays orchestrator-internal.

Design notes
------------
- ``model_config = ConfigDict(extra="forbid")`` — when consumers (HTTP
  client, MCP wrapper, contract tests) call ``IngestionResponse.model_validate``,
  unknown fields raise. This makes "the API silently returned a new field"
  detectable, which is the main lever for cross-transport schema drift.
- ``status`` is the primary success/failure signal (vs. a separate
  ``success: bool``). Three values express partial-failure cleanly:
  ``ok`` — every source fetched and persisted successfully
  ``partial`` — some sources failed, but at least one item was ingested
  ``error`` — nothing landed; the run aborted or every source failed
- ``details`` is the per-command escape hatch for command-specific extras
  (e.g. citations from xsearch, redirected_to URLs from rss). Keeping these
  in ``details`` rather than at the top level preserves the harmonized
  envelope while letting commands carry source-specific signal.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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

    command: str
    """Fully-qualified command identifier, e.g. ``ingest.gmail``."""

    source: str
    """Source identifier — typically matches the subcommand, but may differ
    (e.g. ``perplexity-search`` subcommand emits ``source: "perplexity"``)."""

    status: IngestionStatus

    items_ingested: int = 0
    items_skipped: int = 0
    items_failed: int = 0

    duration_ms: int | None = None
    """Wall-clock duration in milliseconds, or None if not measured."""

    errors: list[IngestionError] = Field(default_factory=list)
    warnings: list[IngestionWarning] = Field(default_factory=list)

    details: dict[str, Any] = Field(default_factory=dict)
    """Command-specific extras (e.g. citations, redirected_to URLs).
    Kept off the top-level envelope to preserve cross-command harmonization."""
