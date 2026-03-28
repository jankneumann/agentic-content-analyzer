## Context

The app runs as a PWA in the browser and (with the `add-capacitor-mobile` change, implemented in parallel) as a native mobile app. Desktop users currently use the PWA in a browser tab, which lacks system tray, global hotkeys, and native drag-and-drop. Tauri v2 provides a Rust-based native shell that wraps the existing Vite build with a ~5MB binary, much lighter than Electron (~100MB).

The voice input system (from `add-voice-input` and `add-on-device-stt`) needs a global hotkey trigger. The content capture system needs native file drag-and-drop with client-side validation.

**Parallel implementation**: `add-capacitor-mobile` is being implemented concurrently. Both features write to `web/src/lib/platform.ts` and `web/package.json`. The coordinator's merge queue handles ordering — work packages declare lock keys for these shared resources.

## Goals / Non-Goals

**Goals:**
- Wrap the existing Vite build in Tauri v2 for macOS, Windows, and Linux
- Provide system tray with digest notification badges and quick actions
- Implement global keyboard shortcut for voice input toggle (non-conflicting default)
- Enable native file drag-and-drop for document ingestion with size validation
- Deliver desktop notifications by subscribing to the shared backend SSE event stream (from `add-notification-events`) with graceful degradation
- Configure Tauri v2 capability-based permissions for all plugins
- Provide build scripts and CI configuration for cross-platform builds

**Non-Goals:**
- Custom native UI (keep everything as web views)
- Auto-update mechanism (manual updates initially; Tauri updater in future)
- Tray-only mode (app always has a window, tray is supplementary)
- System-level audio capture for transcription
- Native menu bar customization beyond system tray
- Deep linking via `aca://` URL scheme (deferred to separate proposal)
- Rust-based STT engine (use existing webview-hosted engines)

## Decisions

### 1. Tauri v2 over Electron

**Choice**: Tauri v2 with Rust backend.

**Alternatives considered**:
- **Electron**: Mature ecosystem but ~100MB binary (bundles Chromium), high memory usage. Overkill for a web-view wrapper.
- **Neutralinojs**: Lighter than Electron but less mature plugin ecosystem and community.
- **Wails (Go)**: Similar to Tauri but smaller ecosystem and less native API coverage.

**Rationale**: Tauri v2 uses the system webview (WebKit on macOS, WebView2 on Windows, webkit2gtk on Linux), resulting in ~5MB binaries. Rust backend provides system-level access (tray, shortcuts, file system) with strong safety guarantees. Tauri v2's plugin system covers all needed capabilities.

### 2. System tray via built-in TrayIconBuilder (not a plugin)

**Choice**: Use Tauri v2's built-in `tauri::tray::TrayIconBuilder` API with the `tray-icon` feature flag on the `tauri` dependency.

**Note**: In Tauri v2, the system tray is a core feature — NOT a separate plugin (unlike Tauri v1). Enable the `tray-icon` feature in `Cargo.toml` under `[dependencies.tauri]` features, and configure tray permissions in `src-tauri/capabilities/default.json`.

**Menu**: Persistent system tray icon with a context menu: Open App, Ingest URL (text input), Start Voice Input, Recent Digests, Quit.

**Rationale**: System tray is the standard desktop pattern for background-accessible apps. Quick actions let users ingest URLs and start voice input without switching to the app window.

### 3. Global shortcut: `Cmd+Shift+Space` / `Ctrl+Shift+Space`

**Choice**: Use `tauri-plugin-global-shortcut` to register `Cmd+Shift+Space` (macOS) / `Ctrl+Shift+Space` (Windows/Linux) as a global voice input hotkey.

**Alternatives rejected**:
- `Ctrl+Shift+V` / `Cmd+Shift+V`: **Conflicts with "Paste without formatting"** in most apps (browsers, Google Docs, VS Code, Slack, Terminal) — would be immediately reported as a bug.
- `Ctrl+Alt+V`: Alt-based combos have accessibility software conflicts on Windows.
- `Ctrl+Shift+M`: Conflicts with mute in Meet/Teams/Zoom.

**Rationale**: `Ctrl+Shift+Space` / `Cmd+Shift+Space` has the fewest conflicts — `Ctrl+Space` is used for input method switching in some locales, but `Ctrl+Shift+Space` is rarely claimed. The shortcut is configurable in settings as a fallback. Registration failure is handled gracefully (log warning, voice input remains accessible via UI button).

### 4. Native drag-and-drop with client-side size validation

**Choice**: Listen to Tauri's `tauri://file-drop` event to receive dropped files. Before uploading, validate:
1. File extension against supported formats (PDF, DOCX, PPTX, etc.)
2. **File size against `MAX_UPLOAD_SIZE_MB` (default 500MB)** — reject oversized files immediately with an error toast, WITHOUT starting an upload
3. Upload via the existing `POST /api/v1/documents/upload` API

**Rationale**: Tauri provides native file drop events out of the box. Files bypass the browser sandbox so have full filesystem paths. Client-side size validation prevents wasting bandwidth on files the server will reject. The same `FILE_SIGNATURES` check runs server-side as defense in depth.

### 5. Platform detection: create file, design for parallel merge

**Choice**: Create `web/src/lib/platform.ts` with Tauri detection. Since `add-capacitor-mobile` also creates this file in parallel, each feature creates its own version:

```typescript
// Tauri version (this feature)
export const isTauri = (): boolean =>
  typeof window !== 'undefined' && Boolean((window as any).__TAURI_INTERNALS__);

export type Platform = 'desktop' | 'web';

export const getPlatform = (): Platform => {
  if (isTauri()) return 'desktop';
  return 'web';
};
```

**Merge strategy**: Whichever feature merges first establishes the file. The second feature rebases and adds its platform detection branch. The coordinator's merge queue ensures ordering. The `Platform` type union expands when Capacitor merges (adds `'ios' | 'android'`).

**Important**: No reference to `Capacitor.isNativePlatform()` in this version — that import would throw `ReferenceError` since `@capacitor/core` is not installed. Capacitor detection is added by `add-capacitor-mobile` when it merges.

### 6. Voice overlay: single-window DOM approach

**Choice**: Implement the floating voice input overlay as a **DOM panel within the main window**, not as a separate Tauri window.

**Alternatives considered**:
- **Multi-window (separate Tauri window)**: Requires a second HTML entry point, complex window lifecycle management (create/destroy), IPC between windows for transcript data, and separate `transparent: true` + `decorations: false` + `always_on_top: true` configuration. Significantly more complex.

**Approach**:
1. When the global hotkey is pressed, call `window.__TAURI_INTERNALS__` → `WebviewWindow.getCurrent().setAlwaysOnTop(true)` on the main window temporarily
2. Show a floating `<div>` panel positioned at the bottom-right of the window with the voice input transcript
3. When voice input stops or the overlay is dismissed, call `setAlwaysOnTop(false)`
4. If the main window is minimized/hidden when the hotkey is pressed, first show and focus it

**Rationale**: Single-window approach is dramatically simpler — no IPC, no window lifecycle, no separate entry point. The UX is similar (overlay appears on screen) without the multi-window complexity.

### 7. Authentication: webview inherits session cookies

**Choice**: Tauri's webview inherits cookies from the login flow (same-origin). No special auth handling needed.

**Rationale**: The Tauri app loads the frontend from bundled assets and makes API requests to the configured backend URL. Since the web app already handles login via session cookies (from `add-user-authentication`), and Tauri's webview manages cookies like a regular browser, authentication works without modification.

**CORS**: Add `tauri://localhost` to `ALLOWED_ORIGINS` for the Tauri webview origin.

### 8. Desktop notifications: graceful degradation

**Choice**: Subscribe to `GET /api/v1/notifications/stream` (from `add-notification-events`) on app start. If the endpoint is unavailable (non-200, connection refused, or timeout), disable notifications silently with a warning log — no user-facing error.

**Reconnection**: Implement SSE reconnection with `Last-Event-ID` header to recover missed events after disconnection.

**Rationale**: The SSE endpoint may not be available on older backend versions or if notifications are disabled. Graceful degradation ensures the desktop app works fully without notifications as a soft dependency.

## Risks / Trade-offs

- **System webview inconsistencies**: WebKit (macOS) vs WebView2 (Windows) vs webkit2gtk (Linux) may render differently. → Mitigated by Tailwind CSS normalization and testing on all platforms.
- **Rust toolchain requirement**: Developers need Rust installed for builds. → Document in setup guide; CI handles release builds.
- **Global shortcut conflicts**: `Cmd+Shift+Space` may still conflict in some locales (input method switching). → Make shortcut configurable in settings; handle registration failure gracefully.
- **Linux webkit2gtk availability**: Not all Linux distros ship webkit2gtk. → Document as a requirement; AppImage bundles dependencies.
- **System tray availability**: Some Linux desktop environments (e.g., GNOME) have limited tray support. → Graceful degradation; tray is optional, all features accessible from the main window.
- **File drop security**: Dropped files bypass the browser sandbox. → Client-side size validation + server-side magic bytes validation (defense in depth).
- **Platform detection merge conflict**: `add-capacitor-mobile` creates the same `platform.ts` file. → Coordinator merge queue handles ordering; lock keys declare the overlap.

## Open Questions

- Should the system tray show unread digest count as a badge? (Leaning: yes, similar to notification badges on mobile.)
