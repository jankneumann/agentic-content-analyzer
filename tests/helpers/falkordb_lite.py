"""FalkorDB Lite embedded test fixture.

Manages an embedded FalkorDB instance via the `falkordblite` package
for fast, isolated graph database testing without Docker.
"""

from __future__ import annotations

import atexit
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FalkorDBLiteFixture:
    """Manage an embedded FalkorDB Lite instance for testing.

    Usage:
        fixture = FalkorDBLiteFixture()
        fixture.start()
        graph = fixture.graph("test_graph")
        graph.query("CREATE (n:Test {name: 'hello'})")
        fixture.reset()  # clear all data
        fixture.stop()
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else None
        self._tmpdir: Path | None = None
        self._db: Any = None
        self._started = False

    @property
    def db_path(self) -> Path:
        """Path to the FalkorDB Lite database file."""
        base = self._data_dir or self._tmpdir
        if base is None:
            raise RuntimeError("FalkorDB Lite not started")
        return base / "falkordb-test.db"

    def start(self, timeout: float = 10.0) -> None:
        """Start the embedded FalkorDB Lite instance.

        Args:
            timeout: Maximum seconds to wait for startup (unused — Lite starts synchronously)
        """
        if self._started:
            return

        # Create temp directory if no explicit data_dir
        if self._data_dir is None:
            self._tmpdir = Path(tempfile.mkdtemp(prefix="falkordb-test-"))

        try:
            from redislite import FalkorDB

            self._db = FalkorDB(str(self.db_path))
            self._started = True
            atexit.register(self.stop)
            logger.info("Started FalkorDB Lite at %s", self.db_path)
        except Exception:
            logger.error("Failed to start FalkorDB Lite", exc_info=True)
            self._cleanup_tmpdir()
            raise

    def stop(self) -> None:
        """Stop the embedded instance and clean up."""
        if not self._started:
            return

        try:
            if self._db is not None:
                self._db.shutdown()
                self._db = None
        except Exception:
            logger.debug("FalkorDB Lite shutdown error", exc_info=True)

        self._cleanup_tmpdir()
        self._started = False
        logger.info("Stopped FalkorDB Lite")

    def reset(self) -> None:
        """Clear all data (FLUSHDB). Fast — used between tests."""
        if self._db is not None:
            self._db.flushdb()

    def graph(self, name: str = "test") -> Any:
        """Get a graph handle for querying."""
        if self._db is None:
            raise RuntimeError("FalkorDB Lite not started — call start() first")
        return self._db.select_graph(name)

    def create_provider(self, database: str = "test") -> Any:
        """Create a FalkorDBGraphDBProvider backed by this Lite instance.

        Returns a provider that satisfies the GraphDBProvider protocol,
        pre-connected to this embedded instance (bypassing lazy connect).
        """
        from src.storage.falkordb_provider import FalkorDBGraphDBProvider

        provider = FalkorDBGraphDBProvider(
            host="localhost",
            port=0,
            database=database,
            mode="embedded",
        )
        # Inject our Lite-managed client and graph directly
        provider._client = self._db
        provider._graph = self._db.select_graph(database)
        return provider

    def _cleanup_tmpdir(self) -> None:
        """Remove temp directory if we created one."""
        if self._tmpdir and self._tmpdir.exists():
            try:
                shutil.rmtree(self._tmpdir)
            except Exception:
                logger.debug("Failed to clean up %s", self._tmpdir, exc_info=True)
            self._tmpdir = None
