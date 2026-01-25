# mobile-cloud-infrastructure Specification

## Purpose
TBD - created by archiving change add-mobile-deployment. Update Purpose after archive.
## Requirements
### Requirement: Durable Task Queue

The system SHALL provide a durable task queue using PGQueuer that persists jobs to PostgreSQL and processes them reliably even across server restarts.

#### Scenario: Job survives server restart
- **WHEN** a content extraction job is queued
- **AND** the worker process restarts
- **THEN** the job SHALL be processed after restart without data loss

#### Scenario: Failed job retry
- **WHEN** a job fails due to a transient error
- **THEN** the system SHALL retry the job according to configured retry policy

#### Scenario: Graceful fallback
- **WHEN** PGQueuer is unavailable
- **THEN** the system SHALL fall back to FastAPI BackgroundTasks for non-durable processing

---

### Requirement: Queue Connection Management

The system SHALL use different connection types for API and worker processes to ensure proper handling of short-lived requests and long-lived job processing.

#### Scenario: Web API uses pooled connection
- **WHEN** the web API handles a request
- **THEN** it SHALL use a pooled database connection for efficient resource sharing

#### Scenario: Worker uses direct connection
- **WHEN** the worker process runs PGQueuer
- **THEN** it SHALL use a direct (non-pooled) connection to support LISTEN/NOTIFY

#### Scenario: DatabaseProvider abstraction
- **WHEN** `get_queue_url()` is called on any DatabaseProvider
- **THEN** it SHALL return the appropriate direct connection URL for that provider

---

### Requirement: Save URL API

The system SHALL provide an API endpoint for saving URLs from mobile devices, enabling iOS Shortcuts and other mobile clients to capture content.

#### Scenario: Save new URL
- **WHEN** a `POST /api/v1/content/save-url` request is received with a valid URL
- **THEN** the system SHALL create a Content record with status PENDING
- **AND** queue a background job for content extraction
- **AND** return the content ID and queued status

#### Scenario: Duplicate URL detection
- **WHEN** a URL that already exists in the database is submitted
- **THEN** the system SHALL return the existing content ID
- **AND** indicate that the content is a duplicate

#### Scenario: Check extraction status
- **WHEN** a `GET /api/v1/content/{id}/status` request is received
- **THEN** the system SHALL return the current status (pending, parsing, parsed, failed)

---

### Requirement: URL Content Extraction

The system SHALL extract content from saved URLs using trafilatura and convert HTML to markdown for storage and processing.

#### Scenario: Successful extraction
- **WHEN** a URL content extraction job runs
- **THEN** the system SHALL fetch the URL content
- **AND** extract the main article content as markdown
- **AND** extract metadata (title, author, published date)
- **AND** update the Content record with extracted data

#### Scenario: Extraction timeout
- **WHEN** content extraction exceeds 30 seconds
- **THEN** the system SHALL cancel the extraction
- **AND** mark the Content record as failed

#### Scenario: Extraction failure
- **WHEN** content extraction fails (404, blocked, parse error)
- **THEN** the system SHALL log the error
- **AND** mark the Content record as failed with error details

---

### Requirement: Mobile Save Interface

The system SHALL provide a mobile-optimized web interface for saving URLs when direct API access is not available.

#### Scenario: Pre-filled save form
- **WHEN** a user visits `/save?url=<encoded-url>`
- **THEN** the system SHALL display a mobile-friendly form
- **AND** pre-fill the URL field from query parameters

#### Scenario: Successful save
- **WHEN** the save form is submitted
- **THEN** the system SHALL call the save URL API
- **AND** display a success message with the content ID

---

### Requirement: Railway Cloud Deployment

The system SHALL deploy to Railway as two services (web API and worker) with proper configuration for cloud hosting.

#### Scenario: Web service deployment
- **WHEN** the web service is deployed
- **THEN** it SHALL be accessible via HTTPS
- **AND** accept requests from mobile clients (CORS configured)

#### Scenario: Worker service deployment
- **WHEN** the worker service is deployed
- **THEN** it SHALL connect to the same database as the web service
- **AND** process queued jobs independently

---

### Requirement: Scheduled Job Execution

The system SHALL support scheduled recurring jobs using pg_cron to insert jobs into the PGQueuer table.

#### Scenario: Daily newsletter scan
- **WHEN** the configured time (6 AM UTC) is reached
- **THEN** pg_cron SHALL insert a `scan_newsletters` job into the queue
- **AND** the worker SHALL process the job when available

#### Scenario: Schedule independent of worker
- **WHEN** the worker is temporarily unavailable
- **THEN** pg_cron SHALL still insert scheduled jobs
- **AND** the worker SHALL process accumulated jobs when it restarts

---

### Requirement: iOS Shortcuts Integration

The system SHALL document and support iOS Shortcuts for one-tap URL saving from the iOS Share Sheet.

#### Scenario: Share Sheet capture
- **WHEN** a user shares a URL from Safari to the configured Shortcut
- **THEN** the Shortcut SHALL send the URL to the Save URL API
- **AND** display a success or error notification

#### Scenario: Shortcut configuration
- **WHEN** a user installs the Shortcut
- **THEN** they SHALL be able to configure the API URL
- **AND** optionally configure an API key for authentication
