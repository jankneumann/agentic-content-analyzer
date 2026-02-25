# notification-events Specification

## Purpose
TBD - created by archiving change add-notification-events. Update Purpose after archive.
## Requirements
### Requirement: Notification Event Types
The system SHALL define a set of notification event types covering all backend pipeline completion events.

#### Scenario: Event type enum
- **WHEN** the notification system is initialized
- **THEN** the following event types SHALL be available:
  - `batch_summary` — batch summarization completed
  - `theme_analysis` — theme analysis completed
  - `digest_creation` — daily or weekly digest created
  - `script_generation` — podcast script generated
  - `audio_generation` — podcast audio or audio digest generated
  - `pipeline_completion` — full pipeline run completed
  - `job_failure` — any background job failed

#### Scenario: Event payload structure
- **WHEN** a notification event is created
- **THEN** it SHALL include: `id`, `event_type`, `title`, `summary`, `payload` (JSON with event-specific data), `read` (boolean), `created_at`
- **AND** `payload` SHALL include a `url` field for client-side navigation to the relevant content

### Requirement: Notification Dispatch Service
The system SHALL provide a dispatch service that emits notification events when jobs complete or fail.

#### Scenario: Emit event on batch summary completion
- **WHEN** a batch summarization job completes successfully
- **THEN** the dispatch service SHALL create a `batch_summary` event with the count of summarized items

#### Scenario: Emit event on theme analysis completion
- **WHEN** a theme analysis job completes successfully
- **THEN** the dispatch service SHALL create a `theme_analysis` event with the number of themes identified

#### Scenario: Emit event on digest creation
- **WHEN** a daily or weekly digest is created
- **THEN** the dispatch service SHALL create a `digest_creation` event with the digest title, type (daily/weekly), and digest ID

#### Scenario: Emit event on script generation
- **WHEN** a podcast script is generated
- **THEN** the dispatch service SHALL create a `script_generation` event with the script title and ID

#### Scenario: Emit event on audio generation
- **WHEN** a podcast audio or audio digest is generated
- **THEN** the dispatch service SHALL create an `audio_generation` event with the audio title, duration, and ID

#### Scenario: Emit event on pipeline completion
- **WHEN** a full pipeline run (ingest → summarize → digest) completes
- **THEN** the dispatch service SHALL create a `pipeline_completion` event summarizing the pipeline results

#### Scenario: Emit event on job failure
- **WHEN** any background job fails
- **THEN** the dispatch service SHALL create a `job_failure` event with the job type, job ID, and error summary

#### Scenario: Respect notification preferences
- **WHEN** a notification event is emitted
- **AND** the event type is disabled in notification preferences
- **THEN** the event SHALL be stored in the database but SHALL NOT be delivered to connected clients

#### Scenario: Write event to database
- **WHEN** a notification event is emitted
- **THEN** the event SHALL be persisted in the `notification_events` table
- **AND** the event SHALL be available via the event history API

#### Scenario: Push event to SSE clients
- **WHEN** a notification event is emitted
- **AND** the event type is enabled in preferences
- **AND** one or more SSE clients are connected
- **THEN** the event SHALL be pushed to all connected SSE clients immediately

### Requirement: Notification Event API
The system SHALL provide REST API endpoints for querying notification events, protected by admin API key.

#### Scenario: List recent events
- **WHEN** `GET /api/v1/notifications/events` is called with a valid `X-Admin-Key` header
- **THEN** the response SHALL include the most recent notification events (default limit: 50)
- **AND** events SHALL be ordered by `created_at` descending

#### Scenario: Filter events by type
- **WHEN** `GET /api/v1/notifications/events?type=digest_creation` is called
- **THEN** only events of the specified type SHALL be returned

#### Scenario: Filter events since timestamp
- **WHEN** `GET /api/v1/notifications/events?since=<ISO-8601 timestamp>` is called
- **THEN** only events created after the specified timestamp SHALL be returned

#### Scenario: Mark event as read
- **WHEN** `PUT /api/v1/notifications/events/{id}/read` is called
- **THEN** the event's `read` field SHALL be set to `true`

#### Scenario: Mark all events as read
- **WHEN** `PUT /api/v1/notifications/events/read-all` is called
- **THEN** all unread events SHALL be marked as read

#### Scenario: Get unread count
- **WHEN** `GET /api/v1/notifications/unread-count` is called
- **THEN** the response SHALL include the count of unread events

#### Scenario: Authentication required
- **WHEN** any notification event endpoint is called without a valid `X-Admin-Key` header
- **THEN** the response SHALL be 401 Unauthorized

### Requirement: SSE Event Stream
The system SHALL provide a Server-Sent Events endpoint for real-time notification delivery.

#### Scenario: Connect to event stream
- **WHEN** `GET /api/v1/notifications/stream` is called with a valid `X-Admin-Key` header (via query param `key`)
- **THEN** the server SHALL establish an SSE connection
- **AND** keep the connection open for real-time event delivery

#### Scenario: Receive event via SSE
- **WHEN** a notification event is emitted while an SSE client is connected
- **THEN** the event SHALL be sent as an SSE message with `event: notification` and JSON data

#### Scenario: SSE reconnection support
- **WHEN** an SSE client reconnects with a `Last-Event-ID` header
- **THEN** the server SHALL send all events created after the specified event ID

#### Scenario: SSE heartbeat
- **WHEN** an SSE connection is active
- **THEN** the server SHALL send a heartbeat comment (`: ping`) every 30 seconds to keep the connection alive

### Requirement: Device Registration
The system SHALL provide an endpoint for registering devices/clients for notification delivery.

#### Scenario: Register device
- **WHEN** `POST /api/v1/notifications/devices` is called with `{ "platform": "ios", "token": "push-token", "delivery_method": "push" }`
- **THEN** the device SHALL be registered in the `device_registrations` table

#### Scenario: Update existing registration
- **WHEN** a device registration is submitted with a platform+token that already exists
- **THEN** the existing registration SHALL be updated (not duplicated)
- **AND** `last_seen` SHALL be refreshed

#### Scenario: Unregister device
- **WHEN** `DELETE /api/v1/notifications/devices/{id}` is called
- **THEN** the device registration SHALL be removed

#### Scenario: List registered devices
- **WHEN** `GET /api/v1/notifications/devices` is called
- **THEN** all registered devices SHALL be returned with platform, delivery method, and last seen

### Requirement: Notification Event Database Schema
The system SHALL store notification events and device registrations in PostgreSQL.

#### Scenario: Notification events table
- **GIVEN** the `notification_events` table
- **THEN** it SHALL have columns: `id` (UUID PK), `event_type` (varchar, indexed), `title` (varchar), `summary` (text), `payload` (JSONB), `read` (boolean default false), `created_at` (timestamp, indexed)

#### Scenario: Device registrations table
- **GIVEN** the `device_registrations` table
- **THEN** it SHALL have columns: `id` (UUID PK), `platform` (varchar), `token` (varchar, unique), `delivery_method` (varchar), `created_at` (timestamp), `last_seen` (timestamp)

### Requirement: Notification Event Cleanup
The system SHALL provide a mechanism to clean up old notification events.

#### Scenario: CLI cleanup command
- **WHEN** `aca manage cleanup-notifications --older-than 30d` is executed
- **THEN** all notification events older than 30 days SHALL be deleted

#### Scenario: Auto-cleanup on startup
- **WHEN** the application starts
- **THEN** notification events older than 90 days SHALL be automatically deleted

### Requirement: Notification Bell UI
The system SHALL display a notification bell icon in the app header with unread event count.

#### Scenario: Unread badge
- **WHEN** there are unread notification events
- **THEN** the bell icon SHALL display a badge with the unread count

#### Scenario: No unread events
- **WHEN** all events are read or no events exist
- **THEN** the bell icon SHALL display without a badge

#### Scenario: Click bell icon
- **WHEN** the user clicks the bell icon
- **THEN** a dropdown SHALL appear showing recent notification events
- **AND** each event SHALL show its type icon, title, summary, and relative timestamp

#### Scenario: Click event in dropdown
- **WHEN** the user clicks an event in the notification dropdown
- **THEN** the app SHALL navigate to the relevant content (digest, script, audio, or job)
- **AND** the event SHALL be marked as read

#### Scenario: Mark all as read
- **WHEN** the user clicks "Mark all as read" in the notification dropdown
- **THEN** all events SHALL be marked as read via the API
- **AND** the badge SHALL be cleared

#### Scenario: Real-time updates
- **WHEN** a new notification event arrives via SSE
- **THEN** the unread badge SHALL update immediately
- **AND** the event SHALL appear at the top of the dropdown if open
