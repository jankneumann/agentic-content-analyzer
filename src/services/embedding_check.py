"""Embedding configuration mismatch detection.

Provides a startup check to warn if the configured embedding provider/model
doesn't match what's stored in the database. This catches configuration
drift after provider switches or mismatched deployments.

Usage (in API startup):
    check_embedding_config_mismatch(db)
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def check_embedding_config_mismatch(db: Session) -> dict | None:
    """Check if configured embedding provider/model matches database state.

    Queries DISTINCT embedding_provider/model from document_chunks and
    compares against the current Settings. Returns mismatch info if found.

    This is a non-blocking, warn-only check — wrapped in try/except.

    Args:
        db: SQLAlchemy session

    Returns:
        Dict with mismatch details if found, None if config matches or
        no embeddings exist yet.
    """
    try:
        settings = get_settings()

        result = db.execute(
            text("""
                SELECT DISTINCT embedding_provider, embedding_model
                FROM document_chunks
                WHERE embedding IS NOT NULL
                  AND embedding_provider IS NOT NULL
                  AND embedding_provider != 'unknown'
            """)
        )
        rows = list(result)

        if not rows:
            return None

        db_providers = {(row.embedding_provider, row.embedding_model) for row in rows}
        current = (settings.embedding_provider, settings.embedding_model)

        if len(db_providers) == 1 and current in db_providers:
            return None

        mismatch = {
            "configured": {"provider": current[0], "model": current[1]},
            "in_database": [{"provider": p, "model": m} for p, m in sorted(db_providers)],
        }

        if current not in db_providers:
            logger.warning(
                f"Embedding config mismatch: configured {current[0]}/{current[1]} "
                f"but database contains embeddings from: "
                f"{', '.join(f'{p}/{m}' for p, m in sorted(db_providers))}. "
                f"Run 'aca manage switch-embeddings' to migrate."
            )
        elif len(db_providers) > 1:
            logger.warning(
                f"Mixed embedding providers in database: "
                f"{', '.join(f'{p}/{m}' for p, m in sorted(db_providers))}. "
                f"Run 'aca manage switch-embeddings' to normalize."
            )

        return mismatch

    except Exception:
        logger.debug(
            "Embedding config mismatch check failed (non-blocking)",
            exc_info=True,
        )
        return None
