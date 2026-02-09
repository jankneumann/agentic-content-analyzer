# content-capture Specification

## Purpose
TBD - created by archiving change content-capture. Update Purpose after archive.
## Requirements
### Requirement: Chrome Extension

The system SHALL provide a Chrome extension for content capture with full page DOM capture support.

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

#### Scenario: Full page capture mode

- **GIVEN** extension with capture mode set to "full page"
- **WHEN** user clicks save
- **THEN** the rendered DOM content SHALL be captured from the active tab
- **AND** HTML content SHALL be sent to `save-page` endpoint
- **AND** page title and selected text SHALL be included

#### Scenario: URL-only capture mode

- **GIVEN** extension with capture mode set to "URL only"
- **WHEN** user clicks save
- **THEN** only the URL SHALL be sent to `save-url` endpoint
- **AND** server-side extraction SHALL be used

#### Scenario: DOM capture failure fallback

- **GIVEN** DOM capture fails (e.g., restricted page)
- **WHEN** the extension attempts full page capture
- **THEN** the extension SHALL fall back to URL-only save
- **AND** user SHALL be notified of the fallback

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
- **AND** status SHALL indicate "exists"

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

### Requirement: Save Page API

The system SHALL provide an API endpoint for saving pre-captured HTML content with image extraction.

#### Scenario: Save captured page

- **GIVEN** `POST /api/v1/content/save-page` with required URL and HTML fields
- **WHEN** the request is valid
- **THEN** content SHALL be queued for background processing
- **AND** content ID SHALL be returned
- **AND** status SHALL be "queued"

#### Scenario: Request field validation

- **GIVEN** `POST /api/v1/content/save-page`
- **WHEN** url or html fields are missing
- **THEN** the server SHALL return 422 Unprocessable Entity

#### Scenario: Reject oversized HTML

- **GIVEN** `POST /api/v1/content/save-page` with HTML exceeding 5 MB
- **WHEN** the request is received
- **THEN** the server SHALL return 413 Payload Too Large

#### Scenario: Duplicate URL detection

- **GIVEN** a URL already saved in the system
- **WHEN** the same URL is submitted via `save-page`
- **THEN** existing content ID SHALL be returned
- **AND** status SHALL indicate "exists"

#### Scenario: Empty or malformed HTML

- **GIVEN** `POST /api/v1/content/save-page` with HTML that contains no extractable content
- **WHEN** background processing runs
- **THEN** content status SHALL be set to FAILED
- **AND** error_message SHALL describe the extraction failure

#### Scenario: Parse client-supplied HTML

- **GIVEN** HTML captured from the browser DOM
- **WHEN** background processing runs
- **THEN** trafilatura SHALL extract markdown from the HTML
- **AND** images SHALL be extracted via ImageExtractor
- **AND** images SHALL be stored via FileStorageProvider
- **AND** markdown image references SHALL be rewritten to local storage URLs
- **AND** content status SHALL be updated to PARSED

#### Scenario: Image download failure

- **GIVEN** an image URL in captured HTML that cannot be downloaded
- **WHEN** image extraction is attempted
- **THEN** the original image URL SHALL be preserved in markdown
- **AND** processing SHALL continue for remaining images
- **AND** a warning SHALL be logged

#### Scenario: Status polling for save-page content

- **GIVEN** content created via `save-page`
- **WHEN** `GET /api/v1/content/{content_id}/status` is called
- **THEN** current processing status SHALL be returned
- **AND** response format SHALL match existing status endpoint

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
The system SHALL provide a web UI that lets users submit a URL for ingestion using the save-url workflow.

#### Scenario: Submit URL for ingestion
- **GIVEN** the user is on the direct URL ingest form
- **WHEN** the user submits a valid URL
- **THEN** the system SHALL call the save-url workflow
- **AND** the UI SHALL display the returned content ID and status

#### Scenario: Validation error
- **GIVEN** the user is on the direct URL ingest form
- **WHEN** the user submits an invalid or empty URL
- **THEN** the UI SHALL display a validation error
- **AND** no save-url request SHALL be sent
