# Design: Add Sync session button to the Chrome extension

## Decision 1: Popup, not the options page

The sync is a response to an expiry alert: open the toolbar popup, click the
site's button, read the result. The options page is a settings form embedded in
`chrome://extensions`; putting an action there adds three clicks and mixes
configuration with operations. The popup already loads the config and shows a
"No API URL configured" warning, so the sync section reuses that gate.

The one-time permission grant for the API origin happens on the options page
(**Save Settings** is a user gesture, and a permission prompt there does not
close anything). The popup also calls `chrome.permissions.request` as the first
statement of each sync click: once granted it resolves `true` without a prompt,
and on a first use it still works when the prompt keeps the popup open. If the
prompt closes the popup, the grant survives and the next click proceeds.

## Decision 2: Runtime host permission for `*.ts.net`

`optional_host_permissions: ["https://*.ts.net/*"]` plus
`chrome.permissions.request({origins: ["<api origin>/*"]})` grants exactly the
configured tailnet host, works for any tailnet name without editing the manifest,
and exempts the extension's requests to it from CORS, so the interim
`chrome-extension://<id>` `ALLOWED_ORIGINS` entry is no longer needed. Origins
outside `https://*.ts.net` (localhost dev, Railway) get no runtime request and
keep working through CORS exactly as before; `chrome.permissions.request` would
throw for an origin the manifest does not list.

## Decision 3: No twitter.com fallback

The acceptance outcome requires host permissions for substack.com and x.com
only. X moved its session cookies to `.x.com` and redirects twitter.com there,
so a twitter.com-only cookie pair is a stale legacy session the server would
reject anyway. Reading it would widen permissions for no working case. The X
pair is read from `https://x.com` only and is used only when both cookies are
present (never one from each place).

## Decision 4: Pure module + `node --test`

The repo has no test harness for `extension/` (vitest is scoped to `web/src`).
The logic is factored into `extension/session_sync.js`, which takes
`chrome.cookies`, `chrome.permissions` and `fetch` as parameters, so
`node --test` exercises it with fakes and no dependencies. `extension/package.json`
sets `"type": "module"` so Node and Chrome load the same file; Chrome ignores it.

## Decision 5: Messages come from the extension, not the server

Status lines are fixed strings keyed on HTTP status and the problem `code`, plus
`saved_at` and `Retry-After`. The server's problem bodies are value-free, but
mapping locally keeps the popup's text stable and guarantees that nothing from a
request body can be echoed into the UI.
