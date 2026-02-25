"""Notification event cleanup service.

Provides auto-cleanup on startup and CLI-invoked cleanup for old events.
"""

from datetime import UTC, datetime, timedelta

from src.models.notification import NotificationEvent
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Default auto-cleanup threshold (days)
AUTO_CLEANUP_DAYS = 90


def cleanup_notifications(older_than_days: int) -> int:
    """Delete notification events older than the specified number of days.

    Args:
        older_than_days: Delete events older than this many days.

    Returns:
        Number of deleted events.
    """
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)

    with get_db() as db:
        count = db.query(NotificationEvent).filter(NotificationEvent.created_at < cutoff).delete()
        db.commit()

    if count > 0:
        logger.info(f"Cleaned up {count} notification events older than {older_than_days} days")
    return count


def auto_cleanup_notifications() -> int:
    """Auto-cleanup old notification events on startup.

    Deletes events older than AUTO_CLEANUP_DAYS (90 days).
    """
    return cleanup_notifications(AUTO_CLEANUP_DAYS)
