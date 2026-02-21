## 1. Capacitor Setup

- [ ] 1.1 Install `@capacitor/core`, `@capacitor/cli` in `web/`
- [ ] 1.2 Run `npx cap init` with app ID and name, configure `capacitor.config.ts`
- [ ] 1.3 Add iOS platform (`npx cap add ios`)
- [ ] 1.4 Add Android platform (`npx cap add android`)
- [ ] 1.5 Configure `webDir` to point to Vite `dist/` output
- [ ] 1.6 Add `ios/` and `android/` to `.gitignore` (or commit — decide convention)

## 2. Platform Detection

- [ ] 2.1 Create `web/src/lib/platform.ts` with `isNative()`, `getPlatform()` utilities
- [ ] 2.2 Add `usePlatform` hook for React components that need platform-conditional rendering
- [ ] 2.3 Add platform info to telemetry resource attributes

## 3. Native Plugins

- [ ] 3.1 Install `@capacitor/push-notifications`, `@capacitor/haptics`, `@capacitor/status-bar`, `@capacitor/splash-screen`
- [ ] 3.2 Install `@capacitor-community/speech-recognition` for native STT
- [ ] 3.3 Configure iOS permissions in `Info.plist` (microphone, speech recognition, push notifications)
- [ ] 3.4 Configure Android permissions in `AndroidManifest.xml` (microphone, speech recognition)

## 4. Push Notification Delivery (depends on `add-notification-events` for backend)

- [ ] 4.1 Create `web/src/lib/push-notifications.ts` with Capacitor Push Notifications plugin wrapper
- [ ] 4.2 Implement device token registration via backend API (`POST /api/v1/notifications/devices`)
- [ ] 4.3 Handle token refresh (re-register updated token with backend)
- [ ] 4.4 Add push notification opt-in toggle to settings UI (native platforms only)
- [ ] 4.5 Handle notification tap — navigate to content via event `payload.url`

## 5. Native Share Target

- [ ] 5.1 Configure Android intent filter in `AndroidManifest.xml` for receiving text/URL shares
- [ ] 5.2 Create iOS Share Extension target in Xcode project
- [ ] 5.3 Implement share handler that extracts URL and calls `save-url` API
- [ ] 5.4 Add confirmation toast after successful share save
- [ ] 5.5 Add offline queue for shares when device is disconnected

## 6. Native STT Engine

- [ ] 6.1 Create `NativeSTTEngine` class implementing the `STTEngine` interface (from `add-on-device-stt`)
- [ ] 6.2 Wire `@capacitor-community/speech-recognition` plugin to the engine interface
- [ ] 6.3 Update `AutoSTTEngine` to prefer `"native"` when running on Capacitor
- [ ] 6.4 Handle native STT permissions (request on first use, handle denial)

## 7. Status Bar and Theme

- [ ] 7.1 Integrate `@capacitor/status-bar` with the existing dark/light theme system
- [ ] 7.2 Update status bar style on theme toggle
- [ ] 7.3 Configure splash screen with app branding

## 8. Haptic Feedback

- [ ] 8.1 Create `web/src/lib/haptics.ts` with `triggerHaptic(style)` utility (no-op on web)
- [ ] 8.2 Add haptic feedback on voice input toggle
- [ ] 8.3 Add haptic feedback on content save confirmation

## 9. Build Scripts

- [ ] 9.1 Add `pnpm cap:dev` script (Vite dev server + live reload)
- [ ] 9.2 Add `pnpm cap:build` script (Vite build + cap sync)
- [ ] 9.3 Add `pnpm cap:open:ios` and `pnpm cap:open:android` scripts
- [ ] 9.4 Document build requirements (Xcode, Android Studio) in README

## 10. Testing

- [ ] 10.1 Add E2E tests for platform detection (mock Capacitor context)
- [ ] 10.2 Add E2E tests for share target flow (mocked)
- [ ] 10.3 Add E2E tests for push notification opt-in flow (mocked)
- [ ] 10.4 Manual testing checklist for iOS and Android builds
