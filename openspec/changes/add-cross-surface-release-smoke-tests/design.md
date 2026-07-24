# Design: Add cross-surface release smoke tests

## Context

RI-01 repaired the real CLI's optional cursor serialization. RI-02 restored the
frontend production build and proved one release manually. Neither result
provides a repeatable gate against a deployed frontend/API pair. The repository
also lacks a served revision contract: `/health` reports only service health,
and the frontend bundle does not identify its source revision.

The release boundary must detect stale artifacts without making production
state changes. It must also support a stronger staging-only scenario without
letting a flag or missing environment label accidentally authorize production.

## Decisions

### D1. Publish revision identity in existing operational surfaces

Extend the public `/health` liveness response with normalized `revision` and
`revision_source` fields. For the API, accept only the platform's immutable full
commit SHA (`RAILWAY_GIT_COMMIT_SHA`, or `GITHUB_SHA` in CI) and its allowlisted
provenance; never let an application runtime override claim a promotion
revision. A local explicit value may produce only the conspicuous `development`
provenance.

The canonical frontend release uses `railway up` from a clean detached checkout,
where Railway leaves `meta.commitHash` null. Before upload, a repository script
verifies the requested full SHA equals detached `HEAD`, verifies tracked files
are clean, and writes a bounded canonical `web/release-build.json` stamp. The
runbook hashes that stamp and requires Railway `meta.cliMessage` to name the
same SHA. Vite consumes the stamp at build time and bakes
`verified_detached_sha` provenance into frontend HTML and the revision-bound
asset manifest. The stamp cannot select a different SHA, and runtime
configuration cannot relabel the built artifact. GitHub integration builds may
use `GITHUB_SHA` directly. Do not add these operational fields to the canonical
content workflow OpenAPI.

The runner reads the backend values from `/health` and the frontend values from
cache-busted served HTML. Expected full SHAs are optional for local diagnostics
but mandatory in promotion CI. Release mode rejects missing values,
non-40-character lowercase SHAs, local/untrusted provenance, and mismatches.
Configuration tests cover the CLI-upload/no-platform-SHA path, a mismatched or
dirty stamp attempt, missing stamp, and the verified detached-SHA success path.

### D2. Use one Python orchestrator and real surface boundaries

Create a release-smoke module and thin command-line script. Direct HTTP checks
establish liveness and canonical discovery. The CLI check invokes the installed
`aca --json capabilities` and configured-source commands in a subprocess while
supplying `API_BASE_URL` and `ADMIN_API_KEY` only through a scrubbed environment.
The browser check uses the explicitly pinned Python Playwright extra against the
deployed frontend and does not replace frontend requests with mocks.

Declare Playwright and JSON Schema format validation in a dedicated
`release-smoke` Python extra. Release jobs install that explicit extra and the
pinned Chromium runtime; normal application installations do not inherit the
browser toolchain.

Tests may use local deterministic HTTP/browser fixtures, but the release
workflow must provide deployed origins and run the same orchestrator.

Before any credential-bearing request, load an approval-protected target policy
whose exact frontend origin, API origin, target identity, classification,
expected revisions, and production deny aliases cannot be workflow inputs.
Require HTTPS outside loopback-local mode. Disable HTTP redirects and reject
every destination that is not the exact pinned origin before adding
authentication. Browser routing aborts off-policy API requests, and observed
workflow traffic must target the pinned API origin. The production and staging
GitHub environments own separate policies and secrets.

### D3. Defeat stale browser state and inspect dormant code

Use a new browser context with service workers blocked, no persisted storage,
cache-disabling request headers, and a cache-busting navigation token that is
never persisted. Observe all requests and require successful capability plus
configured-source discovery. The first-page request must have no `cursor` query
key.

Vite emits `release-assets.json` from the final bundle. It binds the full
frontend SHA to every JavaScript chunk, including dormant lazy chunks, with
path, size, and SHA-256 digest. The runner fetches this authoritative manifest,
then streams every listed same-origin asset with redirects disabled; it also
requires every observed first-party JavaScript request to be listed. Fail on a
revision/digest/content-type mismatch, redirect, duplicate/cycle, missing
asset, unlisted observed asset, more than 512 assets, more than 10 MiB per
asset, more than 64 MiB total, or a 60-second scan deadline.

Scan observed method/normalized-path pairs and all verified asset bytes for the
checked-in baseline retired-route policy. The baseline contains at least
`POST /api/v1/contents/ingest` and `POST /api/v1/content/save-url`, cannot be
overridden, and handles absolute/encoded/query variants after normalization.
Runtime policy may add entries only. Evidence records path-free asset SHA-256
digests and counts, not URLs or query strings.

### D4. Make mutation authorization redundant and fail closed

Mutation requires all of:

1. an explicit `--allow-mutations` flag;
2. an exact target identity and origins from the protected `staging` or
   `ephemeral` policy;
3. no match against any protected production identity or origin alias;
4. a checked-in JSON fixture below `tests/fixtures/release_smoke/`;
5. a deterministic idempotency key `aca-release-smoke-v1:<run_id>`.

Reject absolute/traversal/symlink fixture paths, files over 64 KiB, schema
violations, and anything outside the `IngestCommand` data model; no fixture is
executable. Any missing or conflicting signal aborts before request
construction. The runner sends `POST /api/v1/ingestions` once and never retries
an ambiguous submission. It polls the returned operation using read-only GET
requests and passes only on `completed`; `failed`, `cancelled`, timeout, or
response loss is a failure. Operators can reconstruct the idempotency key from
the retained run ID without storing fixture identifiers.

### D5. Treat evidence as a restrictive data contract

Define a JSON Schema plus semantic validator. Allowed fields are schema version,
run ID, target classification, safe origins stripped to scheme/host/port,
bounded UTC times, observed/expected revisions and provenance, named check
outcomes, counts, asset digests, and—only for mutation—opaque operation
ID/status. Disallow additional properties. A failed run may use null only for a
surface it could not safely observe and must carry a corresponding stable
failure code; passing evidence requires complete trusted observations.

The validator rejects credential-like keys or values, query strings, headers,
cookies, raw stdout/stderr, payloads, content identifiers, source URLs, natural
keys, and unbounded messages. The runner writes evidence on failure as well as
success, using stable error codes rather than exception text.

### D6. Separate promotion and mutation workflows

Add a manual/reusable release-smoke workflow with two jobs. The caller chooses
only the tier; exact origins, target identity, expected SHAs, deny aliases, and
credentials come from the corresponding approval-protected GitHub environment:

- production read-only: no environment capable of mutation, expected immutable
  frontend/API revisions required;
- staging mutation: explicit input, approval-controlled environment, staging
  secrets, and an approved checked-in fixture.

Validate schema and semantics before upload. If the runner output cannot
validate, discard it and generate a separate minimal failure envelope from
fixed safe fields and the validator's stable failure code; validate that
envelope before upload. Upload only validated evidence with bounded retention,
then fail the job when compatibility did not pass. Workflow permissions remain
read-only. Documentation makes clear that the workflow verifies an already
deployed pair; deployment remains a separate operation.

## Data and Contract Impact

- `/health` gains a backward-compatible `revision` string.
- Built frontend HTML gains `release-revision` and
  `release-revision-source` meta values plus `release-assets.json`.
- Detached frontend uploads gain an ephemeral, canonical
  `web/release-build.json` input generated only after HEAD/cleanliness checks.
- A new internal JSON evidence schema is versioned under this change and later
  promoted to the release-smoke implementation directory.
- No database migration, workflow mutation schema, generated client, or
  canonical workflow OpenAPI change.

## Security and Privacy

- Admin and app secrets are environment-only and never CLI arguments.
- Evidence has a strict allowlist and is validated before upload.
- Origins are normalized without paths, queries, fragments, or userinfo and
  compared to protected exact allowlists before credentials are attached.
- Browser traces, videos, raw network archives, and raw subprocess logs are not
  release artifacts because they can contain credentials or content.
- The production tier cannot construct a mutation request.

## Failure and Rollback

- Revision absence/mismatch: fail promotion and inspect deployment metadata;
  do not relabel evidence.
- Stamp mismatch/missing identity: abort the Railway upload before build; never
  substitute a manual runtime variable.
- Retired route or cursor serialization: fail promotion and rebuild the
  offending frontend/CLI revision.
- Browser discovery failure: retain the sanitized failure code; raw diagnostics
  stay in the protected job log with secret masking.
- Ambiguous mutation: do not retry; reconstruct the idempotency key from the
  retained run ID and reconcile before any operator-authorized rerun.
- This change verifies releases and performs no deployment, so rollback remains
  the deployment system's pre-recorded procedure.

## Validation

- Focused backend and Vite build-metadata unit tests.
- Python orchestration tests with deterministic HTTP and subprocess doubles.
- Local Playwright fixture exercising a real built frontend client.
- JSON Schema and semantic evidence tests, including pre-observation failure,
  malicious/redaction, provenance, and conditional-null cases.
- Target-policy tests for redirects, aliases, cross-origin browser traffic, and
  credential attachment.
- Asset-manifest tests for lazy chunks, missing assets, redirects, MIME/digest
  mismatches, cycles/duplicates, byte/count/deadline bounds, and completeness.
- GitHub workflow configuration tests.
- Production frontend build and retired-literal scan.
- Strict OpenSpec, work-package DAG, lock, and scope validation.
