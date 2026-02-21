## 1. Tauri Setup

- [ ] 1.1 Install Tauri v2 CLI and `@tauri-apps/api` in `web/`
- [ ] 1.2 Run `npx tauri init` and configure `tauri.conf.json` (app name, identifier, window settings)
- [ ] 1.3 Configure `src-tauri/Cargo.toml` with required Tauri plugins
- [ ] 1.4 Configure Vite to work with Tauri dev server (dev URL forwarding)
- [ ] 1.5 Add `src-tauri/target/` to `.gitignore`

## 2. Platform Detection

- [ ] 2.1 Extend `web/src/lib/platform.ts` to detect Tauri via `window.__TAURI_INTERNALS__`
- [ ] 2.2 Add `isTauri()` function returning boolean
- [ ] 2.3 Update `getPlatform()` to return `"desktop"` when running in Tauri

## 3. System Tray

- [ ] 3.1 Add `tauri-plugin-tray` to Rust dependencies
- [ ] 3.2 Create system tray with app icon in `src-tauri/src/tray.rs`
- [ ] 3.3 Implement context menu: Open App, Ingest URL, Start Voice Input, Quit
- [ ] 3.4 Handle "Open App" action (show and focus main window)
- [ ] 3.5 Handle "Ingest URL" action (open small input dialog, call save-url API)
- [ ] 3.6 Handle "Start Voice Input" action (launch floating overlay)
- [ ] 3.7 Handle "Quit" action (exit app and remove tray)

## 4. Global Keyboard Shortcut

- [ ] 4.1 Add `tauri-plugin-global-shortcut` to Rust dependencies
- [ ] 4.2 Register `Cmd+Shift+V` / `Ctrl+Shift+V` as global shortcut on app start
- [ ] 4.3 Create floating voice input overlay window (small, always-on-top, transparent background)
- [ ] 4.4 Wire shortcut to toggle voice input and show/hide floating overlay
- [ ] 4.5 Handle shortcut registration failure gracefully (log warning, no crash)
- [ ] 4.6 Add shortcut customization to settings UI

## 5. Native File Drag-and-Drop

- [ ] 5.1 Listen for `tauri://file-drop` events on the main window
- [ ] 5.2 Validate dropped files against supported format list (PDF, DOCX, PPTX, XLSX, TXT, MD, HTML)
- [ ] 5.3 Upload valid files via `POST /api/v1/documents/upload`
- [ ] 5.4 Show drop zone overlay when files are dragged over the window
- [ ] 5.5 Display success/error toast for each dropped file
- [ ] 5.6 Support multiple file drops with summary notification

## 6. Desktop Notification Delivery (depends on `add-notification-events` for backend)

- [ ] 6.1 Add `tauri-plugin-notification` to Rust dependencies
- [ ] 6.2 Request notification permission on first launch
- [ ] 6.3 Subscribe to backend SSE endpoint (`GET /api/v1/notifications/stream`) on app start
- [ ] 6.4 Convert incoming SSE events to native desktop notifications via Tauri notification plugin
- [ ] 6.5 Handle notification click — show/focus window, navigate via event `payload.url`
- [ ] 6.6 Implement SSE reconnection with `Last-Event-ID` for missed events

## 7. Build Scripts

- [ ] 7.1 Add `pnpm tauri:dev` script (Tauri dev mode with Vite HMR)
- [ ] 7.2 Add `pnpm tauri:build` script (production build for current platform)
- [ ] 7.3 Add `pnpm tauri:build:all` script (cross-platform builds via CI)
- [ ] 7.4 Document Rust toolchain setup requirements

## 8. Testing

- [ ] 8.1 Add E2E tests for platform detection (mock Tauri context)
- [ ] 8.2 Add E2E tests for drag-and-drop file upload (mocked)
- [ ] 8.3 Manual testing checklist for macOS, Windows, Linux builds
- [ ] 8.4 Test global shortcut registration and voice overlay flow
