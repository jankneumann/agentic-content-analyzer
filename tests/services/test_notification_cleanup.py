"""Tests for notification cleanup service.

Tests cover:
- cleanup_notifications deletes old events
- auto_cleanup_notifications uses 90-day default
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from src.services.notification_cleanup import (
    AUTO_CLEANUP_DAYS,
    auto_cleanup_notifications,
    cleanup_notifications,
)


def test_cleanup_deletes_old_events():
    """cleanup_notifications deletes events older than threshold."""
    mock_session = MagicMock()
    mock_query = MagicMock()
    mock_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.delete.return_value = 5

    @contextmanager
    def mock_get_db():
        yield mock_session

    with patch("src.services.notification_cleanup.get_db", mock_get_db):
        result = cleanup_notifications(30)

    assert result == 5
    mock_session.commit.assert_called_once()


def test_cleanup_returns_zero_when_none_to_delete():
    """cleanup_notifications returns 0 when nothing to delete."""
    mock_session = MagicMock()
    mock_query = MagicMock()
    mock_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.delete.return_value = 0

    @contextmanager
    def mock_get_db():
        yield mock_session

    with patch("src.services.notification_cleanup.get_db", mock_get_db):
        result = cleanup_notifications(90)

    assert result == 0


def test_auto_cleanup_uses_90_days():
    """auto_cleanup_notifications delegates to cleanup_notifications(90)."""
    with patch("src.services.notification_cleanup.cleanup_notifications") as mock_cleanup:
        mock_cleanup.return_value = 3
        result = auto_cleanup_notifications()

    mock_cleanup.assert_called_once_with(AUTO_CLEANUP_DAYS)
    assert result == 3


def test_auto_cleanup_days_constant():
    """AUTO_CLEANUP_DAYS is 90."""
    assert AUTO_CLEANUP_DAYS == 90
