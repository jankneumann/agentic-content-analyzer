# content-capture Specification

## Purpose
Capture web URLs from browser extensions, bookmarklets, iOS Shortcuts, and the
web save page into the durable ingestion workflow (`POST /api/v1/ingestions`,
`kind: url`). Client-supplied HTML save-page and the retired save-url mutation
are not part of the live contract.

## Requirements

### Requirement: Chrome Extension

The system SHALL provide a Chrome extension that queues URL capture through
canonical ingestion. Client-supplied HTML is not part of the live contract.

#### Scenario: One-click save

- **GIVEN** extension is installed and configured
- **WHEN** user clicks the extension icon and saves
- **THEN** the current page URL SHALL be posted to `POST /api/v1/ingestions` with `kind: url`
- **AND** auth SHALL use the `X-Admin-Key` header when a key is configured
- **AND** the UI SHALL display the returned `operation_id`

#### Scenario: Capture selection

- **GIVEN** user has selected text on a page
- **WHEN** user saves the page
- **THEN** selected text SHALL be sent as `notes` on `UrlIngestCommand`

#### Scenario: Configuration

- **GIVEN** extension options page
- **WHEN** user enters API URL and key
- **THEN** settings SHALL be persisted for future saves

#### Scenario: Full page HTML is not submitted

- **GIVEN** extension is installed
- **WHEN** user clicks save
- **THEN** the request SHALL be `POST /api/v1/ingestions` with `kind: url`
- **AND** client-supplied HTML SHALL NOT be posted to a retired `save-page` route

### Requirement: Bookmarklet

The system SHALL provide a universal bookmarklet.

#### Scenario: Save via bookmarklet
- **GIVEN** bookmarklet is installed
- **WHEN** user clicks the bookmarklet
- **THEN** save page SHALL open with URL pre-filled

### Requirement: Save URL API

The system SHALL queue URL capture through the canonical ingestion command.

#### Scenario: Save new URL
- **GIVEN** `POST /api/v1/ingestions` with `{ "kind": "url", "url": "<https URL>" }` and `X-Admin-Key`
- **WHEN** the command is valid
- **THEN** the system SHALL return `202` with an `OperationHandle`
- **AND** `operation_type` SHALL be `ingestion.execute`
- **AND** `schema_version` SHALL be `2`

#### Scenario: Retired save-url mutation
- **WHEN** `POST /api/v1/content/save-url` is called
- **THEN** the response SHALL be 404 or 405
- **AND** no compatibility adapter SHALL restore the retired body shape

#### Scenario: Save with metadata
- **GIVEN** request includes optional `title`, `tags`, or `notes`
- **WHEN** the command is valid
- **THEN** provided metadata SHALL be stored with content
- **AND** extraction MAY override title if not provided

#### Scenario: Duplicate URL
- **GIVEN** URL already exists in system
- **WHEN** same URL is submitted to `POST /api/v1/ingestions`
- **THEN** the system SHALL still return `202` with an `OperationHandle`
- **AND** durable ingestion MAY skip creating a second content row

#### Scenario: Unknown fields are rejected
- **GIVEN** request includes fields not on `UrlIngestCommand` (e.g. `source`, `excerpt`, `html`)
- **WHEN** `POST /api/v1/ingestions` is called
- **THEN** the response SHALL be 422

### Requirement: Content Extraction

The system SHALL extract content from saved URLs using background processing.

> **Change**: Added explicit background processing requirement and status polling.

#### Scenario: Successful extraction
- **GIVEN** URL is queued for extraction
- **WHEN** extraction completes successfully
- **THEN** markdown content SHALL be stored
- **AND** status SHALL be updated to "parsed"

#### Scenario: Extraction failure
- **GIVEN** URL cannot be extracted (404, blocked, timeout)
- **WHEN** extraction fails
- **THEN** status SHALL be "failed"
- **AND** error message SHALL be stored
- **AND** URL and title SHALL be preserved

#### Scenario: Status polling
- **GIVEN** ingestion has been queued
- **WHEN** `GET /api/v1/operations/{operation_id}` is called
- **THEN** current operation status SHALL be returned

### Requirement: Save Page API

The system SHALL NOT compose `POST /api/v1/content/save-page`. Restoring
client-supplied HTML ingest requires a URL-major or a new ingest `kind`.

#### Scenario: Retired save-page mutation

- **WHEN** `POST /api/v1/content/save-page` is called
- **THEN** the response SHALL be 404 or 405

### Requirement: Image Reference Rewriting

The system SHALL rewrite image URLs in extracted markdown to point to locally stored copies.

#### Scenario: Rewrite external image URLs

- **GIVEN** markdown containing external image URLs
- **WHEN** images have been downloaded and stored
- **THEN** each image URL SHALL be replaced with the local storage URL
- **AND** the storage URL SHALL use the file serving endpoint format

#### Scenario: Preserve failed image URLs

- **GIVEN** markdown containing an image URL that failed to download
- **WHEN** image rewriting runs
- **THEN** the original URL SHALL remain unchanged

#### Scenario: No images to rewrite

- **GIVEN** markdown with no image references
- **WHEN** image rewriting runs
- **THEN** markdown SHALL remain unchanged

### Requirement: Direct URL submission UI
The system SHALL provide a web UI that lets users submit a URL for ingestion using `POST /api/v1/ingestions` with `kind: url`.

#### Scenario: Submit URL for ingestion
- **GIVEN** the user is on the direct URL ingest form
- **WHEN** the user submits a valid URL
- **THEN** the system SHALL POST `{ "kind": "url", "url": "..." }` to `/api/v1/ingestions`
- **AND** the UI SHALL display the returned `operation_id`

#### Scenario: Validation error
- **GIVEN** the user is on the direct URL ingest form
- **WHEN** the user submits an invalid or empty URL
- **THEN** the UI SHALL display a validation error
- **AND** no ingestion request SHALL be sent

### Requirement: iOS Shortcuts Integration

The system SHALL support content capture via Apple iOS Shortcuts.

#### Scenario: Share Sheet capture
- **GIVEN** user has installed the Save to Newsletter shortcut
- **WHEN** user shares a URL via iOS Share Sheet
- **THEN** the URL SHALL be sent as `{ "kind": "url", "url": "..." }` to `POST /api/v1/ingestions`
- **AND** user SHALL receive success/failure notification

#### Scenario: Shortcut configuration
- **GIVEN** user opens the Shortcut settings
- **WHEN** user enters API URL and optional API key
- **THEN** settings SHALL be persisted for future saves

#### Scenario: Offline queueing
- **GIVEN** device has no network connection
- **WHEN** user attempts to save a URL
- **THEN** Shortcut SHALL show offline error
- **AND** URL MAY be saved to clipboard for manual retry

### Requirement: Optional API Key Authentication

The system SHALL support optional API key authentication for mobile clients.

#### Scenario: API key validation
- **GIVEN** request includes `X-Admin-Key: <ADMIN_API_KEY>`
- **WHEN** the key is valid
- **THEN** request SHALL be processed normally

#### Scenario: Missing API key (open mode)
- **GIVEN** server is configured without required authentication
- **WHEN** request has no API key
- **THEN** request SHALL be processed normally

#### Scenario: Invalid API key
- **GIVEN** request includes invalid API key
- **WHEN** endpoint requires authentication
- **THEN** response SHALL be 401 Unauthorized

#### Scenario: Rate limiting
- **GIVEN** API key has exceeded rate limit (default 60/min)
- **WHEN** additional request is made
- **THEN** response SHALL be 429 Too Many Requests
- **AND** response SHALL include `retry_after` seconds

### Requirement: Mobile-Optimized Save Page

The system SHALL provide a mobile-friendly web page for URL saving.

#### Scenario: Pre-filled form
- **GIVEN** user navigates to `/save?url=...&title=...`
- **WHEN** page loads
- **THEN** form SHALL be pre-filled with URL parameters

#### Scenario: Touch-friendly interface
- **WHEN** save page is rendered
- **THEN** all tap targets SHALL be at least 44x44 pixels
- **AND** text SHALL be readable without zooming (16px minimum)

#### Scenario: Save submission
- **GIVEN** user fills in the save form
- **WHEN** user taps Save button
- **THEN** URL SHALL be submitted to `POST /api/v1/ingestions` with `kind: url`
- **AND** success/error state SHALL be displayed
