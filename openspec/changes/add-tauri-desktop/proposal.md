## Why

The application is web-first but power users on desktop want native window management, system tray access, global keyboard shortcuts (e.g., voice input hotkey from any app), and native file drag-and-drop for document ingestion. Tauri wraps the existing web app in a lightweight Rust-based native shell (~5MB binary vs ~100MB Electron), providing native APIs with minimal overhead. Desktop-specific features like system tray digest notifications and global hotkeys for voice input are not possible in a browser tab.

## What Changes

- Add Tauri v2 configuration to wrap the existing Vite build in a native desktop app (macOS, Windows, Linux)
- Implement system tray with digest notification badges and quick actions (open, ingest URL, start voice input)
- Add global keyboard shortcut for voice input (e.g., `Cmd+Shift+V` / `Ctrl+Shift+V` to toggle microphone from any app)
- Implement native file drag-and-drop for document ingestion (PDF, DOCX, etc. dropped onto the app window)
- Add native notification support for digest completion events
- Extend platform detection utility (from `add-capacitor-mobile`) to detect Tauri desktop context
- Add deep linking via `aca://` URL scheme for desktop
- Provide build scripts for macOS, Windows, and Linux targets

## Capabilities

### New Capabilities
- `tauri-desktop`: Native desktop shell via Tauri v2, including system tray, global shortcuts, native drag-and-drop, and desktop notifications

### Modified Capabilities
- `voice-input`: Add global hotkey trigger for voice input from system tray / any focused app
- `content-capture`: Add native file drag-and-drop as a content capture method

## Impact

- **Frontend**: Platform detection extension, Tauri API bridge calls, conditional desktop UI (system tray menu)
- **Build**: Tauri CLI, Rust toolchain required for builds; `src-tauri/` directory with Rust backend code
- **Dependencies**: `@tauri-apps/api` (frontend), Tauri v2 CLI + Rust toolchain (build), `tauri-plugin-global-shortcut`, `tauri-plugin-notification`, `tauri-plugin-shell`
- **Binary size**: ~5-10MB (significantly smaller than Electron)
- **Infrastructure**: No backend changes — Tauri app talks to the same API
- **Existing PWA/Capacitor**: Unchanged — Tauri is additive for desktop, Capacitor for mobile
