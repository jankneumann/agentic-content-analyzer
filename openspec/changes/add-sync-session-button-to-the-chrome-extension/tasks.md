# Tasks: Add Sync session button to the Chrome extension

> Change ID: `add-sync-session-button-to-the-chrome-extension`

## 1. Plan
- [x] 1.1 Refine proposal, design and the `browser-session-credentials` spec delta against `extension/`, the `ri-14` routes and `docs/TAILNET.md`

## 2. Tests first (`extension/tests/session_sync.test.js`, `node --test`)
- [x] 2.1 Cookie selection: Substack from `https://substack.com`; X pair from `https://x.com` only when both are present; empty values count as missing
- [x] 2.2 API permission origin: `https://*.ts.net` hosts only; invalid URLs and other hosts yield none
- [x] 2.3 Status mapping: 200 (`saved_at`), 422 `session_invalid` / other, 401, 403, 429 (`Retry-After`), 502, 503 `openbao_not_configured`, unknown, network error
- [x] 2.4 `syncSession`: exact URL, method, `X-Admin-Key`, body fields; no cookie read or fetch without a key or over plain http to a non-loopback host; no fetch when cookies are missing; no cookie value in any message
- [x] 2.5 Manifest: MV3, exact host permissions, URL-save permissions kept, no CSP override or remote script

## 3. Implementation
- [x] 3.1 `extension/session_sync.js`: pure ES module (sites, cookie reading, permission origins, request, status mapping)
- [x] 3.2 `extension/popup.html` / `popup.js`: "Sync sessions" section, one button and status line per site; popup loaded as a module
- [x] 3.3 `extension/options.js`: request the tailnet API origin when settings are saved
- [x] 3.4 `extension/manifest.json`: `cookies`, `host_permissions` (substack.com, x.com), `optional_host_permissions` (`https://*.ts.net/*`); version 1.1.0
- [x] 3.5 `extension/package.json` (`"type": "module"`, `npm test`) and a CI step running `node --test` in `frontend-release`

## 4. Documentation
- [x] 4.1 `extension/README.md`: sync action, permissions table, tests; host permission replaces the `chrome-extension://` `ALLOWED_ORIGINS` entry
- [x] 4.2 `docs/TAILNET.md`: extension CORS bullet and example `ALLOWED_ORIGINS`

## 5. Validation
- [x] 5.1 `node --test extension/tests/`, manifest JSON/MV3 check (no remote code, no `eval`), `openspec validate --strict`
- [ ] 5.2 Manual check in Chrome against gx-10: load unpacked, grant the tailnet origin, sync both sites (needs the host and a browser)
