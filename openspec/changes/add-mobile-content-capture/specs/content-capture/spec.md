# Content Capture Capability

## ADDED Requirements

### Requirement: iOS Shortcuts Integration

The system SHALL support content capture via Apple iOS Shortcuts.

#### Scenario: Share Sheet capture
- **GIVEN** user has installed the Save to Newsletter shortcut
- **WHEN** user shares a URL via iOS Share Sheet
- **THEN** the URL SHALL be sent to the save-url API
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
- **GIVEN** request includes `Authorization: Bearer <key>` header
- **WHEN** key is valid and not rate-limited
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
- **THEN** URL SHALL be submitted to save-url API
- **AND** success/error state SHALL be displayed

## MODIFIED Requirements

### Requirement: Save URL API

The system SHALL provide an API for saving URLs with enhanced mobile support.

> **Change**: Added optional fields for mobile capture, source tracking, and enhanced response format.

#### Scenario: Save new URL
- **GIVEN** `POST /api/v1/content/save-url` with valid URL
- **WHEN** URL is not already saved
- **THEN** content SHALL be queued for extraction
- **AND** content ID SHALL be returned
- **AND** status SHALL be "queued"

#### Scenario: Save with metadata
- **GIVEN** request includes optional title, excerpt, tags, or notes
- **WHEN** content is created
- **THEN** provided metadata SHALL be stored with content
- **AND** extraction MAY override title if not provided

#### Scenario: Duplicate URL
- **GIVEN** URL already exists in system
- **WHEN** same URL is submitted
- **THEN** existing content ID SHALL be returned
- **AND** status SHALL indicate "exists"
- **AND** duplicate flag SHALL be true

#### Scenario: Source tracking
- **GIVEN** request includes `source` field (e.g., "ios_shortcut", "bookmarklet")
- **WHEN** content is created
- **THEN** source SHALL be stored in content metadata

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
- **GIVEN** content has been queued
- **WHEN** `GET /api/v1/content/{id}/status` is called
- **THEN** current status, title, and word count SHALL be returned
