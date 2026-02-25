## Context

The application has a job queue (PGQueuer) for background processing — summarization batches, theme analysis, digest creation, script generation, and audio generation all run as asynchronous jobs. Currently there is no mechanism to notify clients when these jobs complete. The `add-capacitor-mobile` and `add-tauri-desktop` proposals both need this, and a PWA could use Web Notifications too.

Key existing touchpoints:
- `src/services/job_service.py` — job queue management
- `src/api/job_routes.py` — job status API (`GET /api/v1/jobs`, `GET /api/v1/jobs/{id}`)
- `src/processors/` — summarization, theme analysis, digest creation processors
- `src/delivery/tts_service.py` — audio generation
- Settings override system — 3-tier config (env → db → default)

## Goals / Non-Goals

**Goals:**
- Define a unified set of notification event types for all pipeline completion events
- Create a dispatch service that job handlers call on completion/failure
- Provide an API for clients to fetch recent events and subscribe for real-time delivery
- Support device/client registration for native push delivery
- Allow per-event-type notification preferences (enable/disable)
- Store events for history and retry on delivery failure

**Non-Goals:**
- Native push delivery (Capacitor/Tauri proposals handle their own delivery layer)
- Email notifications (separate concern, could consume events later)
- Real-time WebSocket event streaming (SSE is sufficient; WebSocket reserved for audio in `add-cloud-stt`)
- Complex event routing or fan-out (single-user app, not multi-tenant)

## Decisions

### 1. Server-Sent Events (SSE) for real-time delivery

**Choice**: Add an SSE endpoint at `GET /api/v1/notifications/stream` that pushes events to connected clients in real-time.

**Alternatives considered**:
- **WebSocket**: Bidirectional, but unnecessary — events flow one way (server → client). Also, WebSocket is already used by `add-cloud-stt` for audio streaming; SSE avoids protocol conflicts.
- **Polling**: Simple but adds latency and unnecessary requests. SSE is equally simple with real-time delivery.
- **Push-only (no API)**: Doesn't work for PWA/web clients without push registration.

**Rationale**: SSE is the simplest real-time server → client protocol. FastAPI supports it natively via `StreamingResponse`. Clients that can't use SSE (e.g., native apps in background) fall back to polling `GET /api/v1/notifications/events`.

### 2. Event-driven dispatch via in-process pub/sub

**Choice**: Use a simple in-process event bus (`NotificationDispatcher`) that job handlers call directly. The dispatcher writes to the database and pushes to any connected SSE clients.

**Alternatives considered**:
- **Redis Pub/Sub**: Adds infrastructure dependency for a single-user app. Overkill.
- **Celery signals**: Ties notification dispatch to the task queue framework. Fragile if queue implementation changes.
- **Database polling**: Simple but adds latency. The dispatcher writes to DB *and* pushes to SSE simultaneously.

**Rationale**: In-process dispatch is the simplest pattern for a single-user app. No new infrastructure. The database provides persistence and retry; SSE provides real-time delivery. If the app scales to multi-process, Redis Pub/Sub can replace the in-process bus without changing the API.

### 3. Notification events stored in database

**Choice**: Store all notification events in a `notification_events` table with columns: `id`, `event_type`, `title`, `summary`, `payload` (JSON), `read`, `created_at`.

**Rationale**: Provides event history (bell icon with unread count), retry capability for failed deliveries, and a query API for clients that missed SSE events. Also enables the notification preferences UI to show "recent notifications" alongside the preference toggles.

### 4. Device registration as a separate table

**Choice**: Store device registrations in a `device_registrations` table with: `id`, `platform` (ios/android/desktop/web), `token` (push token or identifier), `delivery_method` (push/sse/poll), `created_at`, `last_seen`.

**Rationale**: Decouples registration from delivery. Capacitor registers with a push token, Tauri registers as a desktop client, PWA registers for Web Push. The dispatch service iterates registered devices and delivers via the appropriate channel. The `last_seen` field enables cleanup of stale registrations.

### 5. Notification preferences under `notification.*` namespace

**Choice**: Store per-event-type preferences as settings overrides with keys like `notification.batch_summary`, `notification.digest_creation`, etc. Values are `"true"` or `"false"`.

**Rationale**: Reuses the existing settings override system (3-tier precedence, env → db → default). All event types default to enabled. The settings UI renders toggles for each event type. No new settings infrastructure needed.

## Risks / Trade-offs

- **SSE connection limits**: Browsers limit concurrent SSE connections per domain (~6). → Acceptable for single-user app with 1-2 tabs.
- **Event storage growth**: Events accumulate over time. → Add a `aca manage cleanup-notifications --older-than 30d` command and auto-cleanup on startup.
- **In-process dispatch loses events on crash**: If the process crashes between job completion and event dispatch, the event is lost. → Mitigated by the job queue itself — failed jobs can be retried, and the notification is re-emitted.
- **No delivery guarantee for SSE**: If no client is connected, SSE events are dropped. → Mitigated by database persistence; clients fetch missed events on reconnect via `GET /api/v1/notifications/events?since=<timestamp>`.

## Open Questions

- Should unread count be shown in the browser tab title (e.g., "(3) ACA")? (Leaning: yes, low effort and helpful.)
- Should notification events include a deep link URL for navigation? (Leaning: yes, `payload.url` field pointing to the relevant digest/script/audio.)
