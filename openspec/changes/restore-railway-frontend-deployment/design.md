# Design: Restore the Railway frontend deployment

## Context

Railway service `aca-app` builds with root directory `/web` and
`web/railway.json`. Production deployment `6ceaa0f8-41e1-42e2-abeb-80d749688d1e`
failed after Railpack selected npm and executed:

```text
npm run build
> pnpm contracts:check && tsc -b && vite build
sh: 1: pnpm: not found
```

The build context is intentionally isolated, so the Python contract generator
must run before deployment in a complete repository checkout.

## Decisions

### D1. Match the isolated Railpack package manager

Commit `web/package-lock.json`, explicitly exempt it from the repository's
global `package-lock.json` ignore rule so Railway's CLI uploader includes it,
declare Node 22 in `web/package.json`, use the same Node major in CI, and use
`npm ci`. Configuration tests assert the runtime and upload-boundary
invariants. Keep the build command composed only of package-local binaries
(`tsc` and `vite`).

This gives Railway an exact dependency graph without changing the service root
or requiring pnpm inside the static build.

### D2. Separate artifact construction from contract verification

`npm run build` constructs the deployable frontend. `npm run contracts:check`
remains available but is no longer transitively invoked by the production
build.

The separation reflects two different contexts:

- production build: isolated `web/`, Node toolchain;
- contract verification: full repository, Python/uv plus OpenSpec inputs.

### D3. Add one CI job that owns both gates

The `frontend-release` CI job installs the exact npm dependency graph under
Node 22, provisions uv, runs the existing generated-contract drift check from
a full checkout, runs
`npm test -- --run src/lib/api/__tests__/workflow-contracts.test.ts`, and runs
the exact production build. A failure in any boundary blocks CI.

### D4. Promote only an immutable, recoverable revision

Before deployment, record the current and last successful deployment IDs,
their revisions, the public domain, exact Railway target IDs, a tested rollback
command, and abort criteria. The candidate must be a clean committed and pushed
SHA. Create or update a draft PR to `main`, wait for the
`frontend-release` check on that exact SHA, and require success.

Create a temporary detached worktree at the checked SHA, confirm its `HEAD` and
clean status, and run `railway up --ci` from its repository root with explicit
project, environment, service, and a message containing the SHA. The Railway
service retains its checked `/web` root. Query `railway deployment list --json`
and require the resulting deployment's `meta.cliMessage` to equal
`frontend-release <CI-passed-SHA>` and its successful active revision record to
name that same SHA. Railway CLI uploads leave `meta.commitHash` null, so the
clean detached checkout plus persisted SHA-bearing CLI message is the
supported identity proof. Abort before mutation if the prior release cannot be
identified or redeployed.

### D5. Verify the deployed revision at the network boundary

After local and CI-equivalent gates pass, deploy the current feature snapshot
to the explicitly resolved production frontend service. Verify:

1. Railway deployment reaches `SUCCESS`;
2. the public frontend loads;
3. capability discovery is requested;
4. exactly one controlled ingestion submission targets
   `/api/v1/ingestions`;
5. bounded frontend/backend HTTP logs contain no retired mutation requests
   during the verification window.

The canary is a `url` command forced to `routing_mode: "webpage"` for
`https://example.com/?aca-release-smoke=<short-sha>`, with title and notes
identifying the release. In browser developer tools, enable preserved network
logging, open the deployed ingestion UI, fill the form once, and click submit
exactly once. Do not script the request, reload, double-click, or repeat it
after an ambiguous response. Capture the durable operation ID and terminal
status. The unique URL marker also makes the server-derived idempotency input
unique. Retain the resulting record as explicitly labeled release evidence
unless a supported deletion path is confirmed; no ad-hoc database cleanup is
allowed.

### D6. Keep production evidence durable

Populate the checked-in sanitized evidence template with the deployed revision,
public URL, verification-window bounds, capability status, canonical request
method/path/status, durable operation ID/status, browser/network attribution,
bounded backend-log correlation, and rollback deployment ID. Do not persist
secrets, cookies, administrator keys, request headers, or raw Railway variable
values. A repository validator treats blank fields, revision mismatch,
non-success states, nonzero retired-route counts, missing time bounds, or
missing browser/log/operation correlation as release failures.

## Data and Contract Impact

- No HTTP schema or database migration changes.
- Generated workflow contracts remain byte-for-byte checked by CI.
- The frontend continues to use the existing `CapabilityDocument`,
  `IngestCommand`, and durable operation response models.

## Failure and Rollback

- Build failure: inspect the exact deployment's bounded build log; do not
  redeploy repeatedly without a code/config change.
- Runtime failure: stop canary work, inspect bounded deployment and HTTP logs,
  then execute the pre-recorded rollback command to the prior successful
  deployment if health, capability discovery, or static asset loading fails.
- Contract drift failure: regenerate contracts in a full checkout and review
  the generated diff; never bypass the CI step in Railway.

## Validation

- Python configuration tests for package/CI boundary invariants.
- `npm ci` and `npm run build` from `web/`.
- `npm run contracts:check` from the full checkout.
- focused workflow contract unit tests.
- exact-SHA GitHub `frontend-release` success.
- strict OpenSpec and work-package validation.
- Railway build/deployment status plus bounded production HTTP evidence.
