## Context

The app is a React SPA (TanStack Router, Vite, Tailwind v4) deployed as a PWA with service worker caching, offline fallback, and iOS safe-area support already implemented. The backend is a FastAPI server with CORS configured. Mobile users currently access the app via Safari/Chrome PWA install or the browser. Content capture on mobile uses iOS Shortcuts hitting the `save-url` API. The voice input system (from `add-voice-input` and `add-on-device-stt`) provides browser-based and on-device STT.

Capacitor adds a native shell around the same web build, enabling native APIs without rewriting the frontend.

## Goals / Non-Goals

**Goals:**
- Wrap the existing Vite build in Capacitor for iOS and Android
- Deliver native push notifications by consuming the shared backend notification event system (from `add-notification-events`)
- Implement native share target to receive URLs from other apps (replacing iOS Shortcuts for content capture)
- Add Capacitor native speech recognition as a third STT engine option
- Maintain PWA as the primary web deployment — Capacitor is additive, not replacing
- Provide build scripts for local development and CI

**Non-Goals:**
- Native UI components (keep everything as web views)
- Offline-first data sync (app requires API connectivity)
- Full App Store production release workflow (initial deployment targets beta channels only)
- Background fetch / background processing (beyond push notifications)
- Tablet-specific layouts (responsive web layout handles this)

## Decisions

### 1. Capacitor over React Native or Flutter

**Choice**: Capacitor (Ionic) to wrap the existing web app.

**Alternatives considered**:
- **React Native**: Requires rewriting all components with RN primitives. Massive effort for marginal UX gain.
- **Flutter**: Different language (Dart), complete rewrite. No code sharing with existing React app.
- **Expo**: React Native variant, same rewrite issue.
- **TWA (Trusted Web Activity)**: Android-only, no native API access.

**Rationale**: Capacitor uses the existing web build as-is, adding native plugins via a thin bridge. Zero frontend rewrite. The existing PWA already handles responsive layout, safe-area insets, and offline fallback — Capacitor just adds native capabilities on top.

### 2. Plugin selection

**Choice**: Use official Capacitor plugins where available, community plugins for gaps.

| Capability | Plugin |
|-----------|--------|
| Push notifications | `@capacitor/push-notifications` (official) |
| Share target | `@capacitor/share` (official, for sending); Android intent filter + iOS share extension for receiving |
| Haptics | `@capacitor/haptics` (official) |
| Status bar | `@capacitor/status-bar` (official) |
| Speech recognition | `@capacitor-community/speech-recognition` (community) |
| Splash screen | `@capacitor/splash-screen` (official) |

**Rationale**: Official plugins are maintained by the Ionic team with guaranteed Capacitor version compatibility. Community speech recognition plugin is mature and well-maintained.

### 3. Platform detection via utility function

**Choice**: Create a `web/src/lib/platform.ts` utility that detects Capacitor native context vs. web browser.

```typescript
import { Capacitor } from '@capacitor/core';
export const isNative = () => Capacitor.isNativePlatform();
export const getPlatform = () => Capacitor.getPlatform(); // 'ios' | 'android' | 'web'
```

**Rationale**: Conditional logic throughout the app (e.g., use native STT vs browser STT, show push notification opt-in vs. skip) needs a single source of truth for platform detection. Capacitor provides this API natively.

### 4. Share target via Android intent filter + iOS app extension

**Choice**: Configure Android `AndroidManifest.xml` with an intent filter for `text/plain` and URL shares. For iOS, add a Share Extension that forwards URLs to the web view.

**Rationale**: This is the standard Capacitor pattern for receiving shared content. The shared URL is routed to the existing `save-url` API endpoint.

### 5. Native STT as engine option

**Choice**: Add `"native"` as a fourth engine option in the voice input system (alongside `"browser"`, `"on-device"`, `"auto"`). When running on Capacitor, `"auto"` prefers `"native"` over `"browser"`.

**Rationale**: Native speech recognition (iOS Speech framework, Android SpeechRecognizer) offers better accuracy, offline support (on recent OS versions), and tighter system integration than the Web Speech API. The engine abstraction from `add-on-device-stt` makes this a clean addition.

### 6. Deployment model: CI/CD → TestFlight / Play Store internal track

**Choice**: Use GitHub Actions with macOS runners for iOS builds and Linux runners for Android builds. Distribute iOS betas via TestFlight and Android betas via Play Store internal testing track. Use Fastlane for build automation, code signing, and store upload.

**Pipeline stages:**
1. **Build**: On merge to main (or manual trigger), CI runs `pnpm build && npx cap sync`, then builds native archives
2. **iOS signing**: Fastlane Match manages provisioning profiles and certificates in a private Git repo. CI exports a signed `.ipa` via `xcodebuild archive` + `exportArchive`
3. **iOS distribution**: Fastlane `pilot upload_build` pushes the `.ipa` to TestFlight. Beta testers are invited via Apple Developer Console
4. **Android signing**: Release keystore stored as CI secret. Gradle `assembleRelease` produces a signed `.aab` (App Bundle)
5. **Android distribution**: Fastlane `supply` (or direct Play Console API) uploads the `.aab` to the internal testing track. Testers opt in via a Play Store link
6. **Promotion to production**: Manual step — after beta validation, promote TestFlight build to App Store review / promote internal track to production in Play Console

**Alternatives considered:**
- **Manual Xcode/Android Studio uploads**: Error-prone, doesn't scale, requires developer machine for every release
- **Expo EAS Build**: Designed for React Native/Expo, not Capacitor. Would require ejecting or extensive workarounds
- **Appflow (Ionic)**: Ionic's paid CI/CD service. Works well with Capacitor but adds cost ($499/mo for team plan) and vendor lock-in
- **Codemagic**: Good Capacitor support but adds another CI vendor alongside GitHub Actions

**Rationale**: GitHub Actions + Fastlane is the standard open-source approach for Capacitor apps. Fastlane handles the painful parts (code signing, provisioning, store uploads) while GitHub Actions provides the CI infrastructure already used by the project. TestFlight and Play Store internal track are the native beta channels — no extra services needed. The pipeline is free for public repos and costs ~$0.08/min for macOS runners on private repos.

**Developer account requirements:**
- **Apple Developer Program**: $99/year. Required for TestFlight, App Store, and code signing certificates
- **Google Play Developer**: $25 one-time. Required for Play Store internal testing and production

## Risks / Trade-offs

- **Capacitor version lag**: Capacitor releases may lag behind iOS/Android SDK updates. → Pin Capacitor major version, update quarterly.
- **Plugin compatibility**: Community speech-recognition plugin may break on major Capacitor updates. → Pin version, monitor releases.
- **App store review**: Apple/Google review adds friction to releases. → Keep native-specific code minimal to reduce rejection risk.
- **WKWebView limitations on iOS**: Some Web APIs (e.g., Web Speech API) behave differently in WKWebView. → Use native STT plugin instead of Web Speech API on iOS.
- **Build complexity**: Requires Xcode (macOS only) for iOS builds. → CI builds on macOS runners.
- **Two deployment channels**: PWA and native app need to stay in sync. → Both use the same Vite build; Capacitor syncs from `dist/`.

## Open Questions

- Should push notifications be opt-in via settings UI or prompted on first app launch? (Leaning: settings UI — avoid aggressive permission requests.)
- Should the native app connect to a configurable backend URL or hardcode production? (Leaning: configurable via settings, default to production.)
