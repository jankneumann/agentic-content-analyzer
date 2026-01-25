# mobile-reader Specification

## Purpose
TBD - created by archiving change mobile-reader. Update Purpose after archive.
## Requirements
### Requirement: PWA Installation

The system SHALL support Progressive Web App installation.

#### Scenario: Add to home screen
- **GIVEN** user accesses the app in a mobile browser
- **WHEN** PWA installability criteria are met
- **THEN** "Add to Home Screen" (iOS) or "Install App" (Android) SHALL be available

#### Scenario: Standalone mode
- **GIVEN** app is installed as PWA
- **WHEN** launched from home screen
- **THEN** app SHALL run in standalone mode without browser UI

#### Scenario: App icons
- **GIVEN** app is installed on device
- **WHEN** displayed on home screen
- **THEN** app icon SHALL be visible and properly sized
- **AND** maskable icon SHALL display correctly on Android

### Requirement: Offline Fallback

The system SHALL provide graceful offline behavior.

#### Scenario: Network unavailable
- **GIVEN** user has previously visited the app
- **WHEN** network connection is unavailable
- **AND** user navigates to an uncached page
- **THEN** offline fallback page SHALL be displayed
- **AND** retry button SHALL be available

#### Scenario: Cached content
- **GIVEN** user has previously visited a page
- **WHEN** network connection is unavailable
- **THEN** cached static assets (JS, CSS, images) SHALL be served

### Requirement: Service Worker Updates

The system SHALL handle service worker updates gracefully.

#### Scenario: New version available
- **GIVEN** a new version of the app is deployed
- **WHEN** user visits the app
- **THEN** update notification SHALL be displayed
- **AND** user SHALL be able to refresh to apply update

### Requirement: iOS-Specific Support

The system SHALL support iOS-specific PWA features.

#### Scenario: iOS splash screen
- **GIVEN** app is installed on iOS device
- **WHEN** launched from home screen
- **THEN** splash screen SHALL be displayed during load

#### Scenario: Safe areas
- **GIVEN** app is running on a device with notch or Dynamic Island
- **WHEN** content is displayed
- **THEN** content SHALL NOT be obscured by device cutouts
- **AND** safe area padding SHALL be applied

### Requirement: E2E Test Coverage

The system SHALL have E2E tests for PWA features.

#### Scenario: Service worker test
- **GIVEN** E2E test suite is run
- **WHEN** service worker registration is tested
- **THEN** test SHALL verify service worker is registered

#### Scenario: Offline test
- **GIVEN** E2E test suite is run
- **WHEN** offline behavior is tested
- **THEN** test SHALL verify offline fallback page displays

#### Scenario: Mobile viewport test
- **GIVEN** E2E test suite is run with mobile device projects
- **WHEN** app is tested on mobile viewport
- **THEN** mobile-specific UI elements SHALL be visible
