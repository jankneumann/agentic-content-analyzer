"""E2E test server lifecycle — start, migrate, health-check, teardown.

Manages a uvicorn subprocess running with PROFILE=test on a dynamically
allocated port, backed by a dedicated test database. This replaces the
previous requirement of `make dev-bg` before running E2E tests.

The server lifecycle is:
    1. Pick a free port (coordinator allocation or deterministic fallback)
    2. Create the test database if it doesn't exist
    3. Run Alembic migrations against the test database
    4. Start uvicorn as a subprocess with PROFILE=test
    5. Wait for GET /health to return 200
    6. Yield connection info to tests

Usage (from conftest.py):
    @pytest.fixture(scope="session")
    def managed_server():
        with e2e_server() as info:
            yield info
"""

from __future__ import annotations

import logging
import os
import re
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FALLBACK_PORT = 9100
_HEALTH_TIMEOUT = 30.0  # seconds to wait for /health 200
_HEALTH_INTERVAL = 0.5  # seconds between health check polls
_SHUTDOWN_TIMEOUT = 5.0  # seconds to wait for graceful shutdown

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServerInfo:
    """Connection info for a running E2E test server."""

    base_url: str
    port: int
    db_name: str
    db_url: str
    pid: int


# ---------------------------------------------------------------------------
# Port allocation
# ---------------------------------------------------------------------------


def _find_free_port(preferred: int = _FALLBACK_PORT) -> int:
    """Find a free TCP port, preferring ``preferred``.

    Tries the preferred port first. If it's in use, falls back to
    OS-assigned ephemeral port (port 0).
    """
    for port in [preferred, 0]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                allocated: int = s.getsockname()[1]
                return allocated
        except OSError:
            continue
    raise RuntimeError("Could not find a free port for E2E server")


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

_E2E_DB_PREFIX = "newsletters_e2e"
_MAX_PG_IDENTIFIER = 63
_DEFAULT_BASE_URL = "postgresql://newsletter_user:newsletter_password@localhost:5432"


def _get_worktree_name() -> str | None:
    """Detect git worktree name (mirrors tests/helpers/test_db.py logic)."""
    git_path = _PROJECT_ROOT / ".git"
    if git_path.is_file():
        try:
            content = git_path.read_text().strip()
        except OSError:
            return None
        if content.startswith("gitdir:"):
            parts = content.split("/worktrees/")
            if len(parts) == 2:
                return parts[1].rstrip("/")
    return None


def get_e2e_db_name() -> str:
    """Return worktree-aware E2E database name.

    Examples:
        Main repo:               "newsletters_e2e"
        Worktree "feat-xyz":     "newsletters_e2e_feat_xyz"
    """
    worktree = _get_worktree_name()
    if worktree:
        suffix = re.sub(r"[^a-z0-9]", "_", worktree.lower()).strip("_")
        prefix = f"{_E2E_DB_PREFIX}_"
        max_suffix = _MAX_PG_IDENTIFIER - len(prefix)
        suffix = suffix[:max_suffix]
        return f"{prefix}{suffix}"
    return _E2E_DB_PREFIX


def get_e2e_db_url() -> str:
    """Resolve E2E database URL.

    Precedence:
        1. TEST_DATABASE_URL env var
        2. Worktree-aware URL from get_e2e_db_name()
    """
    env_url = os.getenv("TEST_DATABASE_URL")
    if env_url:
        return env_url
    return f"{_DEFAULT_BASE_URL}/{get_e2e_db_name()}"


def _ensure_db_exists(db_name: str, db_url: str) -> None:
    """Create the E2E database if it doesn't exist.

    Connects to the ``postgres`` admin database to issue CREATE DATABASE.
    Handles race conditions (another process creates it concurrently).
    """
    from sqlalchemy import create_engine, text

    admin_url = db_url.rsplit("/", 1)[0] + "/postgres"
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not exists:
                logger.info("Creating E2E database: %s", db_name)
                try:
                    conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                except Exception as exc:
                    if "already exists" in str(exc) or "42P04" in str(exc):
                        logger.info("Database %s created by another process", db_name)
                    else:
                        raise
    finally:
        engine.dispose()


def _run_migrations(db_url: str) -> None:
    """Run ``alembic upgrade head`` against the E2E database."""
    env = {**os.environ, "DATABASE_URL": db_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(_PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        logger.error("Alembic migration failed:\n%s\n%s", result.stdout, result.stderr)
        raise RuntimeError(f"Alembic migration failed (exit {result.returncode}):\n{result.stderr}")
    logger.info("Alembic migrations applied to E2E database")


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


def _wait_for_health(base_url: str, timeout: float = _HEALTH_TIMEOUT) -> None:
    """Poll GET /health until 200 or timeout."""
    deadline = time.monotonic() + timeout
    last_error: str = ""
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{base_url}/health", timeout=2.0)
            if resp.status_code == 200:
                logger.info("E2E server healthy at %s", base_url)
                return
            last_error = f"HTTP {resp.status_code}"
        except httpx.ConnectError:
            last_error = "connection refused"
        except httpx.TimeoutException:
            last_error = "timeout"
        time.sleep(_HEALTH_INTERVAL)
    raise RuntimeError(
        f"E2E server at {base_url} did not become healthy within {timeout}s "
        f"(last error: {last_error})"
    )


def _start_uvicorn(port: int, db_url: str) -> subprocess.Popen:
    """Start uvicorn subprocess with PROFILE=test.

    Returns the Popen handle. The caller is responsible for terminating it.
    """
    env = {
        **os.environ,
        "PROFILE": "test",
        "DATABASE_URL": db_url,
        "WORKER_ENABLED": "false",
        "PORT": str(port),
    }

    # Remove keys that might conflict with the test profile
    env.pop("ADMIN_API_KEY", None)
    env.pop("APP_SECRET_KEY", None)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(_PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    logger.info("Started uvicorn (pid=%d) on port %d", proc.pid, port)
    return proc


def _stop_server(proc: subprocess.Popen) -> None:
    """Gracefully stop the uvicorn subprocess."""
    if proc.poll() is not None:
        return  # already exited

    logger.info("Stopping E2E server (pid=%d)", proc.pid)
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=_SHUTDOWN_TIMEOUT)
    except subprocess.TimeoutExpired:
        logger.warning("Server did not stop gracefully, sending SIGKILL")
        proc.kill()
        proc.wait(timeout=2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@contextmanager
def e2e_server(preferred_port: int = _FALLBACK_PORT) -> Generator[ServerInfo, None, None]:
    """Context manager that runs an isolated E2E backend.

    Yields a ``ServerInfo`` with connection details for the running server.

    Example::

        with e2e_server() as info:
            resp = httpx.get(f"{info.base_url}/health")
            assert resp.status_code == 200
    """
    db_name = get_e2e_db_name()
    db_url = get_e2e_db_url()
    port = _find_free_port(preferred_port)
    base_url = f"http://127.0.0.1:{port}"

    # 1. Ensure database exists
    _ensure_db_exists(db_name, db_url)

    # 2. Run migrations
    _run_migrations(db_url)

    # 3. Start server
    proc = _start_uvicorn(port, db_url)
    try:
        # 4. Wait for health
        _wait_for_health(base_url)

        yield ServerInfo(
            base_url=base_url,
            port=port,
            db_name=db_name,
            db_url=db_url,
            pid=proc.pid,
        )
    finally:
        _stop_server(proc)
