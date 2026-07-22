"""Tests for BatchCollector + ResultHandlerRegistry (no Postgres required).

Uses an in-memory SQLite session with only the two batch tables created, so the
collector's persistence is exercised hermetically (the batch models use generic
SQLAlchemy types that round-trip on SQLite).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.models import ModelConfig, ModelStep
from src.models.batch import BatchJob, BatchRequest as BatchRequestRow
from src.services.batch import (
    BatchCollector,
    BatchRequest,
    ResultHandlerRegistry,
    result_handlers,
)


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    # Create only the batch tables — avoids pulling in pgvector/ARRAY columns.
    BatchJob.__table__.create(engine)
    BatchRequestRow.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def collector() -> BatchCollector:
    config = ModelConfig()
    config._batch_config["enabled"] = True
    config._batch_config["execution"][ModelStep.CONTENT_FILTERING.value] = "batch"
    return BatchCollector(config)


class TestEnqueue:
    def test_persists_pending_row(self, db, collector):
        row = collector.enqueue(
            db,
            ModelStep.CONTENT_FILTERING,
            42,
            BatchRequest(key="ignored", contents="classify me", config={"temperature": 0.0}),
        )
        db.commit()

        assert row.status == "pending"
        assert row.content_id == 42
        assert row.model_step == ModelStep.CONTENT_FILTERING.value
        assert row.model_id  # resolved from ModelConfig, non-empty
        assert row.request_payload == {"contents": "classify me", "config": {"temperature": 0.0}}
        assert row.batch_job_id is None  # not yet flushed into a job

    def test_disabled_step_is_a_noop(self, db):
        collector = BatchCollector(ModelConfig())

        row = collector.enqueue(
            db,
            ModelStep.CONTENT_FILTERING,
            7,
            BatchRequest(key="ignored", contents="classify me"),
        )

        assert row is None
        assert db.query(BatchRequestRow).count() == 0

    def test_enqueue_is_idempotent(self, db, collector):
        first = collector.enqueue(
            db, ModelStep.CONTENT_FILTERING, 99, BatchRequest(key="", contents="a")
        )
        second = collector.enqueue(
            db, ModelStep.CONTENT_FILTERING, 99, BatchRequest(key="", contents="b")
        )
        db.commit()

        # Same active row returned; no duplicate; original payload preserved.
        assert second.id == first.id
        assert db.query(BatchRequestRow).count() == 1
        assert first.request_payload["contents"] == "a"

    def test_row_visible_after_flush_same_txn(self, db, collector):
        collector.enqueue(db, ModelStep.CONTENT_FILTERING, 1, BatchRequest(key="", contents="x"))
        # enqueue flushed — a query in the same uncommitted txn must see it.
        found = db.query(BatchRequestRow).filter(BatchRequestRow.content_id == 1).first()
        assert found is not None

    def test_terminal_request_does_not_block_new_collection(self, db, collector):
        first = collector.enqueue(
            db, ModelStep.CONTENT_FILTERING, 5, BatchRequest(key="", contents="first")
        )
        first.status = "succeeded"
        db.commit()

        second = collector.enqueue(
            db, ModelStep.CONTENT_FILTERING, 5, BatchRequest(key="", contents="second")
        )
        db.commit()

        assert second.id != first.id
        assert second.request_key != first.request_key
        assert db.query(BatchRequestRow).count() == 2

    def test_standard_token_limit_config_is_not_mistaken_for_a_credential(self, db, collector):
        row = collector.enqueue(
            db,
            ModelStep.CONTENT_FILTERING,
            6,
            BatchRequest(
                key="",
                contents="classify",
                config={"max_output_tokens": 512},
            ),
        )

        assert row is not None
        assert row.request_payload["config"]["max_output_tokens"] == 512

    def test_explicit_api_key_is_rejected(self, db, collector):
        with pytest.raises(ValueError, match="credentials"):
            collector.enqueue(
                db,
                ModelStep.CONTENT_FILTERING,
                7,
                BatchRequest(key="", contents="classify", config={"api_key": "secret"}),
            )


class TestResultHandlerRegistry:
    def test_register_and_get(self):
        registry = ResultHandlerRegistry()

        class _Handler:
            def apply(self, db, request, result_text):
                return None

        handler = _Handler()
        registry.register(ModelStep.CONTENT_FILTERING, handler)

        assert registry.get(ModelStep.CONTENT_FILTERING) is handler
        assert ModelStep.CONTENT_FILTERING in registry
        assert registry.steps() == [ModelStep.CONTENT_FILTERING]

    def test_get_missing_returns_none(self):
        registry = ResultHandlerRegistry()
        assert registry.get(ModelStep.YOUTUBE_PROCESSING) is None
        assert ModelStep.YOUTUBE_PROCESSING not in registry

    def test_last_registration_wins(self):
        registry = ResultHandlerRegistry()

        class _H:
            def __init__(self, tag):
                self.tag = tag

            def apply(self, db, request, result_text):
                return None

        registry.register(ModelStep.CONTENT_FILTERING, _H("first"))
        registry.register(ModelStep.CONTENT_FILTERING, _H("second"))
        assert registry.get(ModelStep.CONTENT_FILTERING).tag == "second"

    def test_module_singleton_exists(self):
        # Phase modules register against this shared instance at import time.
        assert isinstance(result_handlers, ResultHandlerRegistry)

    def test_registers_fallback_handler_independently(self):
        registry = ResultHandlerRegistry()

        class _Fallback:
            async def fallback(self, db, request):
                return "sync-result"

        handler = _Fallback()
        registry.register_fallback(ModelStep.CONTENT_FILTERING, handler)

        assert registry.get_fallback(ModelStep.CONTENT_FILTERING) is handler
