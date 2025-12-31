"""Database connection and session management."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings
from src.models.newsletter import Base
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Create engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before using
    echo=False,  # Disable echo - use logging configuration instead
)

# Create session factory
# expire_on_commit=False prevents DetachedInstanceError when accessing objects
# after session.commit() - objects remain usable even after commit/session close
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def init_db() -> None:
    """Initialize database tables."""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get database session context manager."""
    db = SessionLocal()
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
    return SessionLocal()
