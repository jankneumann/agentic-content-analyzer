## ADDED Requirements

### Requirement: Extension Session Sync Permissions

The Chrome extension manifest SHALL declare the `cookies` permission and
`host_permissions` for `https://substack.com/*` and `https://x.com/*` and no other
cookie site. It SHALL declare `optional_host_permissions` of `https://*.ts.net/*`
and SHALL request the configured API origin (`<origin>/*`) at runtime, from a user
gesture, when that origin is an `https` host under `ts.net`. The existing URL-save
permissions (`activeTab`, `scripting`, `storage`) SHALL remain. The manifest SHALL
stay Manifest V3 with no remote code.

#### Scenario: Tailnet API origin granted on save
- **WHEN** the operator saves the API URL `https://gx-10.example.ts.net` in the options page
- **THEN** the extension requests the origin `https://gx-10.example.ts.net/*`
- **AND** the settings are saved whether or not the operator grants it

#### Scenario: Non-tailnet API origin
- **WHEN** the API URL is `http://localhost:8000`
- **THEN** the extension requests no runtime host permission and the request relies on CORS as before

### Requirement: Extension Session Sync Action

The extension popup SHALL offer one sync button per site (Substack, X), each with
its own status line, when an API URL is configured. On click it SHALL read the
site's cookies with `chrome.cookies`: `substack.sid` from `https://substack.com`,
and `auth_token` and `ct0` from `https://x.com`, sending the X pair only when both
are present. It SHALL `PUT` exactly `{"substack_sid"}` to
`<apiUrl>/api/v1/browser-sessions/substack` or `{"auth_token", "ct0"}` to
`<apiUrl>/api/v1/browser-sessions/x` with the stored key in the `X-Admin-Key`
header. When a cookie is missing it SHALL show that the browser is not logged in
to the site and SHALL NOT call the API. When no API key is configured, or the API
URL is neither `https` nor `http` on a loopback host, it SHALL say so and SHALL NOT
read cookies or call the API.

#### Scenario: Substack sync succeeds
- **WHEN** the browser holds `substack.sid` and the API answers 200 with `saved_at`
- **THEN** the popup sends one `PUT` with body `{"substack_sid": <value>}` and `X-Admin-Key`
- **AND** the Substack status line shows success with the `saved_at` time

#### Scenario: X pair incomplete
- **WHEN** `https://x.com` has `auth_token` but no `ct0`
- **THEN** the X status line says the browser is not logged in to X and no request is sent

#### Scenario: Plain-http API URL
- **WHEN** the API URL is `http://gx-10.example.ts.net`
- **THEN** the status line asks for an https API URL and no cookie is read and no request is sent

#### Scenario: No API key configured
- **WHEN** the options hold an API URL but no API key
- **THEN** the status line points to the options page and no cookie is read and no request is sent

### Requirement: Extension Session Sync Status Messages and Secrecy

The popup SHALL map responses to fixed messages: 200 success with `saved_at`; 422
`session_invalid` to "log in again in this browser"; other 422 to a rejected-cookie
message; 401 and 403 to missing or rejected API key; 429 to a rate-limit message
with the `Retry-After` seconds when present; 502 to retry later; 503
`openbao_not_configured` to "the server has no OpenBao configured"; a network
failure to a message naming the API URL and the tailnet. The extension SHALL NOT
display, log, or write to `chrome.storage` any cookie value, and SHALL NOT display
response body text other than `saved_at` and the problem `code`.

#### Scenario: Expired session
- **WHEN** the API answers 422 with `code: session_invalid`
- **THEN** the status line tells the operator to log in to the site again in this browser and retry

#### Scenario: OpenBao missing on the server
- **WHEN** the API answers 503 with `code: openbao_not_configured`
- **THEN** the status line says the server has no OpenBao configured

#### Scenario: No value leaks into the UI
- **WHEN** any sync attempt completes with any status
- **THEN** the status message contains none of the cookie values read for that attempt
