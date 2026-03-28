## Why

The application is web-first but power users on desktop want native window management, system tray access, global keyboard shortcuts (e.g., voice input hotkey from any app), and native file drag-and-drop for document ingestion. Tauri wraps the existing web app in a lightweight Rust-based native shell (~5MB binary vs ~100MB Electron), providing native APIs with minimal overhead. Desktop-specific features like system tray digest notifications and global hotkeys for voice input are not possible in a browser tab.

## What Changes

- Add Tauri v2 configuration to wrap the existing Vite build in a native desktop app (macOS, Windows, Linux)
- Configure Tauri v2 capability-based permissions for all plugin APIs
- Create platform detection utility (`web/src/lib/platform.ts`) with Tauri detection; Capacitor detection will be added by `add-capacitor-mobile` when it merges (parallel implementation — coordinator handles merge ordering)
- Implement system tray with digest notification badges and quick actions (open, ingest URL, start voice input) using Tauri v2 built-in tray API (`tauri::tray::TrayIconBuilder`)
- Add global keyboard shortcut for voice input (`Cmd+Shift+Space` on macOS / `Ctrl+Shift+Space` on Windows/Linux — avoids conflicting with "Paste without formatting")
- Implement native file drag-and-drop for document ingestion with client-side size validation before upload
- Deliver native desktop notifications by subscribing to the backend SSE event stream (from `add-notification-events`) with graceful degradation if unavailable
- Provide build scripts for macOS, Windows, and Linux targets
- Create GitHub Actions CI workflow for cross-platform Tauri builds

## Out of Scope (deferred)

- **Deep linking via `aca://` URL scheme** — requires platform-specific configuration (Info.plist, registry, .desktop files) and frontend route handling. Deferred to a separate proposal.
- **Auto-update mechanism** — Tauri updater deferred to future iteration.
- **Custom native UI** — keep everything as web views.
- **Rust-based STT engine** — use existing webview-hosted engines (Web Speech API + Whisper WASM).

## Capabilities

### New Capabilities
- `tauri-desktop`: Native desktop shell via Tauri v2, including system tray, global shortcuts, native drag-and-drop, and desktop notifications

### Modified Capabilities
- `voice-input`: Add global hotkey trigger for voice input from system tray / any focused app (uses existing STT engines — Web Speech API + Whisper WASM — in the webview)
- `content-capture`: Add native file drag-and-drop as a content capture method with client-side size validation

## Impact

- **Frontend**: Platform detection utility creation (shared with `add-capacitor-mobile` via coordinator merge), Tauri API bridge calls, conditional desktop UI (system tray menu)
- **Build**: Tauri CLI, Rust toolchain required for builds; `src-tauri/` directory with Rust backend code
- **Dependencies**: `@tauri-apps/api` (frontend), Tauri v2 CLI + Rust toolchain (build), `tauri-plugin-global-shortcut`, `tauri-plugin-notification`, `tauri-plugin-shell`
- **Binary size**: ~5-10MB (significantly smaller than Electron)
- **Infrastructure**: No backend changes — Tauri app talks to the same API
- **Existing PWA/Capacitor**: Unchanged — Tauri is additive for desktop, Capacitor for mobile. Both features implement in parallel with coordinator-managed merge ordering for shared files (`platform.ts`, `package.json`)

## Parallel Implementation Note

`add-capacitor-mobile` creates `web/src/lib/platform.ts` with `isNative()`, `getPlatform()`, and `usePlatform`. This feature also creates `platform.ts` with `isTauri()` and extends `getPlatform()`. Since both features run in parallel:
- Each feature creates its own version of `platform.ts`
- The coordinator's merge queue handles ordering — whichever merges first establishes the file, the second rebases and adds its detection
- Work packages declare `platform.ts` as a lock key so the coordinator detects the overlap

## Plan Revision

- **Revision**: 2 (post-review)
- **Findings addressed**: 12 findings from review-findings-plan.json (3 high, 5 medium, 4 low)
