# Add Sync session button to the Chrome extension

> Parent roadmap: `x-bookmarks-session-capture` (item `ri-15`)
> Change ID: `add-sync-session-button-to-the-chrome-extension`
> Depends on: `ri-14` (`add-admin-endpoint-for-browser-session-sync`)

## Why

When a Substack or X session expires, the only refresh paths today are
`aca auth session substack|x` on the workstation or copying cookies out of
DevTools into a `curl` call. `ri-14` added `PUT /api/v1/browser-sessions/{substack,x}`,
which validates the cookies and writes them to OpenBao. The operator's laptop
browser already holds a fresh session; the extension can read those cookies and
push them in one click, so an expiry alert is resolved without opening DevTools.

The extension also still depends on an interim `chrome-extension://<id>` entry in
`ALLOWED_ORIGINS`, because the manifest declares no host permission for the API.

## What Changes

- **Popup "Sync sessions" section** (`extension/popup.html`, `extension/popup.js`):
  one button per site (Substack, X), each with its own status line. Shown only
  when an API URL is configured.
- **Pure logic module** `extension/session_sync.js` (ES module, no DOM):
  cookie selection (`substack.sid` from `https://substack.com`; `auth_token` and
  `ct0` from `https://x.com`, both or nothing), the API permission origin, the
  `PUT` request, and the HTTP-status-to-message mapping. The popup imports it.
- **Cookie handling**: read with `chrome.cookies.get`; missing cookies show
  "Not logged in to <site> in this browser" without calling the API. Values are
  never logged, displayed, or written to `chrome.storage`; references are dropped
  after the request. Cookies are sent only to an `https` API URL (plain `http`
  only on loopback), with `credentials: 'omit'` and `redirect: 'manual'`.
- **Manifest** (`extension/manifest.json`): add the `cookies` permission,
  `host_permissions` for `https://substack.com/*` and `https://x.com/*` only, and
  `optional_host_permissions: ["https://*.ts.net/*"]`. The options page requests
  the configured tailnet API origin when settings are saved, and the popup
  requests it again (a no-op once granted) before each sync, both from a click.
- **Status mapping**: 200 shows `saved_at`; 422 `session_invalid` says log in
  again; 502 says retry later; 503 `openbao_not_configured` says the server has
  no OpenBao; 401/403 point at the API key; 429 shows the `Retry-After` wait; a
  network failure points at the URL and tailnet.
- **Tests**: `extension/tests/session_sync.test.js` (`node --test`, mocks
  `chrome.cookies` and `fetch`), `extension/package.json` (`"type": "module"`,
  `npm test`), and a CI step in the `frontend-release` job.
- **Docs**: `extension/README.md` (sync action, permissions, tests, host
  permission replaces the `chrome-extension://` CORS entry) and the extension
  CORS bullet of `docs/TAILNET.md`.

## Impact

- Capability: `browser-session-credentials` (ADDED: extension sync requirements).
  The URL-save behaviour of the `content-capture` Chrome Extension requirement is
  unchanged.
- Affected code: `extension/` only, plus one CI step. No server change.
- Permissions: users are prompted once for `cookies` + the two sites on update,
  and once for the tailnet API origin.
- Non-goals: automatic or background sync, a service worker, twitter.com
  cookies, API origins outside `*.ts.net` getting a runtime host permission
  (they keep working through CORS as before), storing or displaying cookie values.
