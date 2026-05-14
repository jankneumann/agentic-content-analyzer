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

    If using SQLite, this is a no-op as the file is created automatically.

    Connects to the ``postgres`` admin database with ``AUTOCOMMIT``
    isolation to issue DDL. Raises ``RuntimeError`` with a helpful
    message if the admin connection fails.

    Handles the race condition where two concurrent pytest sessions
    both detect the DB is missing and try to create it — the second
    attempt gets PG error 42P04 ("database already exists") which is
    safely ignored.
    """
    if "sqlite" in base_url:
        return

    admin_url = base_url.rsplit("/", 1)[0] + "/postgres"
    admin_engine = None
    try:
        admin_engine = _sa_create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not exists:
                logger.info("Auto-creating test database: %s", db_name)
                try:
                    # DB names can't be parameterized — use quoted identifier
                    conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                except Exception as create_exc:
                    # Handle race condition: another process created it first
                    # PG error code 42P04 = duplicate_database
                    err_str = str(create_exc)
                    if "already exists" in err_str or "42P04" in err_str:
                        logger.info(
                            "Database '%s' was created by another process (race condition handled)",
                            db_name,
                        )
                    else:
                        raise
    except Exception as exc:
        raise RuntimeError(
            f"Could not auto-create test database '{db_name}'. "
            f"Ensure PostgreSQL is running and accessible. "
            f"You can also create it manually: "
            f"createdb {db_name}\n"
            f"Original error: {exc}"
        ) from exc
    finally:
        if admin_engine is not None:
            admin_engine.dispose()


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


def reset_test_schema(engine: Engine) -> None:
    """Drop and recreate the public schema, then run alembic to head.

    Replaces the legacy ``Base.metadata.drop_all`` + ``create_all`` pattern.
    Building the schema via alembic ensures tests see the same DDL that
    production migrations produce — no more "missing table because someone
    forgot a model import in conftest" failures.

    Safety: relies on the same ``"test" in db_name`` invariant enforced by
    ``create_test_engine``; refuses to operate on non-test databases.
    """
    db_name = engine.url.database
    if not db_name or "test" not in db_name.lower():
        raise ValueError(f"reset_test_schema refuses non-test database '{db_name}'.")

    # Drop and recreate the public schema for a clean slate. CASCADE catches
    # any orphan objects (sequences, types, enums) that interrupted runs left
    # behind. Outside a transaction so the DDL takes effect immediately.
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()

    # Run alembic upgrade head pointed at the test DB. env.py respects a
    # pre-set sqlalchemy.url (see alembic/env.py) so this doesn't disturb
    # the developer's real DATABASE_URL or settings cache.
    from alembic.config import Config

    from alembic import command

    repo_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(repo_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(repo_root / "alembic"))
    # render_as_string(hide_password=False) — plain str(engine.url) redacts the
    # password to "***" (a SQLAlchemy safety feature for log output) which would
    # silently break the alembic connection with an "auth failed" error.
    target_url = engine.url.render_as_string(hide_password=False)
    alembic_cfg.set_main_option("sqlalchemy.url", target_url)
    # Print to stderr (bypasses pytest stdout capture) so CI logs always show
    # where we're migrating — silent fixture setup is impossible to debug.
    import sys

    print(f"[reset_test_schema] migrating {db_name} via alembic", file=sys.stderr)
    command.upgrade(alembic_cfg, "head")

    # Sanity check: at least one table from the latest migrations must exist.
    # If migrations silently ran against the wrong DB or got stuck on an early
    # revision, this catches it immediately instead of letting downstream tests
    # fail with cryptic "relation X does not exist" errors.
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            ).fetchall()
        }
    required = {"topics", "digests", "contents"}
    missing = required - tables
    if missing:
        raise RuntimeError(
            f"reset_test_schema: alembic upgrade head left {missing} missing "
            f"in {db_name}. Found {len(tables)} tables: {sorted(tables)}"
        )
