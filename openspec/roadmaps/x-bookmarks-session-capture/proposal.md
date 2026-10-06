# X Bookmarks Ingestion and Tailnet-Native Browser-Session Credential Capture

Design record: session `claude/x-bookmarks-token-capture-1wo4j3` (2026-09-22).
Evidence verified against `src/ingestion/registry.py`, `src/config/bao_secrets.py`,
`src/cli/auth_commands.py`, `settings/deploy/railway_secrets.yaml`,
`src/services/backup/stores.py`, and the upstream
[x-bookmarks-exporter](https://github.com/displace-agency/x-bookmarks-exporter) sources.

## Motivation

Two ingestion sources depend on browser session cookies rather than API keys.
Substack paid posts need the `substack.sid` cookie, and the X bookmarks the
operator curates from every device need the `auth_token` and `ct0` cookie pair
that the browser sends to X's own GraphQL endpoint. Today the Substack cookie is
captured by hand from DevTools, stored in `.secrets.yaml`, and never reaches the
worker: `SUBSTACK_SESSION_COOKIE` is absent from the Railway secret allowlist, no
`saved_at` is recorded, and an expired cookie only produces a log warning and a
silently thinner corpus. X bookmarks are not ingested at all; the only X source is
Grok search.

The project is moving from Railway to the self-hosted gx-10 host, reachable from
the operator's workstation, laptops, and phones over Tailscale. That move changes
the credential design fundamentally. OpenBao becomes the worker's secret store and
already has a background AppRole refresher that re-fetches the KV path and swaps
the cache atomically, so a rotated cookie can reach a running worker without a
restart. The worker shares the operator's residential IP with the operator's own
browser, which is the most tolerant posture for an unofficial GraphQL surface.
And because gx-10 is on the tailnet, the API and OpenBao never need public
exposure, and bookmarking a post on a phone becomes the capture gesture: the
worker pulls it, and the phone never holds a credential.

Success looks like this: the operator logs in once per site from the workstation
through a deterministic CLI, the worker on gx-10 reads live credentials from
OpenBao and heals routine `ct0` rotation itself, every X bookmark and the articles
it links to land in the corpus nightly through the canonical durable workflow, and
the only time a human is involved again is a yearly `auth_token` expiry announced
by an alert that names the exact command to run.

## Capabilities

### Capability: Tailnet exposure baseline for gx-10 services

Document and configure how the API and OpenBao on gx-10 are reached over
Tailscale. OpenBao and the API bind to the Tailscale interface only, never to
`0.0.0.0` on the LAN. A `docs/TAILNET.md` records the bind addresses, a Tailscale
ACL sketch (phones and laptops reach the API port; the workstation additionally
reaches port 8200; nothing else does), the `tailscale serve` or `tailscale cert`
recipe that gives the API a Let's Encrypt certificate on its MagicDNS name, and
the `BAO_ADDR` value the workstation uses. The Chrome extension README gains the
tailnet API URL and the matching host permission note. This is the precondition
for every unattended credential write in later capabilities.

**Acceptance Outcomes:**
- `docs/TAILNET.md` exists and is linked from `CLAUDE.md` and `docs/SETUP.md`.
- The documented compose or systemd configuration binds OpenBao and the API to the Tailscale address, and a listener check in the setup steps shows no `0.0.0.0` listener for either port.
- The API answers over HTTPS on its MagicDNS hostname with a certificate that Chrome trusts without a manual exception.

### Capability: OpenBao secret sink for the auth CLI

Replace the Railway-only `--deploy` flag on `aca auth` commands with a
`--to railway|bao|secrets-file` sink abstraction under `src/cli/`. The OpenBao
sink must use KV v2 `patch_secret` on the existing `secret/newsletter` path so a
single-key refresh never overwrites the LLM keys stored alongside it, because
the background token manager only re-fetches that one path. Ship two AppRole
policies in the `bao-vault` seed script: a workstation role limited to `patch`
on `secret/data/newsletter`, and the worker role with `read` plus `patch` on the
same path so adapters can persist rotated cookies. Existing Gmail and YouTube
OAuth flows gain `--to bao` for free.

**Acceptance Outcomes:**
- `aca auth gmail --to bao` writes only `GMAIL_OAUTH_TOKEN_JSON` and leaves every other key at the path byte-identical, proven by a test against a fake KV v2 client.
- A write with the workstation AppRole succeeds for `patch` and is denied for `read` and `delete`.
- The Railway sink behaves exactly as `--deploy` did, and `--deploy` remains as a deprecated alias for one release.

### Capability: Live credential provider for rotating secrets

Introduce a `CredentialProvider` that resolves a named credential at request time
by consulting the OpenBao cache first and falling back to `Settings`. The
module-level `settings` object is built once behind `lru_cache`, so adapters that
read `settings.substack_session_cookie` keep the boot-time value forever. Each
credential carries `saved_at` and `last_verified_at` metadata stored beside the
value. Migrate the Substack adapter to the provider. Every credential read and
write passes through the existing log redaction so no cookie value appears in
logs, payloads, or alerts.

**Acceptance Outcomes:**
- After a KV patch and one token-manager refresh, a long-running worker process uses the new Substack cookie without restart, proven by an integration test that swaps the cache.
- `substack.py` no longer references `settings.substack_session_cookie` directly.
- The provider exposes `saved_at` for `aca auth status`.

### Capability: Session expiry detection and readiness

Make a dead session visible instead of silently degrading. The Substack adapter
detects a login redirect or an HTML login page in place of JSON and raises a
typed readiness failure with a stable code such as `session_expired`. The
descriptor's `readiness_resolver` resolves through the credential provider so a
freshly patched cookie flips readiness without a restart. `aca auth status`
gains one row per browser session showing `saved_at`, `last_verified_at`, and
the refresh command. When the terminal-event outbox from the
`production-telemetry-and-out-of-band-alerting` change is available, the
readiness failure is classified there and the alert names the exact refresh
command; until then it surfaces through `aca auth status` and the scheduled
real-ingestion evidence artifact.

**Acceptance Outcomes:**
- A Hoverfly-simulated login redirect makes the Substack descriptor report `ready=false` with code `session_expired` and produces zero rows rather than a partial run.
- `aca auth status --json` lists `substack` and `x` sessions with `saved_at` and `last_verified_at`.
- The alert body, once the outbox is wired, contains the refresh command and no cookie value.

### Capability: Browser-session capture CLI

Add `aca auth session substack|x`. The command launches headed Chromium through
Playwright with `launch_persistent_context` on a per-site profile directory
under `~/.aca/browser-profiles/`, opens the login page, and polls
`context.cookies()` until the target cookies exist. It validates them with one
cheap authenticated request per site, then writes them with `saved_at` through
the secret sink. The profile directory persists so a later run needs no login.
No refresh timer is created: routine `ct0` rotation is handled by the adapter's
write-back, and this command is only re-run when an expiry alert fires. The
profile directory is a session credential and must be excluded from every
backup and sync path.

**Acceptance Outcomes:**
- Running the command with a stubbed browser context that already holds the cookies validates them and patches OpenBao within one invocation, with no cookie value on stdout or in logs.
- Running it against a context that never produces the cookies exits non-zero with a timeout message after the configured wait.
- `docs/SETUP.md` replaces the manual DevTools instructions for Substack with the command, and `~/.aca/browser-profiles/` is listed in the backup and sync exclusion documentation.

### Capability: X bookmarks source contract and registry

Register `x_bookmarks` as a canonical ingestion source, contract first. Add
`XBookmarksIngestCommand` to `openspec/contracts/content-workflows/openapi/v1.yaml`
and regenerate `src/contracts/workflow_models.py`; never hand-edit the generated
file. Add `ingest.x-bookmarks` and `x_bookmarks` to the closed literals in
`src/ingestion/result.py`, add the command model to `COMMAND_MODELS`, add
`XBookmarksSource` with `expand_links` and `max_entries` to the `Source` union
in `src/config/sources.py`, ship `sources.d/x_bookmarks.yaml`, and add a
`SourceDescriptor` modelled on Readwise with `scheduled=True`, a bulk planner,
and a readiness resolver that fails closed with `x_bookmarks_credentials_missing`
when the cookies are unset. Add `X_BOOKMARKS` to `ContentSource` with an Alembic
migration using `ALTER TYPE contentsource ADD VALUE IF NOT EXISTS`. Add a
network-free fixture to `tests/fixtures/sources/library.py` so the
fixture-registry completeness check passes.

**Acceptance Outcomes:**
- `aca ingest x-bookmarks` submits an operation through `OperationService` and the CLI, HTTP, MCP, and frontend transports all list the source.
- `alembic heads` reports a single head and the enum migration is idempotent.
- The source fixture registry test passes with `x_bookmarks` covered and the descriptor reports `ready=false` when credentials are absent.

### Capability: X bookmarks adapter with session write-back

Implement `src/ingestion/x_bookmarks.py` as a port of the exporter's fetch logic
to httpx: the public web-app bearer token, the `auth_token` and `ct0` cookies,
the `x-csrf-token` header equal to `ct0`, discovery of the rotating `Bookmarks`
GraphQL query ID from X's JavaScript bundles with the last good ID cached as a
DB override and re-scraped on 404, cursor pagination, and 429 handling that
honours `x-rate-limit-reset`. Persist each bookmark as a Content row with
`source_type=X_BOOKMARKS` and `source_id="xpost:{id}"`, rendering the document
through the same thread-to-markdown path as the Grok search adapter so both X
sources produce one shape. Incremental sync pages newest-first and stops when an
entire page's IDs already exist, with `--full` to override. When X issues a new
`ct0` in a `Set-Cookie` header, the adapter patches OpenBao through the sink
before the response is discarded. A login page in place of JSON raises the typed
`session_expired` readiness failure. The adapter runs from the standard Python
worker image and shells out to nothing.

**Acceptance Outcomes:**
- Hoverfly tests cover query ID discovery, a two-page cursor walk, a 429 with `x-rate-limit-reset`, a rotated `ct0` that is written back through a fake sink, and a login-page response that yields `session_expired`.
- A second run against unchanged bookmarks fetches exactly one page and ingests zero rows.
- A bookmarked post that Grok search later surfaces is deduplicated by `source_id` and not inserted twice.

### Capability: Linked-article expansion for bookmarks

When `expand_links` is enabled on the source, the adapter submits one
`UrlIngestCommand` per expanded outbound URL in a bookmarked post through
`OperationService`, so the linked article is summarized as its own row while the
post row remains the receipt. The existing reference hook still records the link
as a `content_reference` so the relationship is queryable either way. Media-only
and self-referential X URLs are skipped.

**Acceptance Outcomes:**
- With `expand_links: true`, a fixture bookmark carrying one external link produces exactly one submitted `url` operation and a `content_reference` from the post to the article.
- With `expand_links: false`, no url operation is submitted and the reference is still recorded.

### Capability: Documentation and user guide for the new sources

Update `docs/USER_GUIDE.md`, `docs/SETUP.md`, `docs/MOBILE_CAPTURE.md`, and
`CLAUDE.md` so the X bookmarks source, the session capture command, and the
credential lifecycle are discoverable. `docs/MOBILE_CAPTURE.md` states that
bookmarking on X replaces the share-sheet path for X content. `docs/GOTCHAS.md`
gains the two new pitfalls: frozen `settings` versus the live provider, and KV v2
`create_or_update` clobbering sibling keys.

**Acceptance Outcomes:**
- Every new CLI command and setting appears in the documentation index tables and the setup guide.
- `docs/GOTCHAS.md` contains both new entries.

### Capability: Extension session sync button

Add a "Sync session" action to the Chrome extension that reads the `substack.sid`,
`auth_token`, and `ct0` cookies with the `cookies` permission and host
permissions for `substack.com` and `x.com`, and posts them over the tailnet to a
new admin endpoint that writes through the OpenBao sink. The endpoint keeps the
`X-Admin-Key` check and the audit log fingerprint. This is the fast manual
response when an expiry alert fires and the operator is at a laptop rather than
the workstation.

**Acceptance Outcomes:**
- The endpoint rejects requests without a valid admin key, records an audit row, and patches only the session keys.
- The extension manifest declares `cookies` and the two host permissions, and the README documents the tailnet API URL.

## Constraints

- All ingestion must be submitted through `OperationService` as a canonical durable operation; no transport may execute X bookmark fetching inline.
- New commands must be added to the OpenAPI contract first and the Python models regenerated; `src/contracts/workflow_models.py` must never be hand-edited.
- Adding a `ContentSource` value must ship an Alembic migration with `ALTER TYPE contentsource ADD VALUE IF NOT EXISTS`, and `alembic heads` must remain a single head.
- Every registry source must have a network-free fixture or a reviewed exclusion in `tests/fixtures/sources/library.py`.
- No cookie value may appear in stdout, logs, payloads, alerts, process argument lists, or test output; all credential handling must pass through the existing log redaction.
- OpenBao writes must use KV v2 `patch` semantics on the existing `secret/newsletter` path; whole-path `create_or_update` is forbidden outside the seed script.
- The credential capture path must not pass any secret through a language model or an agent transcript.
- The worker image remains `python:3.12-slim`; no Node.js runtime may be required by any adapter.
- OpenBao and the API on gx-10 must bind only to the Tailscale interface; nothing in this effort may expose a port to the public internet.
- The Playwright browser profile directory must be excluded from `aca backup`, `aca sync`, and every artifacts tarball.
- The X adapter must honour `x-rate-limit-reset`, use a conservative page size, and be scheduled at a quiet hour because it shares the operator's account and IP with the operator's own browser.
- `SUBSTACK_SESSION_COOKIE`, `X_AUTH_TOKEN`, and `X_CT0` must be added to the Railway secret allowlist for the interim while both platforms exist, and removed when Railway is retired.
- CLI JSON output must remain pure: one JSON document on stdout, diagnostics on stderr.
- Readiness for credential-gated sources must fail closed; a missing or expired credential yields `ready=false` with a stable code, never a partial run.

## Phases

### Phase 1: Tailnet and secret plumbing

- Tailnet exposure baseline for gx-10 services
- OpenBao secret sink for the auth CLI
- Live credential provider for rotating secrets

### Phase 2: Session lifecycle

- Session expiry detection and readiness
- Browser-session capture CLI

### Phase 3: X bookmarks source

- X bookmarks source contract and registry
- X bookmarks adapter with session write-back
- Linked-article expansion for bookmarks

### Phase 4: Surface and convenience

- Documentation and user guide for the new sources
- Extension session sync button

## Out of Scope

- Replacing `X-Admin-Key` with Tailscale identity headers; that touches the middleware ordering in `src/api/app.py` and is a separate decision.
- Credential capture driven by computer use or Claude in Chrome operating DevTools; it automates the brittle step instead of removing it and routes secrets through a model context.
- Reading cookies directly from Chrome's on-disk cookie database.
- Wrapping the upstream Node.js `x-bookmarks` CLI as a subprocess.
- Any X ingestion beyond the operator's own bookmarks: timelines, lists, search, or other accounts.
- Changes to the gx-10 backup scheme, WAL archiving, or the OpenBao raft snapshot; the existing snapshot already covers cookies stored in OpenBao.
- The terminal-event outbox itself, which belongs to `production-telemetry-and-out-of-band-alerting`; this effort only emits into it once it exists.
- A workstation refresh timer; adapter write-back makes it unnecessary and it would depend on the laptop being awake.
