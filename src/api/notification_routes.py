"""Notification event API routes.

Provides endpoints for:
- Listing and filtering notification events
- Marking events as read
- Real-time event delivery via SSE
- Device registration for push notifications
- Unread count
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, func

from src.api.dependencies import verify_admin_key
from src.models.notification import (
    DeviceRegistration,
    NotificationEvent,
    NotificationEventType,
)
from src.services.notification_service import subscribe, unsubscribe
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# ============================================================================
# Response / Request Models
# ============================================================================


class NotificationEventResponse(BaseModel):
    """Single notification event."""

    id: str
    event_type: str
    title: str
    summary: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    read: bool = False
    created_at: str


class NotificationEventListResponse(BaseModel):
    """Paginated list of notification events."""

    events: list[NotificationEventResponse]
    total: int
    page: int
    page_size: int


class UnreadCountResponse(BaseModel):
    """Unread notification count."""

    count: int


class DeviceRegistrationRequest(BaseModel):
    """Request to register a device."""

    platform: str = Field(..., min_length=1, max_length=50)
    token: str = Field(..., min_length=1, max_length=500)
    delivery_method: str = Field(default="sse", max_length=50)


class DeviceRegistrationResponse(BaseModel):
    """Registered device."""

    id: str
    platform: str
    token: str
    delivery_method: str
    created_at: str
    last_seen: str


# ============================================================================
# Event Endpoints
# ============================================================================


@router.get(
    "/events",
    response_model=NotificationEventListResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    type: str | None = Query(None, alias="type"),
    since: str | None = Query(None),
) -> NotificationEventListResponse:
    """List recent notification events with optional filtering."""
    with get_db() as db:
        query = db.query(NotificationEvent)

        if type:
            # Validate event type
            valid_types = [e.value for e in NotificationEventType]
            if type not in valid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid event type: {type}. Valid types: {valid_types}",
                )
            query = query.filter(NotificationEvent.event_type == type)

        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid 'since' timestamp. Use ISO-8601 format.",
                )
            query = query.filter(NotificationEvent.created_at > since_dt)

        total = query.count()
        events = (
            query.order_by(desc(NotificationEvent.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return NotificationEventListResponse(
            events=[
                NotificationEventResponse(
                    id=str(e.id),
                    event_type=e.event_type,
                    title=e.title,
                    summary=e.summary,
                    payload=e.payload or {},
                    read=e.read,
                    created_at=e.created_at.isoformat() if e.created_at else "",
                )
                for e in events
            ],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def get_unread_count() -> UnreadCountResponse:
    """Get the count of unread notification events."""
    with get_db() as db:
        count = (
            db.query(func.count(NotificationEvent.id))
            .filter(NotificationEvent.read == False)  # noqa: E712
            .scalar()
        ) or 0
        return UnreadCountResponse(count=count)


@router.put(
    "/events/{event_id}/read",
    dependencies=[Depends(verify_admin_key)],
)
async def mark_event_read(
    event_id: str = Path(...),
) -> dict[str, str]:
    """Mark a single notification event as read."""
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event ID format")

    with get_db() as db:
        event = db.query(NotificationEvent).filter(NotificationEvent.id == event_uuid).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        event.read = True
        db.commit()
        return {"status": "ok"}


@router.put(
    "/events/read-all",
    dependencies=[Depends(verify_admin_key)],
)
async def mark_all_events_read() -> dict[str, Any]:
    """Mark all unread notification events as read."""
    with get_db() as db:
        count = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.read == False)  # noqa: E712
            .update({"read": True})
        )
        db.commit()
        return {"status": "ok", "marked_read": count}


# ============================================================================
# SSE Stream
# ============================================================================


@router.get("/stream", dependencies=[Depends(verify_admin_key)])
async def event_stream(
    request: Request,
) -> StreamingResponse:
    """Server-Sent Events endpoint for real-time notification delivery.

    Auth: handled by AuthMiddleware (session cookie) + verify_admin_key
    (defense-in-depth). Browser EventSource sends cookies via
    withCredentials:true so cookie-based auth works automatically.

    Supports Last-Event-ID for reconnection.
    """
    # Check for Last-Event-ID for reconnection support
    last_event_id = request.headers.get("Last-Event-ID")

    async def generate():
        queue = subscribe()
        try:
            # Send missed events if reconnecting
            if last_event_id:
                try:
                    last_uuid = uuid.UUID(last_event_id)
                    with get_db() as db:
                        # Find the timestamp of the last received event
                        last_event = (
                            db.query(NotificationEvent)
                            .filter(NotificationEvent.id == last_uuid)
                            .first()
                        )
                        if last_event:
                            missed = (
                                db.query(NotificationEvent)
                                .filter(NotificationEvent.created_at > last_event.created_at)
                                .order_by(NotificationEvent.created_at)
                                .all()
                            )
                            for event in missed:
                                event_data = {
                                    "id": str(event.id),
                                    "event_type": event.event_type,
                                    "title": event.title,
                                    "summary": event.summary,
                                    "payload": event.payload or {},
                                    "read": event.read,
                                    "created_at": event.created_at.isoformat()
                                    if event.created_at
                                    else "",
                                }
                                yield f"id: {event.id}\nevent: notification\ndata: {json.dumps(event_data)}\n\n"
                except Exception:
                    logger.debug("Invalid Last-Event-ID, skipping replay", exc_info=True)

            # Stream new events with heartbeat
            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"id: {event['id']}\nevent: notification\ndata: {json.dumps(event)}\n\n"
                except TimeoutError:
                    # Send heartbeat
                    yield ": ping\n\n"

        finally:
            unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# Device Registration Endpoints
# ============================================================================


@router.post(
    "/devices",
    response_model=DeviceRegistrationResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def register_device(
    request: DeviceRegistrationRequest,
) -> DeviceRegistrationResponse:
    """Register a device for push notification delivery.

    Uses upsert logic: if platform+token already exists, updates last_seen.
    """
    with get_db() as db:
        # Check for existing registration
        existing = (
            db.query(DeviceRegistration).filter(DeviceRegistration.token == request.token).first()
        )

        if existing:
            existing.platform = request.platform
            existing.delivery_method = request.delivery_method
            existing.last_seen = datetime.now(UTC)
            db.commit()
            db.refresh(existing)
            device = existing
        else:
            device = DeviceRegistration(
                platform=request.platform,
                token=request.token,
                delivery_method=request.delivery_method,
            )
            db.add(device)
            db.commit()
            db.refresh(device)

        return DeviceRegistrationResponse(
            id=str(device.id),
            platform=device.platform,
            token=device.token,
            delivery_method=device.delivery_method,
            created_at=device.created_at.isoformat() if device.created_at else "",
            last_seen=device.last_seen.isoformat() if device.last_seen else "",
        )


@router.get(
    "/devices",
    response_model=list[DeviceRegistrationResponse],
    dependencies=[Depends(verify_admin_key)],
)
async def list_devices() -> list[DeviceRegistrationResponse]:
    """List all registered devices."""
    with get_db() as db:
        devices = db.query(DeviceRegistration).order_by(DeviceRegistration.last_seen.desc()).all()
        return [
            DeviceRegistrationResponse(
                id=str(d.id),
                platform=d.platform,
                token=d.token,
                delivery_method=d.delivery_method,
                created_at=d.created_at.isoformat() if d.created_at else "",
                last_seen=d.last_seen.isoformat() if d.last_seen else "",
            )
            for d in devices
        ]


@router.delete(
    "/devices/{device_id}",
    dependencies=[Depends(verify_admin_key)],
)
async def unregister_device(
    device_id: str = Path(...),
) -> dict[str, str]:
    """Unregister a device."""
    try:
        device_uuid = uuid.UUID(device_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid device ID format")

    with get_db() as db:
        device = db.query(DeviceRegistration).filter(DeviceRegistration.id == device_uuid).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        db.delete(device)
        db.commit()
        return {"status": "ok"}
