## Context

The app is a React SPA (TanStack Router, Vite, Tailwind v4) deployed as a PWA with service worker caching, offline fallback, and iOS safe-area support already implemented. The backend is a FastAPI server with CORS configured. Mobile users currently access the app via Safari/Chrome PWA install or the browser. Content capture on mobile uses iOS Shortcuts hitting the `save-url` API. The voice input system (from `add-voice-input` and `add-on-device-stt`) provides browser-based and on-device STT.

Capacitor adds a native shell around the same web build, enabling native APIs without rewriting the frontend.

## Goals / Non-Goals

**Goals:**
- Wrap the existing Vite build in Capacitor for iOS (Android scaffolded, deployment deferred)
- Deliver native push notifications by consuming the shared backend notification event system (from `add-notification-events`)
- Implement native share target to receive URLs from other apps (replacing iOS Shortcuts for content capture)
- Add Capacitor native speech recognition as a third STT engine option
- Maintain PWA as the primary web deployment — Capacitor is additive, not replacing
- Provide build scripts for local development and CI

**Non-Goals:**
- Native UI components (keep everything as web views)
- Offline-first data sync (app requires API connectivity)
- Full App Store production release workflow (initial deployment targets TestFlight beta only)
- Android deployment pipeline (deferred to a separate proposal — no test device available)
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
| Share target (outgoing) | `@capacitor/share` (official) — for sharing *from* the app to other apps |
| Share target (receiving) | Custom native code: iOS Share Extension + Android intent filter (no plugin) |
| Network status | `@capacitor/network` (official) — offline detection for share queue retry |
| App lifecycle | `@capacitor/app` (official) — foreground/background events for share queue processing |
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

### 4. Share target via Android intent filter + iOS Share Extension

**Choice**: Configure Android `AndroidManifest.xml` with an intent filter for `text/plain` and URL shares. For iOS, add a Share Extension that forwards URLs to the main app via an App Group shared container.

**Note on plugin scope**: `@capacitor/share` only supports *outgoing* shares (sharing from the app to other apps). Receiving shared content requires custom native code — an iOS Share Extension and an Android intent filter. There is no Capacitor plugin for receiving shares.

**iOS Share Extension architecture**: The Share Extension runs in a separate process with a 120MB memory limit and no access to the main app's WKWebView or JavaScript context. Communication between the extension and the main app uses:
1. **App Groups shared container** — the Share Extension writes the shared URL to a `UserDefaults` suite shared via App Group (e.g., `group.com.aca.app`). This requires configuring the App Group capability in both the main app and the Share Extension targets.
2. **URL scheme activation** — after writing to the shared container, the extension opens the `aca://` URL scheme to bring the main app to the foreground. The main app reads the pending URL from the shared container on activation.
3. **Fallback for background app** — if the main app is already running, it checks the shared container on `appStateChange` events (Capacitor `App` plugin) to pick up queued shares.

**Share Extension authentication**: The extension process has no access to the main app's cookie jar or Keychain items (unless explicitly shared). Rather than sharing credentials across processes, the extension **queues URLs in the App Group shared container** and the main app processes them on next activation. This avoids credential sharing and simplifies the security model — the main app already has valid auth context.

**Rationale**: This is the standard Capacitor pattern for receiving shared content. The queued-URL approach avoids the complexity of sharing auth tokens across process boundaries while ensuring no shared URLs are lost.

### 5. Native STT as engine option

**Choice**: Add `"native"` as a fourth engine option in the voice input system (alongside `"browser"`, `"on-device"`, `"auto"`). When running on Capacitor, `"auto"` prefers `"native"` over `"browser"`.

**Rationale**: Native speech recognition (iOS Speech framework, Android SpeechRecognizer) offers better accuracy, offline support (on recent OS versions), and tighter system integration than the Web Speech API. The engine abstraction from `add-on-device-stt` makes this a clean addition.

### 6. Deployment model: CI/CD → TestFlight (iOS only)

**Choice**: Use GitHub Actions with macOS runners for iOS builds. Distribute iOS betas via TestFlight. Use Fastlane for build automation, code signing, and store upload. Android deployment is deferred to a separate proposal (no test device available).

**Pipeline stages:**
1. **Build**: On merge to main (or manual trigger), CI runs `pnpm build && npx cap sync`, then builds the iOS archive
2. **iOS signing**: Fastlane Match manages provisioning profiles and certificates in a private Git repo. CI exports a signed `.ipa` via `xcodebuild archive` + `exportArchive`
3. **iOS distribution**: Fastlane `pilot upload_build` pushes the `.ipa` to TestFlight. Beta testers are invited via Apple Developer Console
4. **Promotion to production**: Manual step — after beta validation, promote TestFlight build to App Store review

**Alternatives considered:**
- **Manual Xcode uploads**: Error-prone, doesn't scale, requires developer machine for every release
- **Expo EAS Build**: Designed for React Native/Expo, not Capacitor. Would require ejecting or extensive workarounds
- **Appflow (Ionic)**: Ionic's paid CI/CD service. Works well with Capacitor but adds cost ($499/mo for team plan) and vendor lock-in
- **Codemagic**: Good Capacitor support but adds another CI vendor alongside GitHub Actions

**Rationale**: GitHub Actions + Fastlane is the standard open-source approach for Capacitor apps. Fastlane handles the painful parts (code signing, provisioning, store uploads) while GitHub Actions provides the CI infrastructure already used by the project. TestFlight is Apple's native beta channel — no extra services needed. The pipeline is free for public repos and costs ~$0.08/min for macOS runners on private repos.

**Developer account requirements:**
- **Apple Developer Program**: $99/year. Required for TestFlight, App Store, and code signing certificates

**Deferred to separate proposal:**
- Android release signing (keystore management)
- Play Store internal testing track and production distribution
- Google Play Developer account setup ($25 one-time)

### 7. Push notifications scoped to foreground local notifications (MVP)

**Choice**: For the initial release, push notifications are **local notifications triggered by SSE events while the app is foregrounded or recently backgrounded**. True remote push (APNs/FCM server-side integration) is deferred to a follow-up proposal.

**Rationale**: The existing backend notification system uses SSE for real-time delivery. Adding server-side APNs integration requires: an APNs signing key, a push dispatch service, and changes to `notification_service.py` to send HTTP/2 requests to Apple's push servers. This is a significant backend addition that contradicts the "no new backend services" goal. Local notifications via the Capacitor Push Notifications plugin (listening to SSE events while the app is active) provide immediate value with zero backend changes. Remote push is tracked as a follow-up.

**What this means**:
- Notifications appear as native banners while the app is in the foreground
- When the app is fully closed/suspended, notifications are NOT delivered (requires APNs — deferred)
- Device token registration still happens (future-proofing for remote push)

### 8. Offline share queue via Capacitor Preferences

**Choice**: Use the `@capacitor/preferences` plugin (key-value storage) to queue shared URLs when the device is offline. The `@capacitor/network` plugin detects connectivity changes to trigger retry.

**Queue mechanism:**
1. Share Extension writes URL to App Group shared container
2. Main app reads URL from shared container on activation
3. If API call fails (network error), URL is appended to a JSON array in Capacitor Preferences under key `pending_shares`
4. `@capacitor/network` `networkStatusChange` listener triggers flush of pending shares when connectivity is restored
5. Dedup: URLs are compared by normalized string before queueing (same URL shared twice while offline → stored once)

**Rationale**: Capacitor Preferences is persistent, synchronous, and available on all platforms. It's simpler than IndexedDB for a small queue of URLs. The Network plugin provides reliable connectivity change events.

### 9. Native platform directories committed to git

**Choice**: Commit `ios/` and `android/` directories to version control.

**Rationale**: The native project directories contain critical configuration that must be version-controlled:
- `Info.plist` with permissions, URL schemes, and App Group entitlements
- Share Extension target and source files
- `capacitor.config.ts` server settings
- Fastlane configuration under `ios/fastlane/`

Gitignoring these would require every developer and CI to run `npx cap add ios` on fresh clones, losing all manual native configuration. The Capacitor convention is to commit native project files.

### 10. Backend URL via VITE_API_URL (resolved)

**Choice**: Use the existing `VITE_API_URL` environment variable, which is already baked into the Vite build. No new configuration mechanism needed.

- `pnpm cap:dev` → dev server uses `VITE_API_URL=http://localhost:8000` (or the Vite proxy)
- `pnpm cap:build` → production build uses `VITE_API_URL` set in CI environment (production API URL)
- `capacitor.config.ts` `server.url` is only set in dev mode (for live reload); production builds serve from bundled files

**Rationale**: The frontend already uses `VITE_API_URL` everywhere via the API client. Capacitor doesn't change how the web app resolves its API base URL — it just wraps the same build output. No new configuration surface is needed.

### 11. CORS for Capacitor native origin

**Choice**: Add `capacitor://localhost` and `http://localhost` to `ALLOWED_ORIGINS` in the backend CORS configuration.

**Rationale**: WKWebView on iOS uses `capacitor://localhost` as the request origin, which differs from the PWA's web origin. Without this, all API calls from the native app are rejected by CORS. `http://localhost` is needed for Android WebView. These are added to the development and production CORS configuration — they are safe because they can only originate from the native app itself.

### 12. Deep linking deferred to follow-up

**Choice**: Deep linking via `aca://` URL scheme is **deferred to a separate proposal**. The initial release focuses on the share target flow (which uses App Groups, not deep links for IPC) and direct app launch.

**Rationale**: Deep linking requires Universal Links (AASA file hosting, domain association), URL scheme registration, and route handler integration in the frontend router. This is orthogonal to the core Capacitor shell functionality and can be added incrementally. The share target uses App Group shared container for IPC, not URL scheme deep links.

## Risks / Trade-offs

- **Capacitor version lag**: Capacitor releases may lag behind iOS/Android SDK updates. → Pin Capacitor major version, update quarterly.
- **Plugin compatibility**: Community speech-recognition plugin may break on major Capacitor updates. → Pin version, monitor releases.
- **App store review**: Apple/Google review adds friction to releases. → Keep native-specific code minimal to reduce rejection risk.
- **WKWebView limitations on iOS**: Some Web APIs (e.g., Web Speech API) behave differently in WKWebView. → Use native STT plugin instead of Web Speech API on iOS.
- **Build complexity**: Requires Xcode (macOS only) for iOS builds. → CI builds on macOS runners.
- **Two deployment channels**: PWA and native app need to stay in sync. → Both use the same Vite build; Capacitor syncs from `dist/`.

## Resolved Questions

- **Push notification opt-in**: Settings UI toggle (Decision 7). Avoids aggressive permission prompts on first launch.
- **Backend URL configuration**: Uses existing `VITE_API_URL` (Decision 10). No new configuration mechanism needed.
