# capacitor-mobile Specification

## Purpose
Native mobile shell via Capacitor, providing platform detection, native plugin integration, build configuration, and app distribution for iOS and Android.

## ADDED Requirements

### Requirement: Capacitor Configuration
The system SHALL include Capacitor configuration to wrap the existing web build in native iOS and Android shells.

#### Scenario: Capacitor initialization
- **WHEN** `npx cap init` is run in the `web/` directory
- **THEN** a `capacitor.config.ts` SHALL be created with app ID, app name, and `webDir` pointing to the Vite build output

#### Scenario: iOS platform
- **WHEN** `npx cap add ios` is run
- **THEN** an `ios/` directory SHALL be created with an Xcode project
- **AND** the project SHALL be configured with the app bundle identifier

#### Scenario: Android platform
- **WHEN** `npx cap add android` is run
- **THEN** an `android/` directory SHALL be created with a Gradle project
- **AND** the project SHALL be configured with the app package name

#### Scenario: Sync web build
- **WHEN** `npx cap sync` is run after a Vite production build
- **THEN** the contents of `dist/` SHALL be copied to both native platforms
- **AND** native plugin dependencies SHALL be resolved

### Requirement: Platform Detection
The system SHALL provide a utility to detect whether the app is running in a native Capacitor shell or a web browser.

#### Scenario: Native platform detection
- **WHEN** the app is running inside a Capacitor native shell
- **THEN** `isNative()` SHALL return `true`
- **AND** `getPlatform()` SHALL return `"ios"` or `"android"`

#### Scenario: Web platform detection
- **WHEN** the app is running in a web browser (including PWA)
- **THEN** `isNative()` SHALL return `false`
- **AND** `getPlatform()` SHALL return `"web"`

### Requirement: Push Notifications
The system SHALL support native push notifications for all backend pipeline completion events.

#### Scenario: Request permission
- **WHEN** the user enables push notifications in settings
- **THEN** the system SHALL request native push notification permission
- **AND** register the device token with the backend

#### Scenario: Batch summary completion notification
- **WHEN** a batch summarization job completes on the backend
- **THEN** the system SHALL send a push notification with the count of summarized items (e.g., "12 items summarized")

#### Scenario: Theme analysis completion notification
- **WHEN** a theme analysis job completes on the backend
- **THEN** the system SHALL send a push notification with the number of themes identified

#### Scenario: Digest completion notification
- **WHEN** a daily or weekly digest is created on the backend
- **THEN** the system SHALL send a push notification with the digest title and type (daily/weekly)

#### Scenario: Podcast script completion notification
- **WHEN** a podcast script is generated on the backend
- **THEN** the system SHALL send a push notification with the script title

#### Scenario: Audio generation completion notification
- **WHEN** a podcast audio or audio digest is generated on the backend
- **THEN** the system SHALL send a push notification with the audio title and duration

#### Scenario: Pipeline completion notification
- **WHEN** a full pipeline run (ingest → summarize → digest) completes
- **THEN** the system SHALL send a single summary notification with pipeline results

#### Scenario: Job failure notification
- **WHEN** any background job fails
- **THEN** the system SHALL send a push notification with the job type and error summary

#### Scenario: Notification tap
- **WHEN** the user taps a push notification
- **THEN** the app SHALL open and navigate to the relevant content (e.g., the completed digest, script, or audio)

#### Scenario: Notification preferences
- **WHEN** the user configures notification preferences in settings
- **THEN** they SHALL be able to enable/disable notifications per event type (summaries, digests, scripts, audio, failures)

#### Scenario: Web fallback
- **WHEN** the app is running as a PWA (not native)
- **THEN** push notification registration SHALL be skipped
- **AND** no push notification UI SHALL be shown

### Requirement: Native Status Bar Control
The system SHALL control the native status bar appearance to match the app theme.

#### Scenario: Dark mode
- **WHEN** the app is in dark mode
- **THEN** the status bar SHALL use light text on a dark background

#### Scenario: Light mode
- **WHEN** the app is in light mode
- **THEN** the status bar SHALL use dark text on a light background

### Requirement: Haptic Feedback
The system SHALL provide haptic feedback for key user interactions on native platforms.

#### Scenario: Voice input toggle
- **WHEN** the user taps the voice input button on a native platform
- **THEN** a light haptic feedback SHALL be triggered

#### Scenario: Content saved confirmation
- **WHEN** content is successfully saved via share target on a native platform
- **THEN** a success haptic feedback SHALL be triggered

#### Scenario: Web no-op
- **WHEN** haptic feedback is triggered on a web platform
- **THEN** the call SHALL be a no-op (no error)

### Requirement: Build Scripts
The system SHALL provide npm scripts for building and running native apps.

#### Scenario: Development build
- **WHEN** `pnpm cap:dev` is run
- **THEN** the Vite dev server SHALL start
- **AND** Capacitor SHALL be configured to use the dev server URL for live reload

#### Scenario: Production build
- **WHEN** `pnpm cap:build` is run
- **THEN** Vite SHALL build production assets
- **AND** `cap sync` SHALL copy them to native platforms

#### Scenario: Open in IDE
- **WHEN** `pnpm cap:open:ios` or `pnpm cap:open:android` is run
- **THEN** Xcode or Android Studio SHALL open with the native project
