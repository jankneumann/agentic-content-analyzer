## Why

The `add-capacitor-mobile` and `add-tauri-desktop` proposals both define identical backend notification infrastructure — event type enums, a dispatch service, job handler integration, device registration, and per-event-type preferences. This duplicated backend work should live in a single shared proposal that defines the notification event system once. Native delivery layers (push notifications on Capacitor, desktop notifications on Tauri, and potentially Web Notifications for PWA) become thin consumers of this shared backend.

## What Changes

- Define a notification event types enum covering all backend pipeline completion events (batch summary, theme analysis, digest creation, script generation, audio generation, pipeline completion, job failure)
- Create a backend notification dispatch service that emits events when jobs complete
- Add a notification event API for clients to query recent events and subscribe via SSE or polling
- Add device/client registration endpoint for push notification tokens and delivery preferences
- Add a notification preferences API and UI for per-event-type enable/disable
- Integrate the dispatch service into all existing job completion handlers (summarization, theme analysis, digest, script, podcast/audio)
- Store notification events in the database for history and retry

## Capabilities

### New Capabilities
- `notification-events`: Backend notification event system with event types, dispatch service, client registration, delivery preferences, and event history API

### Modified Capabilities
- `settings-management`: Add notification preferences (per-event-type enable/disable) to the settings page

## Impact

- **Backend**: New notification dispatch service, event model, device registration table, preferences API, SSE endpoint
- **Frontend**: Notification preferences UI in settings, event indicator (bell icon with badge)
- **Dependencies**: None new — uses existing FastAPI SSE support and database
- **APIs**: New endpoints for event history, device registration, notification preferences, and SSE stream
- **Database**: New tables for notification events and device registrations
- **Existing job handlers**: Minor integration points — emit events on completion/failure
- **Capacitor/Tauri**: Become consumers — they subscribe to the event API and deliver via native channels
