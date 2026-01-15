# Content Capture Capability

## ADDED Requirements

### Requirement: Chrome Extension

The system SHALL provide a Chrome extension for content capture.

#### Scenario: One-click save
- **GIVEN** extension is installed and configured
- **WHEN** user clicks the extension icon
- **THEN** current page URL SHALL be saved to the system

#### Scenario: Capture selection
- **GIVEN** user has selected text on a page
- **WHEN** user saves the page
- **THEN** selected text SHALL be included as excerpt

#### Scenario: Configuration
- **GIVEN** extension options page
- **WHEN** user enters API URL and key
- **THEN** settings SHALL be persisted for future saves

### Requirement: Bookmarklet

The system SHALL provide a universal bookmarklet.

#### Scenario: Save via bookmarklet
- **GIVEN** bookmarklet is installed
- **WHEN** user clicks the bookmarklet
- **THEN** save page SHALL open with URL pre-filled

### Requirement: Save URL API

The system SHALL provide an API for saving URLs.

#### Scenario: Save new URL
- **GIVEN** `POST /api/v1/content/save-url` with valid URL
- **WHEN** URL is not already saved
- **THEN** content SHALL be queued for extraction
- **AND** content ID SHALL be returned

#### Scenario: Duplicate URL
- **GIVEN** URL already exists in system
- **WHEN** same URL is submitted
- **THEN** existing content ID SHALL be returned
- **AND** status SHALL indicate "duplicate"

### Requirement: Content Extraction

The system SHALL extract content from saved URLs.

#### Scenario: Successful extraction
- **GIVEN** URL is queued for extraction
- **WHEN** extraction completes
- **THEN** markdown content SHALL be stored
- **AND** status SHALL be updated to "parsed"

#### Scenario: Extraction failure
- **GIVEN** URL cannot be extracted
- **WHEN** extraction fails
- **THEN** status SHALL be "failed"
- **AND** error message SHALL be stored
