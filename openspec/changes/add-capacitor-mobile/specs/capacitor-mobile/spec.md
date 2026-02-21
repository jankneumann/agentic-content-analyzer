# capacitor-mobile Specification

## Purpose
Native mobile shell via Capacitor, providing platform detection, native plugin integration, build configuration, and iOS app distribution via TestFlight. Android platform is scaffolded but deployment is deferred to a separate proposal.

## ADDED Requirements

### Requirement: Capacitor Configuration
The system SHALL include Capacitor configuration to wrap the existing web build in a native iOS shell. Android platform is scaffolded for future use.

#### Scenario: Capacitor initialization
- **WHEN** `npx cap init` is run in the `web/` directory
- **THEN** a `capacitor.config.ts` SHALL be created with app ID, app name, and `webDir` pointing to the Vite build output

#### Scenario: iOS platform
- **WHEN** `npx cap add ios` is run
- **THEN** an `ios/` directory SHALL be created with an Xcode project
- **AND** the project SHALL be configured with the app bundle identifier

#### Scenario: Android platform (scaffolded, deployment deferred)
- **WHEN** `npx cap add android` is run
- **THEN** an `android/` directory SHALL be created with a Gradle project
- **AND** the project SHALL be configured with the app package name
- **AND** Android build and deployment SHALL be deferred to a separate proposal

#### Scenario: Sync web build
- **WHEN** `npx cap sync` is run after a Vite production build
- **THEN** the contents of `dist/` SHALL be copied to the iOS platform
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

### Requirement: Push Notification Delivery
The system SHALL deliver notification events from `add-notification-events` as native push notifications on iOS and Android. The backend event system (event types, dispatch, preferences, device registration) is defined in the `notification-events` capability.

#### Scenario: Request permission
- **WHEN** the user enables push notifications in settings
- **THEN** the system SHALL request native push notification permission via Capacitor Push Notifications plugin
- **AND** register the device token with the backend device registration API (`POST /api/v1/notifications/devices`)

#### Scenario: Receive push notification
- **WHEN** the backend dispatch service emits a notification event for a registered device
- **THEN** the native push notification SHALL be displayed with the event title and summary

#### Scenario: Notification tap
- **WHEN** the user taps a push notification
- **THEN** the app SHALL open and navigate to the content specified in the event's `payload.url`

#### Scenario: Token refresh
- **WHEN** the push notification token is refreshed by the OS
- **THEN** the system SHALL re-register the updated token with the backend

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

### Requirement: iOS Deployment Pipeline
The system SHALL provide a CI/CD pipeline for building, signing, and distributing the iOS app to TestFlight for beta testing.

#### Scenario: iOS code signing
- **WHEN** a CI build produces an iOS archive
- **THEN** the archive SHALL be signed using provisioning profiles and certificates managed by Fastlane Match
- **AND** Match SHALL store signing assets in a private Git repository
- **AND** the CI environment SHALL have access to the Match passphrase and Apple Developer credentials as secrets

#### Scenario: iOS beta distribution via TestFlight
- **WHEN** a signed `.ipa` is produced by CI
- **THEN** Fastlane `pilot` SHALL upload the build to TestFlight
- **AND** configured beta testers SHALL receive an automatic notification to install the new build
- **AND** the TestFlight build SHALL include the git commit SHA and build number in its metadata

#### Scenario: CI trigger
- **WHEN** a commit is merged to the main branch
- **THEN** the CI pipeline SHALL automatically build and distribute to TestFlight
- **AND** a manual workflow dispatch option SHALL also be available for on-demand builds

#### Scenario: Build versioning
- **WHEN** a CI build runs
- **THEN** the build number SHALL be set to the CI run number (monotonically increasing)
- **AND** the version string SHALL match the `package.json` version
- **AND** iOS `CFBundleVersion` and `CFBundleShortVersionString` SHALL be updated automatically

#### Scenario: Promotion to production
- **WHEN** a TestFlight beta build has been validated by testers
- **THEN** promotion to App Store review SHALL be a manual step
- **AND** the CI pipeline SHALL NOT automatically promote builds to the App Store
