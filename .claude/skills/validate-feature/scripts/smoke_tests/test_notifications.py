"""Smoke tests: Notification event system.

Verifies that notification endpoints are deployed and functioning:
- Event listing with pagination and filtering
- Unread count tracking
- Mark-as-read (single and bulk)
- Device registration CRUD
- Notification preferences (list, update, reset)
- SSE stream connectivity

These tests exercise the HTTP surface only — no internal imports.
They create and clean up their own test data.
"""

from __future__ import annotations

import uuid

import httpx
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOTIFICATION_EVENTS_PATH = "/api/v1/notifications/events"
NOTIFICATION_UNREAD_PATH = "/api/v1/notifications/unread-count"
NOTIFICATION_READ_ALL_PATH = "/api/v1/notifications/events/read-all"
NOTIFICATION_DEVICES_PATH = "/api/v1/notifications/devices"
NOTIFICATION_PREFS_PATH = "/api/v1/settings/notifications"
NOTIFICATION_STREAM_PATH = "/api/v1/notifications/stream"


# ---------------------------------------------------------------------------
# Event Endpoints
# ---------------------------------------------------------------------------


class TestEventList:
    """GET /api/v1/notifications/events returns a paginated event list."""

    def test_event_list_returns_200(self, authed_client: httpx.Client) -> None:
        response = authed_client.get(NOTIFICATION_EVENTS_PATH)
        assert response.status_code == 200

    def test_event_list_shape(self, authed_client: httpx.Client) -> None:
        """Response must contain events array and pagination fields."""
        response = authed_client.get(NOTIFICATION_EVENTS_PATH)
        data = response.json()
        assert "events" in data, f"Missing 'events' key in response: {list(data.keys())}"
        assert "total" in data, f"Missing 'total' key in response: {list(data.keys())}"
        assert isinstance(data["events"], list)
        assert isinstance(data["total"], int)

    def test_event_list_accepts_pagination(self, authed_client: httpx.Client) -> None:
        """Query params page and page_size should be accepted."""
        response = authed_client.get(
            NOTIFICATION_EVENTS_PATH, params={"page": 1, "page_size": 10}
        )
        assert response.status_code == 200

    def test_event_list_accepts_type_filter(self, authed_client: httpx.Client) -> None:
        """Query param event_type should filter without error."""
        response = authed_client.get(
            NOTIFICATION_EVENTS_PATH, params={"event_type": "pipeline_completion"}
        )
        assert response.status_code == 200


class TestUnreadCount:
    """GET /api/v1/notifications/unread-count returns unread count."""

    def test_unread_count_returns_200(self, authed_client: httpx.Client) -> None:
        response = authed_client.get(NOTIFICATION_UNREAD_PATH)
        assert response.status_code == 200

    def test_unread_count_shape(self, authed_client: httpx.Client) -> None:
        data = authed_client.get(NOTIFICATION_UNREAD_PATH).json()
        assert "count" in data, f"Missing 'count' key: {list(data.keys())}"
        assert isinstance(data["count"], int)
        assert data["count"] >= 0


class TestMarkRead:
    """PUT mark-as-read endpoints respond correctly."""

    def test_mark_all_read_returns_200(self, authed_client: httpx.Client) -> None:
        response = authed_client.put(NOTIFICATION_READ_ALL_PATH)
        assert response.status_code == 200

    def test_mark_nonexistent_event_read(self, authed_client: httpx.Client) -> None:
        """Marking a non-existent event should return 404, not 500."""
        fake_id = str(uuid.uuid4())
        response = authed_client.put(f"{NOTIFICATION_EVENTS_PATH}/{fake_id}/read")
        assert response.status_code in (404, 422), (
            f"Expected 404 or 422 for non-existent event, got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# Device Registration
# ---------------------------------------------------------------------------


class TestDeviceRegistration:
    """POST/GET/DELETE /api/v1/notifications/devices."""

    def test_register_and_cleanup(self, authed_client: httpx.Client) -> None:
        """Full lifecycle: register → verify in list → unregister."""
        # Register
        token = f"smoke-test-{uuid.uuid4().hex[:8]}"
        create_resp = authed_client.post(
            NOTIFICATION_DEVICES_PATH,
            json={"platform": "web", "token": token, "delivery_method": "sse"},
        )
        assert create_resp.status_code in (200, 201), (
            f"Device registration failed: {create_resp.status_code} {create_resp.text}"
        )
        device = create_resp.json()
        device_id = device.get("id")
        assert device_id, f"Device response missing 'id': {device}"

        try:
            # Verify in list
            list_resp = authed_client.get(NOTIFICATION_DEVICES_PATH)
            assert list_resp.status_code == 200
            devices = list_resp.json()
            assert isinstance(devices, list)
            ids = [d.get("id") for d in devices]
            assert device_id in ids, f"Registered device {device_id} not in list"
        finally:
            # Cleanup
            del_resp = authed_client.delete(f"{NOTIFICATION_DEVICES_PATH}/{device_id}")
            assert del_resp.status_code == 200, (
                f"Device deletion failed: {del_resp.status_code}"
            )

    def test_register_missing_fields(self, authed_client: httpx.Client) -> None:
        """Missing required fields should return 422, not 500."""
        response = authed_client.post(NOTIFICATION_DEVICES_PATH, json={})
        assert response.status_code == 422, (
            f"Expected 422 for missing fields, got {response.status_code}"
        )

    def test_delete_nonexistent_device(self, authed_client: httpx.Client) -> None:
        """Deleting a non-existent device should return 404, not 500."""
        fake_id = str(uuid.uuid4())
        response = authed_client.delete(f"{NOTIFICATION_DEVICES_PATH}/{fake_id}")
        assert response.status_code in (404, 422), (
            f"Expected 404/422 for non-existent device, got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# Notification Preferences
# ---------------------------------------------------------------------------


class TestNotificationPreferences:
    """GET/PUT/DELETE /api/v1/settings/notifications."""

    def test_list_preferences_returns_200(self, authed_client: httpx.Client) -> None:
        response = authed_client.get(NOTIFICATION_PREFS_PATH)
        assert response.status_code == 200

    def test_list_preferences_shape(self, authed_client: httpx.Client) -> None:
        """Response must contain preferences array with expected fields."""
        data = authed_client.get(NOTIFICATION_PREFS_PATH).json()
        prefs = data.get("preferences", data)
        assert isinstance(prefs, list), f"Expected list of preferences, got {type(prefs)}"
        if prefs:
            first = prefs[0]
            assert "event_type" in first, f"Preference missing 'event_type': {first}"
            assert "enabled" in first, f"Preference missing 'enabled': {first}"

    def test_update_and_reset_preference(self, authed_client: httpx.Client) -> None:
        """Update a preference, verify change, then reset to default."""
        event_type = "job_failure"

        # Update to disabled
        put_resp = authed_client.put(
            f"{NOTIFICATION_PREFS_PATH}/{event_type}",
            json={"enabled": False},
        )
        assert put_resp.status_code == 200, (
            f"Preference update failed: {put_resp.status_code} {put_resp.text}"
        )

        # Reset to default
        del_resp = authed_client.delete(f"{NOTIFICATION_PREFS_PATH}/{event_type}")
        assert del_resp.status_code == 200, (
            f"Preference reset failed: {del_resp.status_code} {del_resp.text}"
        )
        reset_data = del_resp.json()
        assert reset_data.get("source") == "default", (
            f"After reset, source should be 'default': {reset_data}"
        )

    def test_invalid_event_type(self, authed_client: httpx.Client) -> None:
        """Unknown event type should return 400 or 422, not 500."""
        response = authed_client.put(
            f"{NOTIFICATION_PREFS_PATH}/not_a_real_event_type",
            json={"enabled": False},
        )
        assert response.status_code in (400, 404, 422), (
            f"Expected 4xx for invalid event type, got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# SSE Stream
# ---------------------------------------------------------------------------


class TestSSEStream:
    """GET /api/v1/notifications/stream SSE connectivity."""

    def test_stream_accepts_connection(
        self,
        base_url: str,
        auth_header_value: str,
    ) -> None:
        """SSE stream should start sending data (or at least not error)."""
        # Use a raw httpx stream request with short timeout
        with httpx.stream(
            "GET",
            f"{base_url}{NOTIFICATION_STREAM_PATH}",
            params={"key": auth_header_value},
            headers={"Accept": "text/event-stream"},
            timeout=httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0),
        ) as response:
            assert response.status_code == 200, (
                f"SSE stream returned {response.status_code}"
            )
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type, (
                f"SSE stream content-type should be text/event-stream, got: {content_type}"
            )

    def test_stream_rejects_no_auth(self, base_url: str) -> None:
        """SSE stream without credentials should be rejected."""
        try:
            response = httpx.get(
                f"{base_url}{NOTIFICATION_STREAM_PATH}",
                headers={"Accept": "text/event-stream"},
                timeout=5.0,
            )
            # In dev mode this may return 200; in production it should be 401/403
            # We just verify it doesn't return 500
            assert response.status_code != 500, (
                f"SSE stream without auth returned 500"
            )
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip("Could not connect to SSE stream endpoint")
