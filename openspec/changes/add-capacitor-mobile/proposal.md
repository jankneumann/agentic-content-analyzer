## Why

The application runs as a PWA, which works well for mobile access but lacks native platform capabilities — push notifications, background processing, native share targets, and native speech recognition with offline support. Capacitor wraps the existing web app in a native iOS shell, providing access to native APIs while reusing 100% of the existing frontend code. This is the lowest-friction path to a native mobile app given the existing React SPA. Android platform support is scaffolded but deployment is deferred to a separate proposal.

## What Changes

- Add Capacitor configuration to the existing `web/` directory (iOS platform; Android scaffolded but deployment deferred)
- Configure native splash screens, icons, and app metadata
- Add Capacitor plugins for: push notifications, share target (receive shared URLs), native speech recognition, haptic feedback, and status bar control
- Implement a platform detection utility to switch between web APIs and Capacitor native APIs
- Add a native share target handler that routes shared URLs to the existing `save-url` API
- Integrate Capacitor's native speech recognition plugin as an additional engine option in the voice input system
- Add build scripts and CI configuration for iOS builds
- Configure deep linking for `aca://` URL scheme
- Define iOS deployment pipeline: code signing via Fastlane Match, TestFlight beta distribution, CI/CD for automated builds

## Capabilities

### New Capabilities
- `capacitor-mobile`: Native mobile shell via Capacitor, including platform detection, native plugin integration, build configuration, and app store distribution support
- `native-share-target`: Receive shared URLs from other apps via the native share sheet, routing to the content save API

### Modified Capabilities
- `voice-input`: Add `"native"` engine option for Capacitor's native speech recognition plugin
- `content-capture`: Add native share target as a content capture method alongside existing bookmarklet and iOS Shortcuts

## Impact

- **Frontend**: Platform detection utility, conditional plugin imports, Capacitor config files
- **Build**: New `npx cap sync`, `npx cap open ios` commands; Xcode for native builds
- **Dependencies**: `@capacitor/core`, `@capacitor/ios`, `@capacitor/android` (scaffolded), plus plugins (`@capacitor/push-notifications`, `@capacitor/share`, `@capacitor/haptics`, `@capacitor/status-bar`, `@capgo/capacitor-native-audio` or equivalent STT plugin)
- **Infrastructure**: No new backend services — Capacitor consumes existing API and notification event system (from `add-notification-events`)
- **Distribution**: iOS via TestFlight (beta) → App Store. CI/CD automates builds; requires Apple Developer Program ($99/yr). Android deployment deferred to a separate proposal
- **Signing**: iOS provisioning profiles + certificates managed via Fastlane Match
- **Existing PWA**: Unchanged — Capacitor wraps the same build output, PWA continues to work independently
