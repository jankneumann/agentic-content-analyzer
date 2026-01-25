"""Database connection and session management.

This module provides database connectivity through a provider abstraction,
supporting both local PostgreSQL and Supabase cloud deployments.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings
from src.models.base import Base
from src.storage.providers import get_provider
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.storage.providers.base import DatabaseProvider

logger = get_logger(__name__)

# Global provider and engine instances
_provider: "DatabaseProvider | None" = None
_engine: Engine | None = None


def _get_provider() -> "DatabaseProvider":
    """Get or create the database provider.

    Returns:
        The configured database provider instance
    """
    global _provider
    if _provider is None:
        _provider = get_provider(
            database_url=settings.get_effective_database_url(),
            provider_override=settings.database_provider,
            supabase_project_ref=settings.supabase_project_ref,
            supabase_db_password=settings.supabase_db_password,
            supabase_region=settings.supabase_region,
            supabase_pooler_mode=settings.supabase_pooler_mode,
            supabase_az=settings.supabase_az,
        )
        logger.info(f"Database provider initialized: {_provider.name}")
    return _provider


def _get_engine() -> Engine:
    """Get or create the SQLAlchemy engine.

    Creates an engine configured with provider-specific options
    for connection pooling, SSL, timeouts, etc.

    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    if _engine is None:
        provider = _get_provider()
        engine_url = provider.get_engine_url()
        engine_options = provider.get_engine_options()

        logger.info(f"Creating database engine for provider: {provider.name}")
        logger.debug(f"Engine options: {list(engine_options.keys())}")

        _engine = create_engine(engine_url, **engine_options)
    return _engine


# Lazy engine initialization - don't create at import time
def get_engine() -> Engine:
    """Get the SQLAlchemy engine.

    Returns:
        The configured SQLAlchemy Engine instance
    """
    return _get_engine()


# For backward compatibility, create engine lazily via property access
class _LazyEngine:
    """Lazy engine wrapper for backward compatibility."""

    def __getattr__(self, name: str) -> Any:
        return getattr(_get_engine(), name)


# This provides backward compatibility with code that imports `engine` directly
engine = _LazyEngine()  # type: ignore[assignment]


def _create_session_factory() -> sessionmaker[Session]:
    """Create the session factory bound to the current engine.

    Returns:
        Configured sessionmaker instance
    """
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_get_engine(),
        # expire_on_commit=False prevents DetachedInstanceError when accessing objects
        # after session.commit() - objects remain usable even after commit/session close
        expire_on_commit=False,
    )


# Lazy session factory
_session_factory: sessionmaker[Session] | None = None


def _get_session_factory() -> sessionmaker[Session]:
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = _create_session_factory()
    return _session_factory


# Backward compatibility alias
SessionLocal = property(lambda self: _get_session_factory())


def init_db() -> None:
    """Initialize database tables."""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=_get_engine())
    logger.info("Database tables created successfully")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get database session context manager."""
    db = _get_session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """Get a database session (for dependency injection)."""
    return _get_session_factory()()


def health_check() -> bool:
    """Check database connectivity.

    Returns:
        True if database is accessible, False otherwise
    """
    provider = _get_provider()
    return provider.health_check(_get_engine())


def get_provider_name() -> str:
    """Get the name of the current database provider.

    Returns:
        Provider name ("local" or "supabase")
    """
    return _get_provider().name


def reset_connection() -> None:
    """Reset database connection.

    Useful for testing or when connection parameters change.
    Disposes the existing engine and clears cached instances.
    """
    global _provider, _engine, _session_factory, _queue_engine

    if _engine is not None:
        _engine.dispose()
        logger.info("Database engine disposed")

    if _queue_engine is not None:
        _queue_engine.dispose()
        logger.info("Queue engine disposed")

    _provider = None
    _engine = None
    _session_factory = None
    _queue_engine = None
    logger.info("Database connection reset")


# Queue-specific connection management
_queue_engine: Engine | None = None


def get_queue_connection_string() -> str:
    """Get the connection URL for queue workers.

    Queue workers need direct connections (not pooled) because:
    - Long-lived processes exhaust pooler limits
    - LISTEN/NOTIFY requires direct connections
    - Workers should not compete with web request pool

    Returns:
        Direct connection URL suitable for queue workers
    """
    provider = _get_provider()
    return provider.get_queue_url()


def get_queue_engine() -> Engine:
    """Get or create the SQLAlchemy engine for queue workers.

    Creates an engine with configuration optimized for background
    job processing - larger pools, longer timeouts, etc.

    Returns:
        SQLAlchemy Engine instance for queue workers
    """
    global _queue_engine
    if _queue_engine is None:
        provider = _get_provider()
        queue_url = provider.get_queue_url()
        queue_options = provider.get_queue_options()

        logger.info(f"Creating queue engine for provider: {provider.name}")
        logger.debug(f"Queue engine options: {list(queue_options.keys())}")

        _queue_engine = create_engine(queue_url, **queue_options)
    return _queue_engine


def supports_pg_cron() -> bool:
    """Check if the current provider supports pg_cron extension.

    pg_cron enables scheduled jobs to run directly in the database,
    independent of application worker uptime.

    Returns:
        True if pg_cron is available, False otherwise
    """
    provider = _get_provider()
    return provider.supports_pg_cron()
