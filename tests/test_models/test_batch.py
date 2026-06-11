"""Tests for the Gemini batch-execution ORM models (no DB required)."""

import uuid

from src.models import BatchJob, BatchRequest


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
        idx = {i.name for i in BatchJob.__table__.indexes}
        assert "ix_batch_jobs_open" in idx


class TestBatchRequest:
    def test_tablename_and_columns(self):
        assert BatchRequest.__tablename__ == "batch_requests"
        cols = set(BatchRequest.__table__.columns.keys())
        assert {
            "request_key",
            "batch_job_id",
            "target_table",
            "target_id",
            "request_payload",
            "status",
            "result_text",
        } <= cols

    def test_request_key_is_unique(self):
        assert BatchRequest.__table__.c.request_key.unique is True

    def test_fk_points_at_batch_jobs(self):
        fks = {str(fk.target_fullname) for fk in BatchRequest.__table__.foreign_keys}
        assert "batch_jobs.id" in fks

    def test_pending_index_covers_step_model(self):
        idx = {i.name: [c.name for c in i.columns] for i in BatchRequest.__table__.indexes}
        assert idx["ix_batch_requests_pending"] == ["model_step", "model_id", "created_at"]
