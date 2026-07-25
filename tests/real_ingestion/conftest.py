"""Fixtures for the real-ingestion CI tiers.

These tests intentionally *commit* to the test database (see
``tests/real_ingestion/harness.py`` for why cross-connection verification
requires it), so they cannot use the rolled-back ``db_session`` fixture. Each
harness namespaces its rows with a unique token and cleans them up.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator

import asyncpg
import pytest
import pytest_asyncio

from tests.real_ingestion import evidence_sink
from tests.real_ingestion.harness import RealIngestionHarness, _asyncpg_dsn


@pytest.fixture(scope="session", autouse=True)
def _write_failure_class_summary() -> Iterator[None]:
    """Render the collected failure-class evidence for the scheduled CI artifact."""

    yield
    path = os.environ.get("REAL_INGEST_EVIDENCE_PATH")
    if path and evidence_sink.COLLECTED:
        evidence_sink.flush_to(path)


@pytest_asyncio.fixture
async def real_ingestion_harness(test_engine) -> AsyncIterator[RealIngestionHarness]:
    """Provide a harness bound to the shared test database and clean up after."""

    conn = await asyncpg.connect(_asyncpg_dsn(test_engine))
    harness = RealIngestionHarness(test_engine, conn, token=uuid.uuid4().hex[:12])
    try:
        yield harness
    finally:
        try:
            await harness.cleanup()
        finally:
            await conn.close()
