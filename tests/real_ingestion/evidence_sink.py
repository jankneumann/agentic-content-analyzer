"""Session-wide evidence collector for the scheduled tier's CI artifact.

Tier tests push each source's :class:`SourceEvidence` here; the conftest session
fixture renders the accumulated classifications to ``REAL_INGEST_EVIDENCE_PATH``
(set by the scheduled workflow) so CI can upload the failure-class summary.
"""

from __future__ import annotations

from pathlib import Path

from src.ingestion.real_ingest_evidence import SourceEvidence, render_failure_summary

COLLECTED: list[SourceEvidence] = []


def record(evidence: SourceEvidence) -> None:
    """Record one source's classified outcome for the run summary."""

    COLLECTED.append(evidence)


def flush_to(path: str) -> None:
    """Write the rendered failure-class summary for every collected source."""

    Path(path).write_text(render_failure_summary(COLLECTED))
