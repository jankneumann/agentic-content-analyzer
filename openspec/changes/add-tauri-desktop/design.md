## Context

The app runs as a PWA in the browser and (with the `add-capacitor-mobile` change) as a native mobile app. Desktop users currently use the PWA in a browser tab, which lacks system tray, global hotkeys, and native drag-and-drop. Tauri v2 provides a Rust-based native shell that wraps the existing Vite build with a ~5MB binary, much lighter than Electron (~100MB).

The existing platform detection utility (from `add-capacitor-mobile`) needs extending to detect Tauri context. The voice input system (from `add-voice-input` and `add-on-device-stt`) needs a global hotkey trigger. The content capture system needs native file drag-and-drop.

## Goals / Non-Goals

**Goals:**
- Wrap the existing Vite build in Tauri v2 for macOS, Windows, and Linux
- Provide system tray with digest notification badges and quick actions
- Implement global keyboard shortcut for voice input toggle
- Enable native file drag-and-drop for document ingestion
- Desktop notifications for digest completion events
- Provide build scripts and CI configuration for cross-platform builds

**Non-Goals:**
- Custom native UI (keep everything as web views)
- Auto-update mechanism (manual updates initially; Tauri updater in future)
- Tray-only mode (app always has a window, tray is supplementary)
- System-level audio capture for transcription
- Native menu bar customization beyond system tray

## Decisions

### 1. Tauri v2 over Electron

**Choice**: Tauri v2 with Rust backend.

**Alternatives considered**:
- **Electron**: Mature ecosystem but ~100MB binary (bundles Chromium), high memory usage. Overkill for a web-view wrapper.
- **Neutralinojs**: Lighter than Electron but less mature plugin ecosystem and community.
- **Wails (Go)**: Similar to Tauri but smaller ecosystem and less native API coverage.

**Rationale**: Tauri v2 uses the system webview (WebKit on macOS, WebView2 on Windows, webkit2gtk on Linux), resulting in ~5MB binaries. Rust backend provides system-level access (tray, shortcuts, file system) with strong safety guarantees. Tauri v2's plugin system covers all needed capabilities.

### 2. System tray with quick actions

**Choice**: Persistent system tray icon with a context menu offering: Open App, Ingest URL (text input), Start Voice Input, Recent Digests, Quit.

**Rationale**: System tray is the standard desktop pattern for background-accessible apps. Quick actions let users ingest URLs and start voice input without switching to the app window.

### 3. Global shortcut via Tauri plugin

**Choice**: Use `tauri-plugin-global-shortcut` to register `Cmd+Shift+V` (macOS) / `Ctrl+Shift+V` (Windows/Linux) as a global voice input hotkey.

**Alternatives considered**:
- **OS-specific hotkey APIs**: More control but requires platform-specific Rust code.
- **Keyboard hook library**: Complex, permission-heavy, and fragile across OS updates.

**Rationale**: Tauri's global shortcut plugin handles cross-platform registration cleanly. The hotkey activates voice input and shows a floating transcript overlay even when the main window is not focused.

### 4. Native drag-and-drop via Tauri file drop event

**Choice**: Listen to Tauri's `tauri://file-drop` event to receive dropped files, validate against supported formats, and upload via the existing document upload API.

**Rationale**: Tauri provides native file drop events out of the box. Files are validated against the same format list used by the upload API (PDF, DOCX, PPTX, etc.). This extends the existing content capture system with a natural desktop interaction.

### 5. Extend platform detection (not separate utility)

**Choice**: Extend the `web/src/lib/platform.ts` utility (from `add-capacitor-mobile`) to detect Tauri via `window.__TAURI__` or `@tauri-apps/api`.

```typescript
export const isTauri = () => Boolean(window.__TAURI_INTERNALS__);
export const getPlatform = () => {
  if (isTauri()) return 'desktop';
  if (Capacitor.isNativePlatform()) return Capacitor.getPlatform();
  return 'web';
};
```

**Rationale**: Single utility for all platform detection. Components can branch on `'desktop'`, `'ios'`, `'android'`, or `'web'` without importing multiple libraries.

## Risks / Trade-offs

- **System webview inconsistencies**: WebKit (macOS) vs WebView2 (Windows) vs webkit2gtk (Linux) may render differently. → Mitigated by Tailwind CSS normalization and testing on all platforms.
- **Rust toolchain requirement**: Developers need Rust installed for builds. → Document in setup guide; CI handles release builds.
- **Global shortcut conflicts**: `Cmd+Shift+V` may conflict with other apps. → Make shortcut configurable in settings.
- **Linux webkit2gtk availability**: Not all Linux distros ship webkit2gtk. → Document as a requirement; AppImage bundles dependencies.
- **System tray availability**: Some Linux desktop environments (e.g., GNOME) have limited tray support. → Graceful degradation; tray is optional, all features accessible from the main window.
- **File drop security**: Dropped files bypass the browser sandbox. → Validate file signatures (same `FILE_SIGNATURES` check as upload API).

## Open Questions

- Should the global voice input hotkey show a floating overlay window or activate the main window? (Leaning: floating overlay — less disruptive when working in another app.)
- Should the system tray show unread digest count as a badge? (Leaning: yes, similar to notification badges on mobile.)
