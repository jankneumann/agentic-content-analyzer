"""Notification event and device registration models.

Supports the notification event system: backend events emitted on job
completion/failure, stored for history, and delivered via SSE to clients.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.models.base import Base


class NotificationEventType(StrEnum):
    """Types of notification events emitted by the pipeline."""

    BATCH_SUMMARY = "batch_summary"
    THEME_ANALYSIS = "theme_analysis"
    DIGEST_CREATION = "digest_creation"
    SCRIPT_GENERATION = "script_generation"
    AUDIO_GENERATION = "audio_generation"
    PIPELINE_COMPLETION = "pipeline_completion"
    JOB_FAILURE = "job_failure"


class NotificationEvent(Base):
    """A notification event emitted by the pipeline.

    Events are stored for history, delivered via SSE to connected clients,
    and queryable via the notification API.
    """

    __tablename__ = "notification_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    payload = Column(JSONB, nullable=False, default=dict)
    read = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    def __repr__(self) -> str:
        return f"<NotificationEvent(id={self.id}, type={self.event_type!r})>"


class DeviceRegistration(Base):
    """A registered device/client for push notification delivery.

    Supports multiple platforms (iOS, Android, desktop, web) and
    delivery methods (push, SSE, polling).
    """

    __tablename__ = "device_registrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform = Column(String(50), nullable=False)
    token = Column(String(500), nullable=False, unique=True)
    delivery_method = Column(String(50), nullable=False, default="sse")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    last_seen = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<DeviceRegistration(id={self.id}, platform={self.platform!r})>"
