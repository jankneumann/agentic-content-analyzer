# content-capture Delta Spec

## MODIFIED Requirements

### Requirement: Content Capture Methods
The system SHALL support multiple methods for capturing content URLs: bookmarklet, iOS Shortcuts, Chrome extension, and native share target.

#### Scenario: Bookmarklet capture
- **WHEN** a user clicks the bookmarklet in their browser
- **THEN** the current page URL SHALL be sent to `POST /api/v1/content/save-url`

#### Scenario: iOS Shortcuts capture
- **WHEN** a user runs the iOS Shortcut to share a URL
- **THEN** the URL SHALL be sent to `POST /api/v1/content/save-url`

#### Scenario: Native share target capture
- **WHEN** a user shares a URL from any app to the ACA native app via the share sheet
- **THEN** the URL SHALL be sent to `POST /api/v1/content/save-url`
- **AND** a confirmation SHALL be shown to the user

#### Scenario: Chrome extension capture
- **WHEN** a user clicks the Chrome extension button
- **THEN** the current page URL SHALL be sent to `POST /api/v1/content/save-url`
