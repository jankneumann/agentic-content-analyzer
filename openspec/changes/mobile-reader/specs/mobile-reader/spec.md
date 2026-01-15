# Mobile Reader Capability

## ADDED Requirements

### Requirement: Mobile-Responsive Layout

The system SHALL provide mobile-optimized layouts.

#### Scenario: Readable text on mobile
- **GIVEN** content is viewed on a mobile device
- **WHEN** the page loads
- **THEN** text SHALL be readable without zooming
- **AND** font size SHALL be at least 16px

#### Scenario: Touch-friendly controls
- **WHEN** interactive elements are rendered
- **THEN** tap targets SHALL be at least 44x44 pixels

### Requirement: Audio Player

The system SHALL provide an audio player for podcast content.

#### Scenario: Play audio
- **GIVEN** digest has associated audio
- **WHEN** digest page is viewed
- **THEN** audio player SHALL be displayed
- **AND** user SHALL be able to play/pause

#### Scenario: Playback controls
- **GIVEN** audio is playing
- **WHEN** user interacts with player
- **THEN** seek, speed control (1x, 1.5x, 2x) SHALL be available

### Requirement: PWA Support

The system SHALL support Progressive Web App installation.

#### Scenario: Add to home screen
- **GIVEN** user accesses the app in a browser
- **WHEN** PWA criteria are met
- **THEN** "Add to Home Screen" prompt SHALL be available

#### Scenario: Standalone mode
- **GIVEN** app is installed as PWA
- **WHEN** launched from home screen
- **THEN** app SHALL run in standalone mode without browser UI

### Requirement: Dark Mode

The system SHALL support dark mode.

#### Scenario: System preference
- **GIVEN** user's system is set to dark mode
- **WHEN** app is loaded
- **THEN** dark color scheme SHALL be applied
