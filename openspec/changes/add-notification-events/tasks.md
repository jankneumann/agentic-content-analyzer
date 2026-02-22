## 1. Database Schema

- [ ] 1.1 Create Alembic migration for `notification_events` table (id UUID, event_type varchar indexed, title varchar, summary text, payload JSONB, read boolean, created_at timestamp indexed)
- [ ] 1.2 Create Alembic migration for `device_registrations` table (id UUID, platform varchar, token varchar unique, delivery_method varchar, created_at timestamp, last_seen timestamp)
- [ ] 1.3 Create SQLAlchemy models for `NotificationEvent` and `DeviceRegistration`

## 2. Event Types and Dispatch Service

- [ ] 2.1 Create `src/services/notification_service.py` with `NotificationEventType` enum (batch_summary, theme_analysis, digest_creation, script_generation, audio_generation, pipeline_completion, job_failure)
- [ ] 2.2 Implement `NotificationDispatcher` class with `emit(event_type, title, summary, payload)` method
- [ ] 2.3 Implement database persistence of events in the dispatcher
- [ ] 2.4 Implement in-process pub/sub for pushing events to connected SSE clients
- [ ] 2.5 Add notification preference checking — skip delivery (not storage) for disabled event types

## 3. Job Handler Integration

- [ ] 3.1 Integrate dispatcher into batch summarization completion handler
- [ ] 3.2 Integrate dispatcher into theme analysis completion handler
- [ ] 3.3 Integrate dispatcher into digest creation completion handler
- [ ] 3.4 Integrate dispatcher into podcast script generation completion handler
- [ ] 3.5 Integrate dispatcher into audio generation (podcast + audio digest) completion handler
- [ ] 3.6 Integrate dispatcher into pipeline completion handler
- [ ] 3.7 Integrate dispatcher into job failure handler (all job types)

## 4. Notification Event API

- [ ] 4.1 Create `src/api/notification_routes.py` with route prefix `/api/v1/notifications`
- [ ] 4.2 Implement `GET /events` — list recent events (pagination, type filter, since filter)
- [ ] 4.3 Implement `GET /unread-count` — return unread event count
- [ ] 4.4 Implement `PUT /events/{id}/read` — mark single event as read
- [ ] 4.5 Implement `PUT /events/read-all` — mark all events as read
- [ ] 4.6 Add `X-Admin-Key` authentication to all notification endpoints
- [ ] 4.7 Register notification routes in `src/api/app.py`

## 5. SSE Event Stream

- [ ] 5.1 Implement `GET /notifications/stream` SSE endpoint with `X-Admin-Key` auth via query param
- [ ] 5.2 Wire dispatcher pub/sub to push events to connected SSE clients
- [ ] 5.3 Implement `Last-Event-ID` reconnection support (send missed events)
- [ ] 5.4 Add 30-second heartbeat (`: ping` comment) to keep connections alive

## 6. Device Registration API

- [ ] 6.1 Implement `POST /notifications/devices` — register device (platform, token, delivery_method)
- [ ] 6.2 Implement `DELETE /notifications/devices/{id}` — unregister device
- [ ] 6.3 Implement `GET /notifications/devices` — list registered devices
- [ ] 6.4 Add upsert logic (update existing registration if platform+token matches)

## 7. Notification Preferences

- [ ] 7.1 Add notification preference defaults (all event types enabled) using `notification.*` settings namespace
- [ ] 7.2 Extend voice settings routes (or create notification settings routes) with `GET /settings/notifications` returning per-type preferences with source badges
- [ ] 7.3 Add `PUT /settings/notifications/{event_type}` to set per-type preference
- [ ] 7.4 Add `DELETE /settings/notifications/{event_type}` to reset per-type preference

## 8. Event Cleanup

- [ ] 8.1 Add `aca manage cleanup-notifications --older-than <duration>` CLI command
- [ ] 8.2 Add auto-cleanup on startup (delete events older than 90 days)

## 9. Frontend — Notification Bell

- [ ] 9.1 Create `web/src/components/notifications/NotificationBell.tsx` with bell icon and unread badge
- [ ] 9.2 Create `web/src/components/notifications/NotificationDropdown.tsx` with recent events list
- [ ] 9.3 Add notification bell to app header (`AppShell.tsx`)
- [ ] 9.4 Create `web/src/hooks/use-notifications.ts` with React Query hooks for events, unread count, and SSE subscription
- [ ] 9.5 Add SSE client (EventSource) for real-time badge updates
- [ ] 9.6 Implement click-to-navigate for events in dropdown (route to digest/script/audio/job based on payload URL)
- [ ] 9.7 Add "Mark all as read" button in dropdown

## 10. Frontend — Notification Preferences

- [ ] 10.1 Add Notifications section to Settings page with per-event-type toggles
- [ ] 10.2 Wire toggles to notification preferences API
- [ ] 10.3 Add source badges (env/db/default) for each preference
- [ ] 10.4 Add event type descriptions next to each toggle

## 11. Testing

- [ ] 11.1 Add unit tests for `NotificationDispatcher` (emit, preference filtering, pub/sub)
- [ ] 11.2 Add API tests for notification event endpoints (list, filter, mark read, unread count)
- [ ] 11.3 Add API tests for device registration endpoints (register, unregister, list, upsert)
- [ ] 11.4 Add API tests for notification preferences endpoints
- [ ] 11.5 Add E2E tests for notification bell rendering and badge count
- [ ] 11.6 Add E2E tests for notification dropdown (event list, click navigation, mark all read)
- [ ] 11.7 Add E2E tests for notification preferences toggles in settings
