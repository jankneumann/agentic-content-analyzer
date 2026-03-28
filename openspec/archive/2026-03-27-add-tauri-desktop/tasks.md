## 1. Tauri Setup

- [ ] 1.1 Install Tauri v2 CLI and `@tauri-apps/api` in `web/`
- [ ] 1.2 Run `npx tauri init` and configure `tauri.conf.json` (app name, identifier, window settings)
- [ ] 1.3 Configure `src-tauri/Cargo.toml` with required Tauri features and plugins: enable `tray-icon` feature on `tauri` dependency, add `tauri-plugin-global-shortcut`, `tauri-plugin-notification`, `tauri-plugin-shell`
- [ ] 1.4 Configure Tauri v2 capabilities in `src-tauri/capabilities/default.json` — enable permissions for: `core:tray`, `global-shortcut:allow-register`, `global-shortcut:allow-unregister`, `notification:default`, `fs:allow-read`, `shell:allow-open`, `core:window:allow-set-always-on-top`, `core:window:allow-show`, `core:window:allow-set-focus`
- [ ] 1.5 Configure Vite to work with Tauri dev server (dev URL forwarding)
- [ ] 1.6 Add `src-tauri/target/` to `.gitignore`
- [ ] 1.7 Add `tauri://localhost` to `ALLOWED_ORIGINS` in backend CORS configuration

## 2. Platform Detection

- [ ] 2.1 Create `web/src/lib/platform.ts` with `isTauri()` function detecting `window.__TAURI_INTERNALS__`
- [ ] 2.2 Add `Platform` type (`'desktop' | 'web'`) and `getPlatform()` returning the correct value
- [ ] 2.3 Add `usePlatform` hook for React components that need platform-conditional rendering
- [ ] 2.4 Note: Capacitor detection (`isNative()`, `'ios' | 'android'` types) will be added by `add-capacitor-mobile` when it merges — do NOT reference `@capacitor/core` or `Capacitor` global

## 3. System Tray

- [ ] 3.1 Enable `tray-icon` feature in `[dependencies.tauri]` in Cargo.toml and configure tray permissions in `src-tauri/capabilities/default.json`
- [ ] 3.2 Create system tray with app icon using `tauri::tray::TrayIconBuilder` in `src-tauri/src/tray.rs`
- [ ] 3.3 Implement context menu: Open App, Ingest URL, Start Voice Input, Quit
- [ ] 3.4 Handle "Open App" action (show and focus main window)
- [ ] 3.5 Handle "Ingest URL" action (open small input dialog, call save-url API)
- [ ] 3.6 Handle "Start Voice Input" action (show voice overlay panel in main window)
- [ ] 3.7 Handle "Quit" action (exit app and remove tray)

## 4. Global Keyboard Shortcut

- [ ] 4.1 Add `tauri-plugin-global-shortcut` crate to `src-tauri/Cargo.toml` dependencies
- [ ] 4.2 Register `Cmd+Shift+Space` (macOS) / `Ctrl+Shift+Space` (Windows/Linux) as global shortcut on app start
- [ ] 4.3 Create floating voice input panel as a DOM overlay in the main window (bottom-right, styled with existing Tailwind design system)
- [ ] 4.4 Wire shortcut to toggle voice input: on activate → `setAlwaysOnTop(true)`, show overlay panel, start listening; on deactivate → stop listening, `setAlwaysOnTop(false)`, hide panel
- [ ] 4.5 Handle shortcut registration failure gracefully: log warning, display one-time notification suggesting manual shortcut configuration, voice input remains accessible via UI button
- [ ] 4.6 Add shortcut customization to settings UI (allow user to change the default binding)

## 5. Native File Drag-and-Drop

- [ ] 5.1 Listen for `tauri://file-drop` events on the main window
- [ ] 5.2 Validate dropped files: check extension against supported format list (PDF, DOCX, PPTX, XLSX, TXT, MD, HTML)
- [ ] 5.3 Validate dropped file SIZE against `MAX_UPLOAD_SIZE_MB` (default 500MB) — reject oversized files immediately with an error toast WITHOUT uploading
- [ ] 5.4 Upload valid files via `POST /api/v1/documents/upload`
- [ ] 5.5 Show drop zone overlay when files are dragged over the window (`tauri://file-drop-hover`)
- [ ] 5.6 Display success/error toast for each dropped file
- [ ] 5.7 Support multiple file drops with summary notification

## 6. Desktop Notification Delivery (depends on `add-notification-events` for backend)

- [ ] 6.1 Add `tauri-plugin-notification` crate to `src-tauri/Cargo.toml` dependencies
- [ ] 6.2 Request notification permission on first launch
- [ ] 6.3 Subscribe to backend SSE endpoint (`GET /api/v1/notifications/stream`) on app start
- [ ] 6.4 Handle SSE endpoint unavailability: if non-200 or connection refused, disable notifications silently with a warning log (no user-facing error) — graceful degradation
- [ ] 6.5 Convert incoming SSE events to native desktop notifications via Tauri notification plugin
- [ ] 6.6 Handle notification click — show/focus window, navigate via event `payload.url`
- [ ] 6.7 Implement SSE reconnection with `Last-Event-ID` for missed events

## 7. Build Scripts and CI

- [ ] 7.1 Add `pnpm tauri:dev` script (Tauri dev mode with Vite HMR)
- [ ] 7.2 Add `pnpm tauri:build` script (production build for current platform)
- [ ] 7.3 Create `.github/workflows/tauri-build.yml` — cross-platform GitHub Actions workflow with matrix: `macos-latest`, `windows-latest`, `ubuntu-latest`. Install Rust toolchain, webkit2gtk (Linux), and upload build artifacts.
- [ ] 7.4 Document Rust toolchain setup requirements in README/setup guide

## 8. Testing

- [ ] 8.1 Add E2E tests for platform detection (mock Tauri context via `window.__TAURI_INTERNALS__`)
- [ ] 8.2 Add E2E tests for drag-and-drop file upload (mocked)
- [ ] 8.3 Add E2E tests for file size validation rejection (oversized file mock)
- [ ] 8.4 Manual testing checklist for macOS, Windows, Linux builds
- [ ] 8.5 Test global shortcut registration, voice overlay panel show/hide, and `setAlwaysOnTop` toggle
