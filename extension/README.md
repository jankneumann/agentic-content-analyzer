# Newsletter Aggregator - Chrome Extension

Queue the current page URL into durable ingestion with one click, and push
this browser's Substack and X logins to the server when a session expires.

Full-page HTML capture (`POST /api/v1/content/save-page`) is **retired**.
The extension always posts `POST /api/v1/ingestions` with `kind: url`.
Reload the unpacked extension from this directory after pulling `main`.

## Features

- **One-click save**: Click the extension icon to queue the current page URL
- **Text selection**: Selected text is sent as `notes`
- **Tags**: Add comma-separated tags
- **Dark mode**: Adapts to your system color scheme
- **Status feedback**: Shows the returned `operation_id`
- **Session sync**: One button each for Substack and X sends the browser's
  session cookies to the API, which validates them and stores them in OpenBao

## Installation (Load Unpacked)

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select the `extension/` directory from this repository
5. The extension icon will appear in your toolbar

## Configuration

1. Right-click the extension icon and select **Options**
2. Enter your **API URL** (the `aca-api` origin, not the frontend origin)
3. Enter **API Key** (`ADMIN_API_KEY`, sent as `X-Admin-Key`)
4. Click **Save Settings**

### Self-hosted API on the tailnet (gx-10)

When the API runs on gx-10 it is reachable only over Tailscale, at its MagicDNS
name with a Let's Encrypt certificate issued by `tailscale serve`:

- **API URL**: `https://gx-10.<tailnet>.ts.net` (your tailnet name; no port, no
  trailing slash). The machine running Chrome must be on the tailnet with
  Tailscale DNS enabled. Use the full name: the certificate is not valid for
  `gx-10`, the `100.x.y.z` address, or `http://`.
- **Host permission**: the manifest declares
  `"optional_host_permissions": ["https://*.ts.net/*"]`. When you click
  **Save Settings** with an `https://….ts.net` API URL, Chrome asks to allow the
  extension to access that host; allow it. The grant covers exactly your API
  host, works for any tailnet name, and exempts the extension's requests from
  CORS, so the API's `ALLOWED_ORIGINS` needs **no** `chrome-extension://` entry.
  If you declined, save the settings again (or click a sync button) to be asked
  again; you can review the grant under the extension's **Details → Site access**.
- **Other API origins** (`http://localhost:8000`, a Railway URL) get no host
  permission and stay CORS-checked as before: add
  `chrome-extension://<extension-id>` (the ID shown on `chrome://extensions`) to
  that API's `ALLOWED_ORIGINS`.

Topology, ACLs, and verification: [docs/TAILNET.md](../docs/TAILNET.md).

## Usage

1. Navigate to any webpage you want to save
2. Optionally select text on the page (captured as `notes`)
3. Click the extension icon in your toolbar
4. Review the pre-filled URL, title, excerpt, and add tags if desired
5. Click **Save**

The request body is:

```json
{
  "kind": "url",
  "url": "https://example.com/article",
  "title": "Page title",
  "tags": ["ai"],
  "notes": "selected text"
}
```

Success is HTTP 202 with an `OperationHandle` (`schema_version: 2`,
`operation_id`). Poll `GET /api/v1/operations/{operation_id}`.

Paywall and JS-rendered pages that the server cannot fetch anonymously will
not round-trip through the extension. Restoring client-supplied HTML requires
a URL-major (`/api/v2`) or a new ingest `kind`. See
[API consumers](../docs/API_CONSUMERS.md).

## Sync sessions

When a Substack or X session-expiry alert fires and you are at a browser that
is logged in to that site, open the popup and click **Sync Substack session** or
**Sync X session**. This replaces copying cookies out of DevTools; on the
workstation, `aca auth session substack|x` remains the alternative.

| Site | Cookies read | Endpoint | Body |
|------|--------------|----------|------|
| Substack | `substack.sid` from `https://substack.com` | `PUT /api/v1/browser-sessions/substack` | `{"substack_sid": "..."}` |
| X | `auth_token` and `ct0` from `https://x.com` (both or nothing) | `PUT /api/v1/browser-sessions/x` | `{"auth_token": "...", "ct0": "..."}` |

The request carries the configured API key as `X-Admin-Key` (required: the
sync endpoint accepts nothing else). The API validates the session with the
site, then writes it to OpenBao; see
[docs/TAILNET.md](../docs/TAILNET.md#browser-session-sync-endpoint).

Each site has its own status line:

| Status line | Meaning / what to do |
|-------------|----------------------|
| Synced … (saved *time*) | Stored in OpenBao; *time* is the server's `saved_at` |
| Not logged in to *site* in this browser | The cookies are missing; log in to the site in this Chrome profile. Nothing was sent |
| No API key configured | Set the API key in Options. Nothing was read or sent |
| Session sync needs an https:// API URL | Cookies are only sent over HTTPS (plain `http` only to `localhost`). Nothing was read or sent |
| *site* refused this session: log in again (422 `session_invalid`) | The site rejected the cookies; log out and back in, then sync |
| API key rejected (403) / API refused the request (401) | Fix the key in Options; the server needs `ADMIN_API_KEY` |
| Too many sync attempts (429) | 10 syncs per 5 minutes; wait the time shown |
| … could not be reached / OpenBao refused the write (502) | Temporary; retry later |
| The server has no OpenBao configured (503) | The API needs `BAO_ADDR` and AppRole credentials; nothing was saved |
| Could not reach the API | Wrong API URL, machine not on the tailnet, or host access not granted |

Cookie values are never shown, logged, or written to extension storage; they
exist only for the duration of the request.

## Permissions

| Permission | Purpose |
|------------|---------|
| `activeTab` | Access the current tab's URL and title when you click the icon |
| `scripting` | Capture selected text from the page |
| `storage` | Persist API URL and key across sessions |
| `cookies` | Read the session cookies for **Sync sessions** |
| Host `https://substack.com/*`, `https://x.com/*` | The only sites whose cookies the extension can read |
| Optional host `https://*.ts.net/*` | Requested at runtime for your tailnet API host only (exempts it from CORS) |

After pulling version 1.1.0, click the reload icon on `chrome://extensions`;
an unpacked extension receives the new `cookies` and host permissions on reload.
The optional tailnet host is still asked for separately (see Configuration).

## Tests

The sync logic lives in `session_sync.js`, a module without DOM or `chrome.*`
globals, so it runs under Node's built-in test runner (Node 20+, no install):

```bash
node --test 'extension/tests/*.test.js'   # from the repo root
cd extension && npm test                  # same, from this directory
```

`package.json` only sets `"type": "module"` for Node; Chrome ignores it. CI runs
these tests in the `frontend-release` job.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No API URL configured" | Open extension options and set your API URL |
| "Failed to fetch" | Check that your API URL is the API origin and the server is running |
| "Save failed" with 422 | Body must include `"kind": "url"`; do not send `source`, `excerpt`, or HTML |
| Can't capture selected text | Some pages (chrome://, file://) restrict extension access |
| Extension not visible | Click the puzzle piece icon in Chrome toolbar and pin the extension |
| Sync says "Could not reach the API" on a tailnet URL | Save the settings again and allow access to the host, or check **Details → Site access** |
| "Could not read … cookies" | Reload the unpacked extension and accept the `cookies` permission |
| Empty content behind a paywall | Client-supplied HTML is retired; the server fetches the URL |
