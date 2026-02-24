"""API tests for notification event endpoints.

Tests cover:
- Event listing with pagination and filtering (type, since)
- Unread count
- Marking events as read (single and batch)
- Device registration (create, upsert, list, delete)
- Error handling (404, 400 for invalid IDs and params)
"""

import uuid
from datetime import UTC, datetime, timedelta

from src.models.notification import (
    DeviceRegistration,
    NotificationEvent,
    NotificationEventType,
)

# ============================================================================
# Event List Tests
# ============================================================================


class TestListEvents:
    """Test GET /api/v1/notifications/events."""

    def test_list_events_empty(self, client):
        """Returns empty list when no events exist."""
        resp = client.get("/api/v1/notifications/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 50

    def test_list_events(self, client, db_session):
        """Returns events ordered by created_at desc."""
        now = datetime.now(UTC)
        older = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.BATCH_SUMMARY,
            title="Older event",
            summary="First event",
            payload={"count": 1},
            read=False,
            created_at=now - timedelta(hours=2),
        )
        newer = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.DIGEST_CREATION,
            title="Newer event",
            summary="Second event",
            payload={"count": 2},
            read=True,
            created_at=now - timedelta(hours=1),
        )
        db_session.add_all([older, newer])
        db_session.commit()

        resp = client.get("/api/v1/notifications/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["events"]) == 2
        # Newest first
        assert data["events"][0]["title"] == "Newer event"
        assert data["events"][1]["title"] == "Older event"
        # Verify field shapes
        event = data["events"][0]
        assert event["event_type"] == "digest_creation"
        assert event["summary"] == "Second event"
        assert event["payload"] == {"count": 2}
        assert event["read"] is True
        # id is a string UUID
        uuid.UUID(event["id"])

    def test_list_events_pagination(self, client, db_session):
        """Tests page and page_size query params."""
        now = datetime.now(UTC)
        events = []
        for i in range(5):
            events.append(
                NotificationEvent(
                    id=uuid.uuid4(),
                    event_type=NotificationEventType.BATCH_SUMMARY,
                    title=f"Event {i}",
                    payload={},
                    created_at=now - timedelta(minutes=5 - i),
                )
            )
        db_session.add_all(events)
        db_session.commit()

        # Page 1, size 2
        resp = client.get("/api/v1/notifications/events?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["events"]) == 2
        # Most recent first (Event 4, Event 3)
        assert data["events"][0]["title"] == "Event 4"
        assert data["events"][1]["title"] == "Event 3"

        # Page 2, size 2
        resp = client.get("/api/v1/notifications/events?page=2&page_size=2")
        data = resp.json()
        assert len(data["events"]) == 2
        assert data["events"][0]["title"] == "Event 2"
        assert data["events"][1]["title"] == "Event 1"

        # Page 3, size 2 (only 1 remaining)
        resp = client.get("/api/v1/notifications/events?page=3&page_size=2")
        data = resp.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["title"] == "Event 0"

    def test_list_events_filter_by_type(self, client, db_session):
        """Tests type query param filtering."""
        now = datetime.now(UTC)
        e1 = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.JOB_FAILURE,
            title="Job failed",
            payload={"job_id": "123"},
            created_at=now,
        )
        e2 = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.DIGEST_CREATION,
            title="Digest created",
            payload={},
            created_at=now - timedelta(minutes=1),
        )
        e3 = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.JOB_FAILURE,
            title="Another failure",
            payload={"job_id": "456"},
            created_at=now - timedelta(minutes=2),
        )
        db_session.add_all([e1, e2, e3])
        db_session.commit()

        resp = client.get("/api/v1/notifications/events?type=job_failure")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["events"]) == 2
        assert all(e["event_type"] == "job_failure" for e in data["events"])

    def test_list_events_filter_invalid_type(self, client):
        """Returns 400 for an unrecognized event type."""
        resp = client.get("/api/v1/notifications/events?type=nonexistent_type")
        assert resp.status_code == 400
        assert "Invalid event type" in resp.json()["detail"]

    def test_list_events_filter_by_since(self, client, db_session):
        """Tests since query param filtering."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=1)

        old_event = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.BATCH_SUMMARY,
            title="Old event",
            payload={},
            created_at=now - timedelta(hours=2),
        )
        new_event = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.BATCH_SUMMARY,
            title="New event",
            payload={},
            created_at=now,
        )
        db_session.add_all([old_event, new_event])
        db_session.commit()

        since_iso = cutoff.isoformat()
        resp = client.get("/api/v1/notifications/events", params={"since": since_iso})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["events"][0]["title"] == "New event"

    def test_list_events_filter_since_invalid(self, client):
        """Returns 400 for an invalid since timestamp."""
        resp = client.get("/api/v1/notifications/events?since=not-a-date")
        assert resp.status_code == 400
        assert "Invalid 'since' timestamp" in resp.json()["detail"]


# ============================================================================
# Unread Count Tests
# ============================================================================


class TestUnreadCount:
    """Test GET /api/v1/notifications/unread-count."""

    def test_unread_count_zero(self, client):
        """Returns count 0 when no events exist."""
        resp = client.get("/api/v1/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_unread_count(self, client, db_session):
        """Counts only unread events."""
        now = datetime.now(UTC)
        unread1 = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.BATCH_SUMMARY,
            title="Unread 1",
            payload={},
            read=False,
            created_at=now,
        )
        unread2 = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.THEME_ANALYSIS,
            title="Unread 2",
            payload={},
            read=False,
            created_at=now - timedelta(minutes=1),
        )
        read_event = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.DIGEST_CREATION,
            title="Already read",
            payload={},
            read=True,
            created_at=now - timedelta(minutes=2),
        )
        db_session.add_all([unread1, unread2, read_event])
        db_session.commit()

        resp = client.get("/api/v1/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["count"] == 2


# ============================================================================
# Mark Read Tests
# ============================================================================


class TestMarkEventRead:
    """Test PUT /api/v1/notifications/events/{event_id}/read."""

    def test_mark_event_read(self, client, db_session):
        """Sets read=True on the specified event."""
        event_id = uuid.uuid4()
        event = NotificationEvent(
            id=event_id,
            event_type=NotificationEventType.PIPELINE_COMPLETION,
            title="Pipeline done",
            payload={"duration_s": 120},
            read=False,
            created_at=datetime.now(UTC),
        )
        db_session.add(event)
        db_session.commit()

        resp = client.put(f"/api/v1/notifications/events/{event_id}/read")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Verify in DB
        db_session.refresh(event)
        assert event.read is True

    def test_mark_event_read_not_found(self, client):
        """Returns 404 for a nonexistent event ID."""
        fake_id = uuid.uuid4()
        resp = client.put(f"/api/v1/notifications/events/{fake_id}/read")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_mark_event_read_invalid_id(self, client):
        """Returns 400 for a malformed UUID."""
        resp = client.put("/api/v1/notifications/events/not-a-uuid/read")
        assert resp.status_code == 400
        assert "Invalid event ID" in resp.json()["detail"]


# ============================================================================
# Mark All Read Tests
# ============================================================================


class TestMarkAllRead:
    """Test PUT /api/v1/notifications/events/read-all."""

    def test_mark_all_read(self, client, db_session):
        """Updates all unread events to read."""
        now = datetime.now(UTC)
        unread1 = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.BATCH_SUMMARY,
            title="Unread A",
            payload={},
            read=False,
            created_at=now,
        )
        unread2 = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.AUDIO_GENERATION,
            title="Unread B",
            payload={},
            read=False,
            created_at=now - timedelta(minutes=1),
        )
        already_read = NotificationEvent(
            id=uuid.uuid4(),
            event_type=NotificationEventType.SCRIPT_GENERATION,
            title="Already read",
            payload={},
            read=True,
            created_at=now - timedelta(minutes=2),
        )
        db_session.add_all([unread1, unread2, already_read])
        db_session.commit()

        resp = client.put("/api/v1/notifications/events/read-all")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["marked_read"] == 2

        # Verify all are now read
        db_session.refresh(unread1)
        db_session.refresh(unread2)
        db_session.refresh(already_read)
        assert unread1.read is True
        assert unread2.read is True
        assert already_read.read is True

    def test_mark_all_read_none_unread(self, client):
        """Returns marked_read=0 when no unread events exist."""
        resp = client.put("/api/v1/notifications/events/read-all")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["marked_read"] == 0


# ============================================================================
# Device Registration Tests
# ============================================================================


class TestDeviceRegistration:
    """Test device registration CRUD endpoints."""

    def test_register_device(self, client):
        """POST /devices creates a new device registration."""
        resp = client.post(
            "/api/v1/notifications/devices",
            json={
                "platform": "web",
                "token": "test-token-abc",
                "delivery_method": "sse",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["platform"] == "web"
        assert data["token"] == "test-token-abc"
        assert data["delivery_method"] == "sse"
        # id is a valid UUID string
        uuid.UUID(data["id"])
        # timestamps are ISO strings
        assert data["created_at"] != ""
        assert data["last_seen"] != ""

    def test_register_device_upsert(self, client, db_session):
        """POST /devices with existing token updates instead of creating duplicate."""
        token = f"upsert-token-{uuid.uuid4().hex[:8]}"

        # First registration
        resp1 = client.post(
            "/api/v1/notifications/devices",
            json={
                "platform": "ios",
                "token": token,
                "delivery_method": "push",
            },
        )
        assert resp1.status_code == 200
        first_id = resp1.json()["id"]
        first_last_seen = resp1.json()["last_seen"]

        # Second registration with same token, different platform
        resp2 = client.post(
            "/api/v1/notifications/devices",
            json={
                "platform": "android",
                "token": token,
                "delivery_method": "sse",
            },
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        # Same device (same ID)
        assert data2["id"] == first_id
        # Updated fields
        assert data2["platform"] == "android"
        assert data2["delivery_method"] == "sse"
        # last_seen should be updated (or at least not earlier)
        assert data2["last_seen"] >= first_last_seen

    def test_list_devices(self, client, db_session):
        """GET /devices returns all registered devices."""
        now = datetime.now(UTC)
        d1 = DeviceRegistration(
            id=uuid.uuid4(),
            platform="web",
            token="list-token-1",
            delivery_method="sse",
            created_at=now,
            last_seen=now,
        )
        d2 = DeviceRegistration(
            id=uuid.uuid4(),
            platform="ios",
            token="list-token-2",
            delivery_method="push",
            created_at=now - timedelta(minutes=5),
            last_seen=now - timedelta(minutes=5),
        )
        db_session.add_all([d1, d2])
        db_session.commit()

        resp = client.get("/api/v1/notifications/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Ordered by last_seen desc
        assert data[0]["token"] == "list-token-1"
        assert data[1]["token"] == "list-token-2"

    def test_list_devices_empty(self, client):
        """GET /devices returns empty list when none registered."""
        resp = client.get("/api/v1/notifications/devices")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unregister_device(self, client, db_session):
        """DELETE /devices/{device_id} removes the device."""
        device_id = uuid.uuid4()
        device = DeviceRegistration(
            id=device_id,
            platform="desktop",
            token="delete-me-token",
            delivery_method="sse",
            created_at=datetime.now(UTC),
            last_seen=datetime.now(UTC),
        )
        db_session.add(device)
        db_session.commit()

        resp = client.delete(f"/api/v1/notifications/devices/{device_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Verify gone from DB
        remaining = (
            db_session.query(DeviceRegistration).filter(DeviceRegistration.id == device_id).first()
        )
        assert remaining is None

    def test_unregister_device_not_found(self, client):
        """DELETE /devices/{device_id} returns 404 for unknown device."""
        fake_id = uuid.uuid4()
        resp = client.delete(f"/api/v1/notifications/devices/{fake_id}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_unregister_device_invalid_id(self, client):
        """DELETE /devices/{device_id} returns 400 for malformed UUID."""
        resp = client.delete("/api/v1/notifications/devices/not-a-uuid")
        assert resp.status_code == 400
        assert "Invalid device ID" in resp.json()["detail"]
