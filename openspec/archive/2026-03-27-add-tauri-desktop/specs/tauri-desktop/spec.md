# tauri-desktop Specification

## Purpose
Native desktop shell via Tauri v2, providing system tray, global keyboard shortcuts, native file drag-and-drop, and desktop notifications for macOS, Windows, and Linux.

## ADDED Requirements

### Requirement: Tauri Configuration
The system SHALL include Tauri v2 configuration to wrap the existing web build in native desktop shells, with capability-based permissions for all plugin APIs.

#### Scenario: Tauri initialization
- **WHEN** `npx tauri init` is run in the project root
- **THEN** a `src-tauri/` directory SHALL be created with `tauri.conf.json`, `Cargo.toml`, and Rust source files

#### Scenario: Capability permissions
- **WHEN** Tauri v2 is configured
- **THEN** `src-tauri/capabilities/default.json` SHALL grant permissions for: tray icon, global shortcut registration/unregistration, notification, file system read, shell open, window management (set-always-on-top, show, set-focus)

#### Scenario: Development mode
- **WHEN** `npx tauri dev` is run
- **THEN** the Vite dev server SHALL start
- **AND** a native window SHALL open loading the dev server URL with hot reload

#### Scenario: Production build
- **WHEN** `npx tauri build` is run
- **THEN** the system SHALL build the Vite production assets
- **AND** compile the Rust backend
- **AND** produce a native installer for the target platform

#### Scenario: Cross-platform targets
- **WHEN** a production build is created
- **THEN** macOS SHALL produce a `.dmg` installer
- **AND** Windows SHALL produce an `.msi` or `.exe` installer
- **AND** Linux SHALL produce a `.deb`, `.AppImage`, or `.rpm` package

### Requirement: System Tray
The system SHALL provide a system tray icon with a context menu for quick actions, using Tauri v2's built-in `TrayIconBuilder` API (not a plugin).

#### Scenario: Tray icon display
- **WHEN** the application starts
- **THEN** a system tray icon SHALL be displayed
- **AND** it SHALL remain visible when the main window is closed

#### Scenario: Tray context menu
- **WHEN** the user right-clicks (or clicks on macOS) the tray icon
- **THEN** a context menu SHALL appear with options: Open App, Ingest URL, Start Voice Input, Quit

#### Scenario: Open app from tray
- **WHEN** the user selects "Open App" from the tray menu
- **THEN** the main window SHALL be shown and focused

#### Scenario: Ingest URL from tray
- **WHEN** the user selects "Ingest URL" from the tray menu
- **THEN** a small input dialog SHALL appear for entering a URL
- **AND** submitting the URL SHALL call `POST /api/v1/content/save-url`

#### Scenario: Start voice input from tray
- **WHEN** the user selects "Start Voice Input" from the tray menu
- **THEN** the voice input overlay panel SHALL appear in the main window
- **AND** voice recognition SHALL start automatically

#### Scenario: Quit from tray
- **WHEN** the user selects "Quit" from the tray menu
- **THEN** the application SHALL exit completely (close window and remove tray icon)

### Requirement: Global Keyboard Shortcut
The system SHALL register a global keyboard shortcut for toggling voice input.

#### Scenario: Default shortcut
- **WHEN** the application starts
- **THEN** a global shortcut SHALL be registered: `Cmd+Shift+Space` (macOS) / `Ctrl+Shift+Space` (Windows/Linux)

#### Scenario: Activate voice input via shortcut
- **WHEN** the global shortcut is pressed while the app is running (foreground or background)
- **THEN** the main window SHALL be shown (if hidden) and brought to front with `setAlwaysOnTop(true)`
- **AND** the voice input overlay panel SHALL appear
- **AND** voice recognition SHALL start

#### Scenario: Deactivate voice input via shortcut
- **WHEN** the global shortcut is pressed while voice input is active
- **THEN** voice recognition SHALL stop
- **AND** the overlay panel SHALL close
- **AND** `setAlwaysOnTop` SHALL be set back to `false`

#### Scenario: Shortcut conflict
- **WHEN** the global shortcut cannot be registered (conflict with another app)
- **THEN** a warning SHALL be logged
- **AND** a one-time notification SHALL suggest manual shortcut configuration
- **AND** voice input SHALL remain accessible via the UI button

#### Scenario: Shortcut customization
- **WHEN** the user changes the global shortcut in settings
- **THEN** the previous shortcut SHALL be unregistered
- **AND** the new shortcut SHALL be registered
- **AND** the preference SHALL persist across app restarts

### Requirement: Native File Drag-and-Drop
The system SHALL accept files dropped onto the application window for document ingestion, with client-side validation before upload.

#### Scenario: Drop supported file
- **WHEN** a user drops a supported file (PDF, DOCX, PPTX, XLSX, TXT, MD, HTML) onto the app window
- **AND** the file size is within the configured maximum (`MAX_UPLOAD_SIZE_MB`, default 500MB)
- **THEN** the file SHALL be uploaded via `POST /api/v1/documents/upload`
- **AND** a success toast SHALL confirm the upload

#### Scenario: Drop unsupported file
- **WHEN** a user drops an unsupported file type onto the app window
- **THEN** an error toast SHALL display indicating the file type is not supported
- **AND** the file SHALL NOT be uploaded

#### Scenario: Drop oversized file
- **WHEN** a user drops a file that exceeds the configured maximum upload size
- **THEN** an error toast SHALL display immediately indicating the file is too large
- **AND** the file SHALL NOT be uploaded (no upload attempt SHALL be made)

#### Scenario: Drop multiple files
- **WHEN** a user drops multiple files onto the app window
- **THEN** each supported, correctly-sized file SHALL be uploaded individually
- **AND** a summary toast SHALL show the count of successful, rejected (unsupported/oversized), and failed uploads

#### Scenario: Drop zone visual feedback
- **WHEN** a file is dragged over the app window
- **THEN** a visual drop zone overlay SHALL appear indicating the area accepts files
- **WHEN** the drag leaves the window or the file is dropped
- **THEN** the drop zone overlay SHALL disappear

### Requirement: Desktop Notification Delivery
The system SHALL deliver notification events from `add-notification-events` as native desktop notifications via Tauri's notification plugin, with graceful degradation if the backend endpoint is unavailable.

#### Scenario: Subscribe to event stream
- **WHEN** the desktop app starts
- **THEN** it SHALL connect to the backend SSE endpoint (`GET /api/v1/notifications/stream`) for real-time events

#### Scenario: SSE endpoint unavailable
- **WHEN** the SSE endpoint returns a non-200 status or is unreachable (connection refused, timeout)
- **THEN** desktop notifications SHALL be disabled gracefully
- **AND** a warning SHALL be logged (NOT shown to the user)
- **AND** the app SHALL continue functioning normally without notifications

#### Scenario: Display native notification
- **WHEN** a notification event arrives via SSE
- **THEN** a native desktop notification SHALL be displayed with the event title and summary

#### Scenario: Notification click
- **WHEN** the user clicks a notification
- **THEN** the main window SHALL be shown and focused
- **AND** the app SHALL navigate to the content specified in the event's `payload.url`

#### Scenario: Notification permission
- **WHEN** the app starts for the first time
- **THEN** the system SHALL request notification permission from the OS
- **AND** respect the user's choice without re-prompting

#### Scenario: SSE reconnection
- **WHEN** the SSE connection drops
- **THEN** the app SHALL reconnect with `Last-Event-ID` to receive missed events

### Requirement: Desktop Platform Detection
The system SHALL detect Tauri desktop context for conditional feature activation.

#### Scenario: Tauri context detection
- **WHEN** the app is running inside a Tauri shell
- **THEN** `isTauri()` SHALL return `true`
- **AND** `getPlatform()` SHALL return `"desktop"`

#### Scenario: Non-Tauri context
- **WHEN** the app is running in a browser or Capacitor shell
- **THEN** `isTauri()` SHALL return `false`
