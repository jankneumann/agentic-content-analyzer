# Tauri Desktop Deployment

Guide for building, distributing, and connecting the ACA Tauri desktop app.

## Quick Start (Local Development)

```bash
make tauri-setup   # Install Rust toolchain + frontend deps
make tauri-dev     # Start backend + open native desktop window with HMR
```

First build takes 2-5 minutes (Cargo compiles ~200 crates). Subsequent builds are incremental (~5-10s).

## Architecture

The desktop app is a Tauri v2 shell wrapping the same React SPA used in the browser and Capacitor mobile app:

```
┌─────────────────────────────┐
│     Tauri Native Shell      │  ← Rust: tray, shortcuts, notifications
│  ┌───────────────────────┐  │
│  │    System WebView     │  │  ← WebKit (macOS), WebView2 (Windows),
│  │  ┌─────────────────┐  │  │     webkit2gtk (Linux)
│  │  │   React SPA     │  │  │
│  │  │  (same as web)  │  │  │  ← Vite build output
│  │  └─────────────────┘  │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
         │ API calls
         ▼
┌─────────────────────────────┐
│   Backend API (FastAPI)     │  ← Same backend (local or remote)
└─────────────────────────────┘
```

**Key files:**
- `web/src-tauri/tauri.conf.json` — App config (window, bundle, build commands)
- `web/src-tauri/Cargo.toml` — Rust dependencies (plugins, features)
- `web/src-tauri/capabilities/default.json` — Permission grants for plugin APIs
- `web/src-tauri/src/lib.rs` — App entry point (plugin registration, setup)
- `web/src-tauri/src/tray.rs` — System tray menu and event handlers
- `web/src-tauri/src/shortcuts.rs` — Global keyboard shortcut registration

## Connecting to a Remote Backend

By default, `make tauri-dev` connects to the local backend (`http://localhost:8000`) via Vite's dev proxy. To connect to a remote backend (e.g., Railway):

### Development (remote backend)

```bash
VITE_API_URL=https://your-app.railway.app make tauri-dev
```

### Production build (remote backend)

```bash
VITE_API_URL=https://your-app.railway.app make tauri-build
```

The `VITE_API_URL` is baked into the frontend at build time.

### CORS Configuration (Critical)

The remote backend **must** include the Tauri origin in its CORS allowlist, or all API requests from the desktop app will fail silently.

```bash
# On your production/staging backend (Railway, etc.)
ALLOWED_ORIGINS=https://your-frontend.railway.app,tauri://localhost
```

**Why `tauri://localhost`?** Tauri v2 uses a custom URL scheme (`tauri://localhost`) as the webview origin for bundled assets. This is different from `http://localhost` used in dev mode. The backend CORS middleware checks the `Origin` header, and without this entry, all cross-origin requests are blocked.

**Production gotcha:** When `ENVIRONMENT=production` and `ALLOWED_ORIGINS` is still the development default (localhost-only values), `get_allowed_origins_list()` returns an **empty list** — blocking ALL cross-origin requests. You must explicitly set `ALLOWED_ORIGINS` in production.

## Authentication

### Local development
No login required — `ENVIRONMENT=development` bypasses auth enforcement.

### Production builds
The Tauri webview manages cookies like a regular browser. When the user logs in via the web UI (loaded inside the Tauri window), the session cookie is stored in the webview's cookie jar and persists across app restarts. No special auth handling is needed.

**Same-origin requirement:** The API URL configured at build time is the origin for cookie scope. If you change `VITE_API_URL` between builds, previous session cookies won't transfer.

## Building for Distribution

### Current platform

```bash
make tauri-build
```

Output is in `web/src-tauri/target/release/bundle/`:

| Platform | Output Location | Format |
|----------|----------------|--------|
| macOS | `bundle/dmg/` | `.dmg` installer + `.app` bundle |
| Windows | `bundle/msi/` | `.msi` installer |
| Linux | `bundle/deb/`, `bundle/appimage/` | `.deb`, `.AppImage` |

### App icons

Generate from a 1024x1024 source PNG:

```bash
make tauri-icons ICON=path/to/icon-1024.png
```

This populates `web/src-tauri/icons/` with all required sizes and formats (`.icns`, `.ico`, PNGs for all platforms).

### Cross-platform builds (CI)

The GitHub Actions workflow at `.github/workflows/tauri-build.yml` builds for all platforms on push to `main`:

| Runner | Target | Notes |
|--------|--------|-------|
| `macos-latest` | `aarch64-apple-darwin` | Apple Silicon |
| `macos-13` | `x86_64-apple-darwin` | Intel Mac |
| `ubuntu-22.04` | `x86_64-unknown-linux-gnu` | Requires webkit2gtk |
| `windows-latest` | `x86_64-pc-windows-msvc` | WebView2 included |

Build artifacts are uploaded as GitHub Actions artifacts (7-day retention).

### Code signing (not yet configured)

Unsigned builds trigger OS warnings:
- **macOS**: "App is damaged" or Gatekeeper block. Users can bypass with `xattr -cr /path/to/ACA\ Desktop.app`
- **Windows**: SmartScreen warning on first run

For production distribution, configure:
- **macOS**: Apple Developer ID certificate via `tauri.conf.json` > `bundle` > `macOS` > `signingIdentity`
- **Windows**: Code signing certificate via `tauri.conf.json` > `bundle` > `windows` > `certificateThumbprint`

## Desktop-Specific Features

### System Tray

A persistent tray icon provides quick actions without opening the main window:
- **Open App** — Show and focus the main window
- **Ingest URL** — Opens the app to capture a URL
- **Start Voice Input** — Activates voice overlay
- **Quit** — Fully exits the app (removes tray icon)

The tray icon remains visible when the window is closed. Closing the window hides it; Quit fully exits.

### Global Keyboard Shortcut

| Platform | Default Shortcut |
|----------|-----------------|
| macOS | `Cmd+Shift+Space` |
| Windows/Linux | `Ctrl+Shift+Space` |

Pressing the shortcut from any app:
1. Shows the ACA window (if hidden)
2. Brings it to the front (`setAlwaysOnTop`)
3. Opens the voice input overlay panel
4. Starts listening

Press again to stop listening and dismiss the overlay.

**If the shortcut conflicts** with another app (e.g., input method switching), registration fails gracefully — a one-time warning appears, and voice input remains accessible via the UI button.

### File Drag-and-Drop

Drop files directly onto the app window to ingest documents:
- **Supported formats**: PDF, DOCX, PPTX, XLSX, TXT, MD, HTML, EPUB, WAV, MP3
- **Size limit**: 500MB (validated client-side before upload — oversized files are rejected immediately)
- **Multiple files**: Each file is uploaded individually with a summary toast

### Desktop Notifications

Subscribes to the backend SSE stream (`GET /api/v1/notifications/stream`) for real-time events (digest created, pipeline completed, job failed). Notifications appear as native OS notifications.

**Graceful degradation**: If the SSE endpoint is unavailable (backend not running, older version without notifications), notifications are disabled silently with a console warning — the app continues working normally.

## Platform Requirements

### macOS
- macOS 10.15 (Catalina) or later
- WebKit (built-in, no additional install)

### Windows
- Windows 10 or later
- WebView2 runtime (pre-installed on Windows 10/11; bundled in installer for older systems)

### Linux
- `webkit2gtk-4.1` development package required for building:
  ```bash
  # Debian/Ubuntu
  sudo apt-get install libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf libssl-dev

  # Fedora
  sudo dnf install webkit2gtk4.1-devel libappindicator-gtk3-devel librsvg2-devel

  # Arch
  sudo pacman -S webkit2gtk-4.1 libappindicator-gtk3 librsvg
  ```
- Some desktop environments (GNOME without extensions) have limited system tray support — tray is optional, all features work from the main window

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `cargo not found` | Run `make tauri-setup` or install Rust via `rustup.rs` |
| First build is slow (2-5 min) | Normal — Cargo compiles all dependencies. Subsequent builds are ~5-10s |
| macOS: "App is damaged" | Run `xattr -cr /path/to/ACA\ Desktop.app` (unsigned build) |
| macOS: code signing errors | Use `pnpm tauri build -- --no-bundle` for unsigned dev builds |
| Linux: `webkit2gtk` not found | Install `libwebkit2gtk-4.1-dev` (not `4.0`) |
| Windows: WebView2 missing | Download from Microsoft — usually pre-installed on Win 10/11 |
| Global shortcut doesn't work | Another app may have claimed it. Restart ACA or check for conflicts |
| No notifications | Backend SSE endpoint may not be running. Check `make dev-bg` |
| CORS errors in console | Backend `ALLOWED_ORIGINS` must include `tauri://localhost` |
| API returns 401/403 | Production mode requires login. Check `ENVIRONMENT` setting |
| `generate_context!()` icon error | Run `make tauri-icons ICON=path/to/1024x1024.png` |
| `.icns` file too large for git | Already excluded from `check-added-large-files` pre-commit hook |

## Make Targets Reference

```bash
make tauri-setup          # Install Rust + pnpm install
make tauri-dev            # Dev mode (backend + Tauri + HMR)
make tauri-build          # Production build for current platform
make tauri-icons ICON=... # Generate all icon sizes from source PNG
make test-tauri           # Run Tauri E2E tests (no Rust needed)
```
