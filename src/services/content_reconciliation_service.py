"""Bounded, fail-closed reconciliation for operation-owned Content states."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import asyncpg

from src.contracts.workflow_models import (
    ContentReconciliationAction,
    ContentReconciliationContentStatus,
    ContentReconciliationCounts,
    ContentReconciliationItem,
    ContentReconciliationOperationStatus,
    ContentReconciliationPhase,
    ContentReconciliationReason,
    ContentReconciliationReport,
    ContentReconciliationRequest,
)
from src.queue import setup as queue_setup
from src.queue.content_execution_lock import _CONTENT_EXECUTION_LOCK_NAMESPACE
from src.services.operation_service import OperationService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class LockState(StrEnum):
    """Content transaction-lock observation made by the apply path."""

    NOT_CHECKED = "not_checked"
    ACQUIRED = "acquired"
    CONTENDED = "contended"


@dataclass(frozen=True, slots=True)
class CandidateSnapshot:
    """Safe lifecycle evidence consumed by the pure reconciliation classifier."""

    content_id: int
    content_status: ContentReconciliationContentStatus
    owner_operation_id: int | None
    owner_claim_generation: int | None
    owner_phase: ContentReconciliationPhase | None
    owner_version: int | None
    operation_id: int | None
    operation_status: ContentReconciliationOperationStatus | None
    operation_claim_generation: int | None
    operation_claim_protocol_version: int | None
    operation_retry_count: int | None
    operation_cancel_requested: bool
    operation_force: bool
    operation_is_stale: bool
    matching_summary: bool
    mismatched_summary: bool
    extraction_succeeded: bool
    lock_state: LockState
    revalidated: bool


@dataclass(frozen=True, slots=True)
class ReconciliationDecision:
    """Closed proposed lifecycle projection for one candidate."""

    action: ContentReconciliationAction
    reason: ContentReconciliationReason
    content_status_after: ContentReconciliationContentStatus
    operation_status_after: ContentReconciliationOperationStatus | None
    retry_count_after: int | None


class ContentReconciliationClassifier:
    """Classify persisted evidence without performing reads or mutations."""

    CURRENT_CLAIM_PROTOCOL = 2

    def __init__(self, *, max_retries: int) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self._max_retries = max_retries

    def classify(self, candidate: CandidateSnapshot) -> ReconciliationDecision | None:
        if candidate.content_status in {"completed", "filtered_out"}:
            return None

        if candidate.operation_id is None or candidate.operation_status is None:
            return ReconciliationDecision(
                action="none",
                reason="missing_operation",
                content_status_after=candidate.content_status,
                operation_status_after=None,
                retry_count_after=None,
            )

        if not self._has_exact_owner(candidate):
            return self._decision(candidate, reason="ownership_conflict")

        if not candidate.revalidated:
            return self._decision(candidate, reason="revalidation_conflict")

        if candidate.operation_claim_protocol_version != self.CURRENT_CLAIM_PROTOCOL:
            return self._decision(candidate, reason="incompatible_worker")

        if candidate.operation_status == "queued":
            return self._decision(candidate, reason="active_operation")

        if candidate.operation_status == "in_progress":
            return self._classify_in_progress(candidate)

        if candidate.operation_cancel_requested:
            return self._classify_cancelled(candidate, reason="cancellation_requested")

        if candidate.operation_force and candidate.operation_status in {
            "failed",
            "cancelled",
        }:
            return self._decision(candidate, reason="forced_reprocessing")

        output_decision = self._classify_output(candidate)
        if output_decision is not None:
            return output_decision

        if candidate.operation_status == "failed":
            if self._retry_exhausted(candidate):
                return self._decision(candidate, reason="retry_budget_exhausted")
            return self._decision(
                candidate,
                action="retry_operation",
                reason="failed_operation",
                operation_status_after="queued",
                retry_count_after=(candidate.operation_retry_count or 0) + 1,
            )

        if candidate.operation_status == "cancelled":
            return self._classify_cancelled(candidate)

        return self._decision(candidate, reason="completed_output_missing")

    @staticmethod
    def _has_exact_owner(candidate: CandidateSnapshot) -> bool:
        phase_matches_status = (
            candidate.content_status == "failed"
            or candidate.content_status == candidate.owner_phase
        )
        return (
            candidate.owner_operation_id is not None
            and candidate.owner_claim_generation is not None
            and candidate.owner_phase is not None
            and candidate.owner_version is not None
            and candidate.owner_operation_id == candidate.operation_id
            and candidate.owner_claim_generation == candidate.operation_claim_generation
            and phase_matches_status
        )

    def _classify_in_progress(
        self,
        candidate: CandidateSnapshot,
    ) -> ReconciliationDecision:
        if not candidate.operation_is_stale:
            reason: ContentReconciliationReason = (
                "cancellation_pending"
                if candidate.operation_cancel_requested
                else "active_operation"
            )
            return self._decision(candidate, reason=reason)
        if candidate.lock_state is LockState.CONTENDED:
            return self._decision(candidate, reason="execution_locked")
        if candidate.operation_cancel_requested:
            return self._classify_cancelled(candidate, reason="cancellation_requested")
        if candidate.operation_force:
            return self._decision(candidate, reason="forced_reprocessing")
        if self._retry_exhausted(candidate):
            return self._decision(candidate, reason="retry_budget_exhausted")
        return self._decision(
            candidate,
            action="retry_operation",
            reason="stale_operation",
            content_status_after="failed",
            operation_status_after="queued",
            retry_count_after=(candidate.operation_retry_count or 0) + 1,
        )

    @staticmethod
    def _classify_output(
        candidate: CandidateSnapshot,
    ) -> ReconciliationDecision | None:
        if candidate.mismatched_summary and not candidate.matching_summary:
            return ContentReconciliationClassifier._decision(
                candidate,
                reason="output_owner_mismatch",
            )
        if candidate.owner_phase == "processing" and candidate.matching_summary:
            return ContentReconciliationClassifier._decision(
                candidate,
                action="project_completed",
                reason="summary_exists",
                content_status_after="completed",
            )
        if candidate.operation_status == "completed" and candidate.owner_phase == "parsing":
            if candidate.content_status == "parsing" and candidate.extraction_succeeded:
                return ContentReconciliationClassifier._decision(
                    candidate,
                    action="project_parsed",
                    reason="extraction_completed",
                    content_status_after="parsed",
                )
            return ContentReconciliationClassifier._decision(
                candidate,
                reason="completed_output_missing",
            )
        if candidate.operation_status == "completed":
            return ContentReconciliationClassifier._decision(
                candidate,
                reason="completed_output_missing",
            )
        return None

    @staticmethod
    def _classify_cancelled(
        candidate: CandidateSnapshot,
        *,
        reason: ContentReconciliationReason | None = None,
    ) -> ReconciliationDecision:
        if candidate.owner_phase == "processing":
            return ContentReconciliationClassifier._decision(
                candidate,
                action=(
                    "cancel_restore_parsed"
                    if reason == "cancellation_requested"
                    else "restore_parsed"
                ),
                reason=reason or "summarization_cancelled",
                content_status_after="parsed",
                operation_status_after=(
                    "cancelled" if reason == "cancellation_requested" else None
                ),
            )
        return ContentReconciliationClassifier._decision(
            candidate,
            action=(
                "cancel_restore_pending"
                if reason == "cancellation_requested"
                else "restore_pending"
            ),
            reason=reason or "extraction_cancelled",
            content_status_after="pending",
            operation_status_after=("cancelled" if reason == "cancellation_requested" else None),
        )

    def _retry_exhausted(self, candidate: CandidateSnapshot) -> bool:
        return (candidate.operation_retry_count or 0) >= self._max_retries

    @staticmethod
    def _decision(
        candidate: CandidateSnapshot,
        *,
        action: ContentReconciliationAction = "none",
        reason: ContentReconciliationReason,
        content_status_after: ContentReconciliationContentStatus | None = None,
        operation_status_after: ContentReconciliationOperationStatus | None = None,
        retry_count_after: int | None = None,
    ) -> ReconciliationDecision:
        return ReconciliationDecision(
            action=action,
            reason=reason,
            content_status_after=content_status_after or candidate.content_status,
            operation_status_after=(
                candidate.operation_status
                if operation_status_after is None
                else operation_status_after
            ),
            retry_count_after=(
                candidate.operation_retry_count if retry_count_after is None else retry_count_after
            ),
        )


class ContentReconciliationApplyDisabledError(RuntimeError):
    """Raised before any SQL when reconciliation apply is disabled."""


class ContentReconciliationService:
    """Scan one bounded keyset page and optionally apply guarded decisions."""

    def __init__(
        self,
        *,
        connection: asyncpg.Connection,
        stale_seconds: int,
        max_retries: int,
        batch_size: int,
        lock_timeout_ms: int,
        statement_timeout_ms: int,
        apply_enabled: bool,
    ) -> None:
        if stale_seconds <= 0:
            raise ValueError("stale_seconds must be positive")
        if not 1 <= batch_size <= 100:
            raise ValueError("batch_size must be between 1 and 100")
        if lock_timeout_ms <= 0 or statement_timeout_ms < lock_timeout_ms:
            raise ValueError("statement timeout must be at least the positive lock timeout")
        self._connection = connection
        self._stale_seconds = stale_seconds
        self._batch_size = batch_size
        self._lock_timeout_ms = lock_timeout_ms
        self._statement_timeout_ms = statement_timeout_ms
        self._apply_enabled = apply_enabled
        self._classifier = ContentReconciliationClassifier(max_retries=max_retries)

    async def reconcile(
        self,
        request: ContentReconciliationRequest,
        *,
        run_id: UUID | None = None,
    ) -> ContentReconciliationReport:
        """Return a bounded report; reject disabled apply before issuing SQL."""

        if request.apply and not self._apply_enabled:
            raise ContentReconciliationApplyDisabledError(
                "Content reconciliation apply is disabled"
            )
        limit = request.limit or self._batch_size
        if limit > self._batch_size:
            raise ValueError("Requested limit exceeds the configured reconciliation batch size")

        rows = await self._scan(
            after_content_id=request.after_content_id or 0,
            limit=limit,
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        effective_run_id = run_id or uuid4()
        if request.apply:
            items = await self._apply_page(page, run_id=effective_run_id)
        else:
            items = [self._dry_run_item(row) for row in page]
        return ContentReconciliationReport(
            run_id=effective_run_id,
            mode="apply" if request.apply else "dry_run",
            scanned=len(page),
            reported=len(items),
            next_after_content_id=(int(page[-1]["content_id"]) if has_more else None),
            counts=self._counts(items),
            items=items,
        )

    async def _apply_page(
        self,
        rows: list[asyncpg.Record],
        *,
        run_id: UUID,
    ) -> list[ContentReconciliationItem]:
        items: list[ContentReconciliationItem] = []
        for row in rows:
            try:
                async with self._connection.transaction():
                    item = await self._apply_one(row, run_id=run_id)
            except Exception as exc:
                candidate = self._candidate(row)
                logger.warning(
                    "content reconciliation apply_failed",
                    extra={
                        "reconciliation_run_id": str(run_id),
                        "content_id": candidate.content_id,
                        "error_type": type(exc).__name__,
                    },
                )
                failed = ReconciliationDecision(
                    action="none",
                    reason="apply_failed",
                    content_status_after=candidate.content_status,
                    operation_status_after=candidate.operation_status,
                    retry_count_after=candidate.operation_retry_count,
                )
                item = self._item(
                    candidate,
                    failed,
                    row=row,
                    projection="observed",
                    applied=False,
                )
                try:
                    await self._insert_apply_failed_event(
                        run_id=run_id,
                        content_id=candidate.content_id,
                    )
                except Exception:
                    logger.error(
                        "content reconciliation failure intent could not be persisted",
                        extra={"reconciliation_run_id": str(run_id)},
                    )
            items.append(item)
        return items

    async def _insert_apply_failed_event(
        self,
        *,
        run_id: UUID,
        content_id: int,
    ) -> None:
        """Persist bounded post-rollback evidence without exception text or input data."""

        event_key = f"reconciliation-failure:{run_id}:content:{content_id}:reason:apply_failed"
        await self._connection.execute(
            """
            INSERT INTO workflow_terminal_events (
                event_key, source_kind, reconciliation_run_id,
                reconciliation_content_id, occurred_at
            ) VALUES ($1, 'reconciliation_failure', $2, $3, NOW())
            ON CONFLICT (event_key) DO NOTHING
            """,
            event_key,
            run_id,
            content_id,
        )

    async def _apply_one(
        self,
        scanned_row: asyncpg.Record,
        *,
        run_id: UUID,
    ) -> ContentReconciliationItem:
        content_id = int(scanned_row["content_id"])
        operation_id = scanned_row["owner_operation_id"]
        scanned_candidate = self._candidate(scanned_row)
        proposed = self._classifier.classify(scanned_candidate)
        if proposed is None:
            raise RuntimeError("Protected Content unexpectedly reached apply")
        if proposed.action == "none" or operation_id is None:
            return self._item(
                scanned_candidate,
                proposed,
                row=scanned_row,
                projection="observed",
                applied=False,
            )

        await self._connection.execute(
            "SELECT set_config('lock_timeout', $1, true)",
            f"{self._lock_timeout_ms}ms",
        )
        await self._connection.execute(
            "SELECT set_config('statement_timeout', $1, true)",
            f"{self._statement_timeout_ms}ms",
        )
        content_lock = await self._connection.fetchval(
            "SELECT pg_try_advisory_xact_lock($1::integer, $2::integer)",
            _CONTENT_EXECUTION_LOCK_NAMESPACE,
            content_id,
        )
        if not content_lock:
            decision = ReconciliationDecision(
                action="none",
                reason="execution_locked",
                content_status_after=scanned_candidate.content_status,
                operation_status_after=scanned_candidate.operation_status,
                retry_count_after=scanned_candidate.operation_retry_count,
            )
            return self._item(
                scanned_candidate,
                decision,
                row=scanned_row,
                projection="observed",
                applied=False,
            )

        root_id = await queue_setup._resolve_operation_graph_root(
            self._connection,
            int(operation_id),
        )
        if root_id is None:
            raise RuntimeError("Owning operation graph vanished during reconciliation")
        await queue_setup._acquire_operation_graph_lock(self._connection, root_id)
        locked_root = await self._connection.fetchval(
            "SELECT id FROM pgqueuer_jobs WHERE id = $1 FOR UPDATE",
            root_id,
        )
        if locked_root is None:
            raise RuntimeError("Owning operation root vanished during reconciliation")
        locked_target = await self._connection.fetchval(
            "SELECT id FROM pgqueuer_jobs WHERE id = $1 FOR UPDATE",
            operation_id,
        )
        if locked_target is None:
            raise RuntimeError("Owning operation vanished during reconciliation")
        locked_content = await self._connection.fetchval(
            "SELECT id FROM contents WHERE id = $1 FOR UPDATE",
            content_id,
        )
        if locked_content is None:
            raise RuntimeError("Candidate Content vanished during reconciliation")
        await self._connection.fetch(
            """
            SELECT id FROM summaries
            WHERE content_id = $1
              AND operation_id = $2
              AND operation_claim_generation = $3
            ORDER BY created_at DESC, id DESC
            FOR UPDATE
            """,
            content_id,
            operation_id,
            scanned_row["owner_claim_generation"],
        )

        current_row = await self._read_candidate(content_id)
        if current_row is None:
            raise RuntimeError("Candidate evidence vanished during reconciliation")
        current = self._candidate(current_row)
        current = CandidateSnapshot(
            **{
                **self._candidate_values(current),
                "lock_state": LockState.ACQUIRED,
                "revalidated": self._same_evidence(scanned_row, current_row),
            }
        )
        decision = self._classifier.classify(current)
        if decision is None:
            raise RuntimeError("Protected Content unexpectedly reached apply")
        if decision.action == "none":
            return self._item(
                current,
                decision,
                row=current_row,
                projection="observed",
                applied=False,
            )

        await self._mutate(current, decision, current_row=current_row, root_id=root_id)
        observed = await self._connection.fetchrow(
            """
            SELECT c.status AS content_status_after,
                   j.status AS operation_status_after,
                   j.retry_count AS retry_count_after,
                   j.heartbeat_at AS operation_heartbeat_at,
                   j.completed_at AS operation_completed_at
            FROM contents AS c
            JOIN pgqueuer_jobs AS j ON j.id = $2
            WHERE c.id = $1
            """,
            content_id,
            operation_id,
        )
        if observed is None:
            raise RuntimeError("Applied reconciliation state could not be observed")
        observed_decision = ReconciliationDecision(
            action=decision.action,
            reason=decision.reason,
            content_status_after=observed["content_status_after"],
            operation_status_after=observed["operation_status_after"],
            retry_count_after=observed["retry_count_after"],
        )
        observed_row = dict(current_row)
        observed_row["operation_heartbeat_at"] = observed["operation_heartbeat_at"]
        observed_row["operation_completed_at"] = observed["operation_completed_at"]
        item = self._item(
            current,
            observed_decision,
            row=observed_row,
            projection="observed",
            applied=True,
        )
        await self._insert_action(run_id=run_id, decision=item)
        return item

    async def _mutate(
        self,
        candidate: CandidateSnapshot,
        decision: ReconciliationDecision,
        *,
        current_row: asyncpg.Record,
        root_id: int,
    ) -> None:
        if decision.action in {"project_completed", "project_parsed"}:
            await self._project_output(candidate, decision, current_row=current_row)
            return
        if decision.action in {
            "restore_parsed",
            "restore_pending",
            "cancel_restore_parsed",
            "cancel_restore_pending",
        }:
            if decision.action.startswith("cancel_"):
                await self._connection.execute(
                    """
                    UPDATE pgqueuer_jobs
                    SET status = 'cancelled', completed_at = NOW(), heartbeat_at = NOW()
                    WHERE id = $1 AND status = 'in_progress'
                    """,
                    candidate.operation_id,
                )
            await self._restore_predecessor(candidate, decision)
            return
        if decision.action == "retry_operation":
            if candidate.operation_status == "in_progress":
                await self._connection.execute(
                    """
                    UPDATE contents
                    SET status = 'failed', status_owner_version = status_owner_version + 1
                    WHERE id = $1
                      AND status_operation_id = $2
                      AND status_claim_generation = $3
                      AND status_operation_phase = $4
                      AND status_owner_version = $5
                    """,
                    candidate.content_id,
                    candidate.owner_operation_id,
                    candidate.owner_claim_generation,
                    candidate.owner_phase,
                    candidate.owner_version,
                )
                await self._connection.execute(
                    """
                    UPDATE pgqueuer_jobs
                    SET status = 'failed', completed_at = NOW(), heartbeat_at = NOW(),
                        error = 'Stale operation reclaimed by content reconciliation'
                    WHERE id = $1 AND status = 'in_progress'
                      AND claim_generation = $2
                    """,
                    candidate.operation_id,
                    candidate.operation_claim_generation,
                )
            await OperationService(connection=self._connection)._retry_locked(
                self._connection,
                int(candidate.operation_id),
                root_id=root_id,
                max_retries=self._classifier._max_retries,
            )
            return
        raise RuntimeError(f"Unsupported reconciliation action: {decision.action}")

    async def _project_output(
        self,
        candidate: CandidateSnapshot,
        decision: ReconciliationDecision,
        *,
        current_row: asyncpg.Record,
    ) -> None:
        if decision.action == "project_completed":
            processed_at = await self._connection.fetchval(
                """
                SELECT created_at FROM summaries
                WHERE content_id = $1 AND operation_id = $2
                  AND operation_claim_generation = $3
                ORDER BY created_at DESC, id DESC LIMIT 1
                """,
                candidate.content_id,
                candidate.operation_id,
                candidate.operation_claim_generation,
            )
            await self._connection.execute(
                """
                UPDATE contents
                SET status = 'completed', error_message = NULL, processed_at = $2,
                    status_operation_id = NULL, status_claim_generation = NULL,
                    status_operation_phase = NULL, status_owner_version = NULL
                WHERE id = $1
                """,
                candidate.content_id,
                processed_at,
            )
        else:
            await self._connection.execute(
                """
                UPDATE contents
                SET status = 'parsed', error_message = NULL, parsed_at = $2,
                    processed_at = NULL, status_operation_id = NULL,
                    status_claim_generation = NULL, status_operation_phase = NULL,
                    status_owner_version = NULL
                WHERE id = $1
                """,
                candidate.content_id,
                current_row["operation_completed_at"],
            )

    async def _restore_predecessor(
        self,
        candidate: CandidateSnapshot,
        decision: ReconciliationDecision,
    ) -> None:
        if decision.content_status_after == "parsed":
            await self._connection.execute(
                """
                UPDATE contents
                SET status = 'parsed', error_message = NULL, processed_at = NULL,
                    status_operation_id = NULL, status_claim_generation = NULL,
                    status_operation_phase = NULL, status_owner_version = NULL
                WHERE id = $1
                """,
                candidate.content_id,
            )
        else:
            await self._connection.execute(
                """
                UPDATE contents
                SET status = 'pending', error_message = NULL, parsed_at = NULL,
                    processed_at = NULL, status_operation_id = NULL,
                    status_claim_generation = NULL, status_operation_phase = NULL,
                    status_owner_version = NULL
                WHERE id = $1
                """,
                candidate.content_id,
            )

    async def _insert_action(
        self,
        *,
        run_id: UUID,
        decision: ContentReconciliationItem,
    ) -> None:
        await self._connection.execute(
            """
            INSERT INTO content_reconciliation_actions (
                run_id, content_id, operation_id, claim_generation,
                claim_protocol_version, phase, content_status_before,
                content_status_after, operation_status_before,
                operation_status_after, retry_count_before, retry_count_after,
                action, reason
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
            )
            """,
            run_id,
            decision.content_id,
            int(decision.operation_id),
            decision.claim_generation,
            decision.claim_protocol_version,
            decision.phase,
            decision.content_status_before,
            decision.content_status_after,
            decision.operation_status_before,
            decision.operation_status_after,
            decision.retry_count_before,
            decision.retry_count_after,
            decision.action,
            decision.reason,
        )

    @staticmethod
    def _candidate_values(candidate: CandidateSnapshot) -> dict[str, Any]:
        return {
            field: getattr(candidate, field) for field in CandidateSnapshot.__dataclass_fields__
        }

    @staticmethod
    def _same_evidence(scanned: asyncpg.Record, current: asyncpg.Record) -> bool:
        fields = (
            "content_status",
            "owner_operation_id",
            "owner_claim_generation",
            "owner_phase",
            "owner_version",
            "operation_id",
            "operation_status",
            "operation_claim_generation",
            "operation_claim_protocol_version",
            "operation_retry_count",
            "operation_cancel_requested",
            "operation_force",
            "operation_heartbeat_at",
            "operation_completed_at",
        )
        return all(scanned[field] == current[field] for field in fields)

    async def _scan(
        self,
        *,
        after_content_id: int,
        limit: int,
    ) -> list[asyncpg.Record]:
        return await self._connection.fetch(
            """
            SELECT
                c.id AS content_id,
                c.status AS content_status,
                c.status_operation_id AS owner_operation_id,
                c.status_claim_generation AS owner_claim_generation,
                c.status_operation_phase AS owner_phase,
                c.status_owner_version AS owner_version,
                j.id AS operation_id,
                j.status AS operation_status,
                j.claim_generation AS operation_claim_generation,
                j.claim_protocol_version AS operation_claim_protocol_version,
                j.retry_count AS operation_retry_count,
                COALESCE(j.payload->>'cancel_requested' = 'true', FALSE)
                    AS operation_cancel_requested,
                COALESCE(
                    j.payload #>> '{input,force}' = 'true'
                    OR j.payload #>> '{input,force_reprocess}' = 'true',
                    FALSE
                ) AS operation_force,
                COALESCE(
                    j.status = 'in_progress'
                    AND COALESCE(j.heartbeat_at, j.started_at, j.created_at)
                        < NOW() - make_interval(secs => $3),
                    FALSE
                ) AS operation_is_stale,
                EXISTS (
                    SELECT 1 FROM summaries AS matching
                    WHERE matching.content_id = c.id
                      AND matching.operation_id = c.status_operation_id
                      AND matching.operation_claim_generation = c.status_claim_generation
                ) AS matching_summary,
                EXISTS (
                    SELECT 1 FROM summaries AS mismatched
                    WHERE mismatched.content_id = c.id
                      AND (
                          mismatched.operation_id IS DISTINCT FROM c.status_operation_id
                          OR mismatched.operation_claim_generation
                             IS DISTINCT FROM c.status_claim_generation
                      )
                ) AS mismatched_summary,
                COALESCE(
                    j.status = 'completed'
                    AND j.payload->'result'->>'command_key' = 'url'
                    AND j.payload->'result'->>'resolved_route' = 'webpage'
                    AND j.payload->'result'->>'status' = 'ok'
                    AND j.payload->'result'->>'outcome' = 'success'
                    AND CASE
                        WHEN jsonb_typeof(j.payload->'result'->'content_ids') = 'array'
                        THEN jsonb_array_length(
                            j.payload->'result'->'content_ids'
                        ) = 1
                        ELSE FALSE
                    END
                    AND CASE
                        WHEN j.payload->'result'->'content_ids'->>0
                            ~ '^[1-9][0-9]{0,18}$'
                        THEN (j.payload->'result'->'content_ids'->>0)::numeric = c.id
                        ELSE FALSE
                    END,
                    FALSE
                ) AS extraction_succeeded,
                j.heartbeat_at AS operation_heartbeat_at,
                j.completed_at AS operation_completed_at
            FROM contents AS c
            LEFT JOIN pgqueuer_jobs AS j ON j.id = c.status_operation_id
            WHERE c.status IN ('parsing', 'processing', 'failed')
              AND c.id > $1
            ORDER BY c.id
            LIMIT $2
            """,
            after_content_id,
            limit + 1,
            self._stale_seconds,
        )

    async def _read_candidate(self, content_id: int) -> asyncpg.Record | None:
        rows = await self._scan(after_content_id=content_id - 1, limit=1)
        if not rows or int(rows[0]["content_id"]) != content_id:
            return None
        return rows[0]

    def _dry_run_item(self, row: asyncpg.Record) -> ContentReconciliationItem:
        candidate = self._candidate(row)
        decision = self._classifier.classify(candidate)
        if decision is None:
            raise RuntimeError("Protected Content unexpectedly reached reconciliation scan")
        return self._item(candidate, decision, row=row, projection="proposed", applied=False)

    @staticmethod
    def _candidate(row: asyncpg.Record) -> CandidateSnapshot:
        return CandidateSnapshot(
            content_id=int(row["content_id"]),
            content_status=row["content_status"],
            owner_operation_id=row["owner_operation_id"],
            owner_claim_generation=row["owner_claim_generation"],
            owner_phase=row["owner_phase"],
            owner_version=row["owner_version"],
            operation_id=row["operation_id"],
            operation_status=row["operation_status"],
            operation_claim_generation=row["operation_claim_generation"],
            operation_claim_protocol_version=row["operation_claim_protocol_version"],
            operation_retry_count=row["operation_retry_count"],
            operation_cancel_requested=bool(row["operation_cancel_requested"]),
            operation_force=bool(row["operation_force"]),
            operation_is_stale=bool(row["operation_is_stale"]),
            matching_summary=bool(row["matching_summary"]),
            mismatched_summary=bool(row["mismatched_summary"]),
            extraction_succeeded=bool(row["extraction_succeeded"]),
            lock_state=LockState.NOT_CHECKED,
            revalidated=True,
        )

    @staticmethod
    def _item(
        candidate: CandidateSnapshot,
        decision: ReconciliationDecision,
        *,
        row: Any,
        projection: str,
        applied: bool,
    ) -> ContentReconciliationItem:
        return ContentReconciliationItem(
            content_id=candidate.content_id,
            projection=projection,
            content_status_before=candidate.content_status,
            content_status_after=decision.content_status_after,
            operation_id=(
                str(candidate.operation_id) if candidate.operation_id is not None else None
            ),
            claim_generation=candidate.operation_claim_generation,
            claim_protocol_version=candidate.operation_claim_protocol_version,
            operation_status_before=candidate.operation_status,
            operation_status_after=decision.operation_status_after,
            retry_count_before=candidate.operation_retry_count,
            retry_count_after=decision.retry_count_after,
            phase=candidate.owner_phase,
            action=decision.action,
            reason=decision.reason,
            operation_heartbeat_at=row["operation_heartbeat_at"],
            operation_completed_at=row["operation_completed_at"],
            applied=applied,
        )

    @staticmethod
    def _counts(items: list[ContentReconciliationItem]) -> ContentReconciliationCounts:
        values = dict.fromkeys(ContentReconciliationCounts.model_fields, 0)
        for item in items:
            if item.applied:
                values["applied"] += 1
            if item.action == "retry_operation":
                values["retried"] += 1
            if item.action in {"project_completed", "project_parsed"}:
                values["projected"] += 1
            if item.action in {
                "restore_parsed",
                "restore_pending",
                "cancel_restore_parsed",
                "cancel_restore_pending",
            }:
                values["restored"] += 1
            reason_count = {
                "active_operation": "active",
                "cancellation_pending": "active",
                "execution_locked": "locked",
                "missing_operation": "missing",
                "ownership_conflict": "conflicted",
                "revalidation_conflict": "conflicted",
                "cancellation_requested": "cancelled",
                "forced_reprocessing": "forced",
                "retry_budget_exhausted": "exhausted",
                "incompatible_worker": "incompatible",
                "apply_failed": "failed",
            }.get(item.reason)
            if reason_count is not None:
                values[reason_count] += 1
        return ContentReconciliationCounts(**values)
