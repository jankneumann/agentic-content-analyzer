"""Shared test database helper for parallel-safe test execution.

Provides worktree-aware database naming, auto-creation, and engine
factories. All three conftest files (root, api, integration) import
from this module to avoid duplicating connection logic.

Key behaviors:
- Detects git worktrees via the `.git` file to derive unique DB names
- Auto-creates test databases via admin connection to `postgres` DB
- Safety check: refuses to connect to databases without "test" in the name
- `TEST_DATABASE_URL` env var always overrides worktree detection
"""

import logging
import os
import re
from pathlib import Path

from sqlalchemy import create_engine as _sa_create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_MAX_PG_IDENTIFIER = 63
_PREFIX = "newsletters_test_"
_DEFAULT_BASE_URL = "postgresql://newsletter_user:newsletter_password@localhost"


def get_worktree_name() -> str | None:
    """Detect if running from a git worktree, return its name.

    In a git worktree, `.git` is a text file (not a directory) containing
    ``gitdir: /path/to/.git/worktrees/<name>``. We parse this to extract
    the worktree name.

    Returns None for main repo, missing `.git`, or parse failures.
    """
    git_path = Path.cwd() / ".git"
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


def get_test_db_name() -> str:
    """Return worktree-aware test database name.

    PostgreSQL identifiers are limited to 63 characters.
    Long worktree names are truncated to fit within this limit.
    """
    worktree = get_worktree_name()
    if worktree:
        # Sanitize: replace non-alphanumeric with underscore, lowercase
        suffix = re.sub(r"[^a-z0-9]", "_", worktree.lower()).strip("_")
        max_suffix = _MAX_PG_IDENTIFIER - len(_PREFIX)
        suffix = suffix[:max_suffix]
        return f"{_PREFIX}{suffix}"
    return "newsletters_test"


def get_test_database_url() -> str:
    """Resolve the test database URL.

    Precedence:
    1. ``TEST_DATABASE_URL`` env var (always wins)
    2. Worktree-aware URL derived from ``get_test_db_name()``
    """
    env_url = os.getenv("TEST_DATABASE_URL")
    if env_url:
        return env_url
    db_name = get_test_db_name()
    return f"{_DEFAULT_BASE_URL}/{db_name}"


def ensure_test_db_exists(db_name: str, base_url: str) -> None:
    """Create the test database if it doesn't exist.

    Connects to the ``postgres`` admin database with ``AUTOCOMMIT``
    isolation to issue DDL. Raises ``RuntimeError`` with a helpful
    message if the admin connection fails.
    """
    admin_url = base_url.rsplit("/", 1)[0] + "/postgres"
    try:
        admin_engine = _sa_create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not exists:
                logger.info("Auto-creating test database: %s", db_name)
                # DB names can't be parameterized — use quoted identifier
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        admin_engine.dispose()
    except Exception as exc:
        raise RuntimeError(
            f"Could not auto-create test database '{db_name}'. "
            f"Ensure PostgreSQL is running and accessible. "
            f"You can also create it manually: "
            f"createdb {db_name}\n"
            f"Original error: {exc}"
        ) from exc


def create_test_engine(url: str | None = None) -> Engine:
    """Create a test database engine with safety checks and auto-creation.

    1. Resolves the URL (from argument or ``get_test_database_url()``)
    2. Safety check: verifies "test" is in the database name
    3. Auto-creates the database if it doesn't exist
    4. Returns a SQLAlchemy engine

    This does NOT create/drop tables — that remains the conftest's job
    so each test suite can control its own table lifecycle.
    """
    if url is None:
        url = get_test_database_url()

    engine = _sa_create_engine(url, echo=False)

    # Safety check: Only use test databases
    db_name = engine.url.database
    if not db_name or "test" not in db_name.lower():
        engine.dispose()
        raise ValueError(
            f"Safety check failed: Database '{db_name}' does not contain 'test'. "
            f"Set TEST_DATABASE_URL to a test database."
        )

    # Auto-create the database if it doesn't exist
    ensure_test_db_exists(db_name, url)

    return engine
