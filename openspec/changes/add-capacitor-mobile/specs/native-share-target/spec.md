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

#### Scenario: Offline share
- **WHEN** a user shares a URL while the device is offline
- **THEN** the URL SHALL be queued locally
- **AND** submitted to the API when connectivity is restored

### Requirement: Android Intent Filter
The system SHALL configure an Android intent filter to appear in the share sheet for text and URL content.

#### Scenario: Share sheet visibility
- **WHEN** a user opens the Android share sheet with text or URL content
- **THEN** the ACA app SHALL appear as a share target option

#### Scenario: Intent handling
- **WHEN** the ACA app receives a share intent
- **THEN** the app SHALL extract the shared URL from the intent extras
- **AND** process it via the content save flow

### Requirement: iOS Share Extension
The system SHALL include an iOS Share Extension to receive shared content.

#### Scenario: Share sheet visibility
- **WHEN** a user opens the iOS share sheet on a webpage or URL
- **THEN** the ACA app SHALL appear as a share target option

#### Scenario: Extension handling
- **WHEN** the iOS Share Extension receives a URL
- **THEN** it SHALL forward the URL to the main app
- **AND** the main app SHALL process it via the content save flow
