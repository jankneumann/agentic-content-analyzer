## 1. Capacitor Setup

- [ ] 1.1 Install `@capacitor/core`, `@capacitor/cli` in `web/`
- [ ] 1.2 Run `npx cap init` with app ID and name, configure `capacitor.config.ts`
- [ ] 1.3 Add iOS platform (`npx cap add ios`)
- [ ] 1.4 Add Android platform (`npx cap add android`) — scaffolded only, deployment deferred
- [ ] 1.5 Configure `webDir` to point to Vite `dist/` output
- [ ] 1.6 Commit `ios/` and `android/` directories to git (Capacitor convention — native config must be version-controlled)

## 2. Platform Detection

- [ ] 2.1 Create `web/src/lib/platform.ts` with `isNative()`, `getPlatform()` utilities
- [ ] 2.2 Add `usePlatform` hook for React components that need platform-conditional rendering
- [ ] 2.3 Add platform info to telemetry resource attributes

## 3. Native Plugins

- [ ] 3.1 Install `@capacitor/push-notifications`, `@capacitor/haptics`, `@capacitor/status-bar`, `@capacitor/splash-screen`
- [ ] 3.2 Install `@capacitor-community/speech-recognition` for native STT
- [ ] 3.3 Install `@capacitor/network` for offline detection (share queue retry)
- [ ] 3.4 Install `@capacitor/app` for lifecycle events (share queue processing on foreground)
- [ ] 3.5 Install `@capacitor/preferences` for offline share URL queue persistence
- [ ] 3.6 Configure iOS permissions in `Info.plist` (microphone, speech recognition, push notifications)
- [ ] 3.7 Configure App Group capability (`group.com.aca.app`) on both main app and Share Extension targets

## 4. Backend CORS Configuration

- [ ] 4.1 Add `capacitor://localhost` to `ALLOWED_ORIGINS` in backend CORS configuration (WKWebView origin on iOS)
- [ ] 4.2 Add `http://localhost` to `ALLOWED_ORIGINS` (Android WebView origin)
- [ ] 4.3 Verify CORS headers returned correctly for Capacitor origins in dev and production profiles

## 5. Push Notification Delivery (foreground local notifications — MVP)

- [ ] 5.1 Create `web/src/lib/push-notifications.ts` with Capacitor Push Notifications plugin wrapper
- [ ] 5.2 Implement device token registration via backend API (`POST /api/v1/notifications/devices`) — future-proofing for remote push
- [ ] 5.3 Handle token refresh (re-register updated token with backend)
- [ ] 5.4 Add push notification opt-in toggle to settings UI (native platforms only)
- [ ] 5.5 Trigger local notifications from SSE events when app is foregrounded (MVP — no APNs server integration)
- [ ] 5.6 Handle notification tap — navigate to content via event `payload.url`

## 6. Native Share Target

- [ ] 6.1 Create iOS Share Extension target in Xcode project
- [ ] 6.2 Configure App Group entitlement on Share Extension target (`group.com.aca.app`)
- [ ] 6.3 Implement Share Extension handler: write shared URL to App Group `UserDefaults` suite
- [ ] 6.4 Configure Android intent filter for `text/plain` and URL shares in `AndroidManifest.xml` (scaffolded, deferred)
- [ ] 6.5 Implement main app handler: read pending URL from App Group shared container on `appStateChange` events
- [ ] 6.6 Validate shared URLs: reject non-http(s) schemes (`javascript:`, `data:`, etc.), enforce max URL length, sanitize before display
- [ ] 6.7 Call `POST /api/v1/content/save-url` with validated URL
- [ ] 6.8 Add confirmation toast after successful share save
- [ ] 6.9 Implement offline queue: on API failure, append URL to `pending_shares` in Capacitor Preferences
- [ ] 6.10 Implement queue flush: listen to `@capacitor/network` `networkStatusChange`, retry pending shares on reconnect
- [ ] 6.11 Dedup queued URLs by normalized string (prevent duplicate entries while offline)

## 7. Native STT Engine

- [ ] 7.1 Create `NativeSTTEngine` class implementing the `STTEngine` interface (from `add-on-device-stt`). Use lazy initialization — only import/initialize the Capacitor speech recognition plugin on first use.
- [ ] 7.2 Wire `@capacitor-community/speech-recognition` plugin to the engine interface
- [ ] 7.3 Update `AutoSTTEngine` to prefer `"native"` when running on Capacitor
- [ ] 7.4 Handle native STT permissions (request on first use, handle denial)

## 8. Status Bar and Theme

- [ ] 8.1 Integrate `@capacitor/status-bar` with the existing dark/light theme system
- [ ] 8.2 Update status bar style on theme toggle
- [ ] 8.3 Configure splash screen with app branding

## 9. Haptic Feedback

- [ ] 9.1 Create `web/src/lib/haptics.ts` with `triggerHaptic(style)` utility (no-op on web)
- [ ] 9.2 Add haptic feedback on voice input toggle
- [ ] 9.3 Add haptic feedback on content save confirmation

## 10. Build Scripts

- [ ] 10.1 Add `pnpm cap:dev` script — sets `VITE_API_URL=http://localhost:8000`, starts Vite dev server with live reload via `capacitor.config.ts` `server.url`
- [ ] 10.2 Add `pnpm cap:build` script — Vite production build + `cap sync` (uses `VITE_API_URL` from CI environment)
- [ ] 10.3 Add `pnpm cap:open:ios` script
- [ ] 10.4 Document build requirements (Xcode, macOS) in README

## 11. iOS Deployment Pipeline

- [ ] 11.1 Set up Fastlane Match for iOS code signing (private Git repo for profiles + certificates)
- [ ] 11.2 Create `ios/fastlane/Fastfile` with `build_app` and `upload_to_testflight` lanes
- [ ] 11.3 Create `.github/workflows/ios-build.yml` with macOS runner — trigger on merge to main only (not PRs, to manage cost at ~$0.08/min)
- [ ] 11.4 Configure CI secrets: Apple Developer credentials, Match passphrase
- [ ] 11.5 Implement automatic build versioning — set `CFBundleVersion` from CI run number, `CFBundleShortVersionString` from `package.json` version
- [ ] 11.6 Configure manual workflow dispatch for on-demand builds
- [ ] 11.7 Add TestFlight beta tester group configuration (Apple Developer Console)
- [ ] 11.8 Document promotion-to-App-Store steps (manual process)
- [ ] 11.9 Draft and host privacy policy covering data collection: device tokens, speech data, shared URLs
- [ ] 11.10 Add required App Store metadata: privacy policy URL, app description, screenshots, app icon assets

## 12. Testing

- [ ] 12.1 Add E2E tests for platform detection (mock Capacitor context)
- [ ] 12.2 Add E2E tests for share target flow (mocked)
- [ ] 12.3 Add E2E tests for push notification opt-in flow (mocked)
- [ ] 12.4 Add unit tests for URL validation in share handler (reject javascript:, data:, oversized URLs)
- [ ] 12.5 Add unit tests for offline queue (enqueue, dedup, flush on reconnect)
- [ ] 12.6 Manual testing checklist for iOS builds
- [ ] 12.7 Verify CI pipeline end-to-end: commit → build → TestFlight upload
- [ ] 12.8 Verify build versioning (monotonic build numbers, version from package.json)
