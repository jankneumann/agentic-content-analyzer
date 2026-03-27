# native-share-target Specification

## Purpose
Receive shared URLs from other mobile apps via the native share sheet, routing them to the content save API for extraction and processing.

## ADDED Requirements

### Requirement: Receive Shared URLs
The system SHALL receive URLs shared from other apps via the native share sheet and save them for content extraction.

#### Scenario: Share URL from Safari
- **WHEN** a user shares a URL from Safari (or any app) to the ACA app
- **THEN** the app SHALL receive the shared URL
- **AND** call `POST /api/v1/content/save-url` with the shared URL
- **AND** display a confirmation toast

#### Scenario: Share text with URL
- **WHEN** a user shares text that contains a URL
- **THEN** the app SHALL extract the first URL from the text
- **AND** save it via the content save API

#### Scenario: Share without URL
- **WHEN** a user shares text that does not contain a URL
- **THEN** the app SHALL display an error message indicating no URL was found

### Requirement: URL Validation
The system SHALL validate shared URLs before processing to prevent injection of malicious content.

#### Scenario: Valid HTTP(S) URL
- **WHEN** a shared URL uses the `http` or `https` scheme
- **THEN** the URL SHALL be accepted for processing

#### Scenario: Rejected schemes
- **WHEN** a shared URL uses a non-HTTP scheme (e.g., `javascript:`, `data:`, `file:`, `ftp:`)
- **THEN** the URL SHALL be rejected
- **AND** the user SHALL see an error message indicating the URL is not supported

#### Scenario: Oversized URL
- **WHEN** a shared URL exceeds 2048 characters
- **THEN** the URL SHALL be rejected
- **AND** the user SHALL see an error message indicating the URL is too long

### Requirement: Offline Share Queue
The system SHALL queue shared URLs when the device is offline and submit them when connectivity is restored.

#### Scenario: Offline share
- **WHEN** a user shares a URL while the device is offline
- **THEN** the URL SHALL be stored in Capacitor Preferences under key `pending_shares`
- **AND** a confirmation SHALL indicate the URL is queued for later

#### Scenario: Queue flush on reconnect
- **WHEN** network connectivity is restored (detected via `@capacitor/network` `networkStatusChange`)
- **THEN** all pending URLs SHALL be submitted to the save-url API
- **AND** successfully submitted URLs SHALL be removed from the queue

#### Scenario: Duplicate prevention
- **WHEN** the same URL is shared multiple times while offline
- **THEN** only one entry SHALL be stored in the queue (deduplicated by normalized URL string)

### Requirement: Android Intent Filter
The system SHALL configure an Android intent filter to appear in the share sheet for text and URL content. (Android deployment deferred — scaffolded only.)

#### Scenario: Share sheet visibility
- **WHEN** a user opens the Android share sheet with text or URL content
- **THEN** the ACA app SHALL appear as a share target option

#### Scenario: Intent handling
- **WHEN** the ACA app receives a share intent
- **THEN** the app SHALL extract the shared URL from the intent extras
- **AND** process it via the content save flow

### Requirement: iOS Share Extension
The system SHALL include an iOS Share Extension to receive shared content. The extension communicates with the main app via an App Group shared container.

#### Scenario: Share sheet visibility
- **WHEN** a user opens the iOS share sheet on a webpage or URL
- **THEN** the ACA app SHALL appear as a share target option

#### Scenario: Extension writes to shared container
- **WHEN** the iOS Share Extension receives a URL
- **THEN** it SHALL write the URL to the App Group `UserDefaults` suite (`group.com.aca.app`)
- **AND** the extension process SHALL complete without making API calls (no auth context available)

#### Scenario: Main app processes shared URL
- **WHEN** the main app is activated (via `@capacitor/app` `appStateChange` event)
- **AND** a pending URL exists in the App Group shared container
- **THEN** the main app SHALL read the URL, validate it, and submit it to the save-url API
- **AND** clear the pending URL from the shared container after successful processing
