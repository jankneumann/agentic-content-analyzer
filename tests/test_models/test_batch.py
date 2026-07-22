"""Tests for the revised Gemini batch-execution persistence contract."""

import uuid

from sqlalchemy import CheckConstraint

from src.models import BatchJob, BatchJobState, BatchRequest, BatchRequestStatus


class TestBatchJob:
    def test_tablename_and_columns(self):
        assert BatchJob.__tablename__ == "batch_jobs"
        cols = set(BatchJob.__table__.columns.keys())
        assert {
            "id",
            "provider",
            "provider_job_name",
            "model_id",
            "model_step",
            "state",
            "request_count",
            "submitted_at",
            "completed_at",
            "error",
            "created_at",
        } <= cols

    def test_id_default_is_uuid(self):
        job = BatchJob(
            provider="google_ai",
            model_id="gemini-3.1-flash-lite",
            model_step="content_filtering",
            state="pending",
        )
        # default callable runs on instantiation
        generated = BatchJob.__table__.c.id.default.arg(None)
        uuid.UUID(generated)  # raises if not a valid uuid string

    def test_open_state_index_present(self):
        indexes = {i.name: i for i in BatchJob.__table__.indexes}
        assert "ix_batch_jobs_open" in indexes
        assert indexes["ix_batch_jobs_open"].dialect_options["postgresql"]["where"] is not None

    def test_provider_job_name_is_unique_when_present(self):
        indexes = {i.name: i for i in BatchJob.__table__.indexes}
        provider_name = indexes["uq_batch_jobs_provider_job_name"]
        assert provider_name.unique is True
        assert provider_name.dialect_options["postgresql"]["where"] is not None

    def test_job_states_are_constrained(self):
        assert {state.value for state in BatchJobState} == {
            "submitting",
            "pending",
            "running",
            "succeeded",
            "failed",
            "cancelled",
            "expired",
        }
        constraints = {
            constraint.name: str(constraint.sqltext)
            for constraint in BatchJob.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        }
        assert "ck_batch_jobs_state" in constraints
        assert "submitting" in constraints["ck_batch_jobs_state"]


class TestBatchRequest:
    def test_tablename_and_columns(self):
        assert BatchRequest.__tablename__ == "batch_requests"
        cols = set(BatchRequest.__table__.columns.keys())
        assert {
            "request_key",
            "batch_job_id",
            "content_id",
            "request_payload",
            "status",
            "result_text",
            "fallback_attempts",
            "updated_at",
        } <= cols
        assert "target_table" not in cols
        assert "target_id" not in cols

    def test_request_key_is_unique(self):
        assert BatchRequest.__table__.c.request_key.unique is True

    def test_request_key_fits_the_canonical_correlation_key(self):
        """The longest step + bigint id + UUID key must fit on PostgreSQL."""
        assert BatchRequest.__table__.c.request_key.type.length >= 128

    def test_fk_points_at_batch_jobs(self):
        fks = {str(fk.target_fullname) for fk in BatchRequest.__table__.foreign_keys}
        assert "batch_jobs.id" in fks
        assert "contents.id" in fks

        content_fk = next(
            fk for fk in BatchRequest.__table__.foreign_keys if fk.target_fullname == "contents.id"
        )
        assert content_fk.ondelete == "SET NULL"
        assert BatchRequest.__table__.c.content_id.nullable is True

    def test_pending_index_covers_step_model(self):
        indexes = {i.name: i for i in BatchRequest.__table__.indexes}
        pending = indexes["ix_batch_requests_pending"]
        assert [column.name for column in pending.columns] == [
            "model_step",
            "model_id",
            "created_at",
        ]
        assert pending.dialect_options["postgresql"]["where"] is not None

    def test_active_content_target_has_partial_unique_index(self):
        indexes = {i.name: i for i in BatchRequest.__table__.indexes}
        active = indexes["uq_batch_requests_active_target"]
        assert active.unique is True
        assert [column.name for column in active.columns] == ["model_step", "content_id"]
        where = str(active.dialect_options["postgresql"]["where"])
        assert "content_id IS NOT NULL" in where
        assert "claimed" in where
        assert "fallback" in where

    def test_request_statuses_are_constrained(self):
        assert {status.value for status in BatchRequestStatus} == {
            "pending",
            "claimed",
            "submitted",
            "succeeded",
            "fallback",
            "failed",
        }
        constraints = {
            constraint.name: str(constraint.sqltext)
            for constraint in BatchRequest.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        }
        assert "ck_batch_requests_status" in constraints
        assert "claimed" in constraints["ck_batch_requests_status"]

    def test_fallback_attempts_default_to_zero(self):
        column = BatchRequest.__table__.c.fallback_attempts
        assert column.nullable is False
        assert column.default.arg == 0
