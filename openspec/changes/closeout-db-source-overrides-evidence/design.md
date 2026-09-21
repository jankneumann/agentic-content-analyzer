# Design: Source override closeout

## Context

The implementation is already authoritative for runtime behavior, while its
archived proposal contains stale endpoint and request-shape claims. The
closeout therefore favors compatibility and executable evidence over a new API
design. The durable `source-configuration` spec retains ownership of merge and
source-resolution behavior; this change verifies the public management
contract and its supporting evidence.

## Decisions

### D1. Keep the discriminator inside the full `config` object

POST `/api/v1/sources` accepts:

```json
{
  "config": { "type": "rss", "url": "https://example.com/feed.xml" },
  "description": "optional operator note"
}
```

`config.type` is the single meaningful discriminator. The published model has
no top-level `type`. Existing `/api/v1` Pydantic models ignore unknown request
siblings, so compatibility evidence must prove that a legacy top-level `type`
cannot override or conflict with the nested value; this closeout does not add
`extra="forbid"` and turn tolerated input into a 422.

**Rejected alternatives:** publishing the archived top-level `type` would create
two potentially conflicting discriminators. Tightening all request models to
reject unknown siblings would be a separate compatibility change rather than a
faithful evidence closeout.

### D2. PATCH is the sole enabled-state mutation

`PATCH /api/v1/sources/{key}` accepts exactly `{ "enabled": boolean }`.
POST remains full-config upsert; DELETE removes a database override. PATCH of a
YAML source without an override creates a self-describing shadow. Deleting that
shadow restores the YAML definition; deleting a DB-only source removes it.

Successful POST/PATCH responses carry `source_key`, `version`, `origin`, and
`enabled`. A new row begins at version 1 and each effective update advances the
version. DELETE returns `source_key` and `deleted=true`. GET returns the existing
`SourcesOverview` projection: source key/type/label or URL/origin/enabled plus
counts, not mutation version.

Source routes preserve their legacy JSON errors: service 400/404 responses are
`{detail: string}`; body validation is 422 `{detail: ValidationError[]}`; and
auth middleware returns 401/403 `{error, detail, trace_id?}`. The durable
OpenAPI names these separately rather than applying the RFC 7807 schemas used by
newer endpoint families.

**Rejected alternatives:** PUT or generic partial-config PATCH would introduce
new merge/version semantics; dedicated `/enable` and `/disable` routes are the
obsolete historical design this closeout is correcting.

### D3. Extend the existing durable content-workflow contract domain

The additive paths and source schemas live in
`openspec/contracts/content-workflows/openapi/v1.yaml`. The existing generator
produces Python and TypeScript contract models, including the runtime copy in
`src/contracts/workflow_models.py` and the web copy in
`web/src/generated/workflow-contracts.ts`.

HTTP transport wrappers remain hand-maintained. Tests compare their payloads
and response types with the generated contract; the plan does not claim to
generate clients.

**Rejected alternative:** create a second source-management OpenAPI domain and
generator. That adds permanent contract infrastructure for four routes already
adjacent to configured ingestion and defeats the bounded closeout.

### D4. Model the existing authentication boundary

Outside credential-free local development, every source route is protected by
the API authentication middleware and accepts an owner session cookie or
`X-Admin-Key`. Write routes retain `verify_admin_key` as defense in depth with
the same two credential modes. Missing credentials yield 401; an explicitly
invalid key yields 403; rejected writes create no row and advance no version.

The stale web comment that calls GET public is corrected. OpenAPI documents
both supported credential schemes without implying anonymous production read.

**Rejected alternative:** publish GET as public because its route lacks a
local dependency. Authentication is enforced centrally by middleware; a
route-only reading would encode the wrong production boundary.

### D5. Public management keys never expose private locators

Ordinary sources use `<type>:<locator>`. Obsidian uses an HMAC-derived
`src_[a-f0-9]{20}` key at public boundaries. Responses and errors never expose
`vault_id`, `vault_path`, `ingest_folder`, private tags, or a caller-supplied
private natural key. Path parameters are URL-encoded by clients and retain the
existing server validation (non-empty and no NUL); this closeout does not invent
a new HTTP length bound.

Write configuration remains distinct from read/mutation projections: an
authenticated full-config POST may carry worker-local configuration, but no
public response model echoes it.

**Rejected alternative:** describe every management key as a natural key, as
the archive does. That would regress the Obsidian privacy boundary.

### D6. Browser management is intentionally asymmetric

The add dialog supports every non-worker-filesystem source type, adding
Readwise as the one currently missing type. Its fields are a reviewed quick-add
subset; advanced options remain available through YAML, CLI, or direct API use.

The browser offers no Obsidian creation/editing because it cannot browse or
validate the worker mount, allowed roots are deployment policy, and private
paths cannot be read back to prepopulate an edit form. Trusted CLI/API callers
may still submit full Obsidian configuration. Existing Obsidian rows may be
rendered with a generic label plus opaque key and may be enabled, disabled, or
deleted without exposing private configuration.

GET does not distinguish a DB-only override from a DB shadow over YAML: both
project as `origin="db"`. The delete control therefore uses one truthful message:
“Remove database override; a YAML definition may reappear.” Backend tests prove
the two outcomes; browser mocks must not fabricate unavailable provenance.

Component tests render `SourcesConfigurator` with Testing Library and a jsdom
environment. Playwright tests use deterministic API mocks for browser control
and error paths. Backend/API tests separately prove persisted shadow and delete
semantics; the browser suite does not pretend its mocks are database evidence.

**Rejected alternative:** browser-based Obsidian creation/editing. A safe UX
would first need a deployment-owned path-alias registry and worker readiness
contract, which is a separate feature rather than evidence closeout.

### D7. Prove the deployed migration chain on disposable PostgreSQL

A migration-local fixture uses an isolated disposable PostgreSQL schema rather
than the session-shared `test_engine`. It upgrades to the predecessor revision
`b8f8b5ededed`, creates an unrelated sentinel, upgrades through
`c3d4e5f6a7b8` to current head, and verifies:

- the source migration is present in the revision chain and head is current;
- PostgreSQL JSONB for `config`;
- column types, nullability, and server defaults;
- primary key, unique `source_key`, and `source_type` index;
- insert/default behavior and JSON round trip;
- preservation of the unrelated sentinel table/row;
- a second `alembic upgrade head` is a no-op.

A test-local schema verifier separately demonstrates that the historical
migration's table-exists guard does not make an incompatible manual table
supported. This is diagnostic evidence, not a new production preflight. The
runbook directs an operator to back up, remove or rename, and recreate that table
through Alembic.

**Rejected alternative:** alter the historical migration to repair arbitrary
pre-existing schemas. It has already shipped, cannot repair databases that
recorded it as applied, and would make historical behavior non-reproducible.

### D8. Retain the complete-catalog GET contract

GET `/api/v1/sources` returns the complete operator-managed source catalog and
one grouped content-count query. It is not content history and currently has no
pagination. The closeout documents this bounded configuration assumption and
does not add pagination without measurements or a compatibility proposal.

**Rejected alternative:** add pagination as incidental closeout work. That
would change the frontend/CLI contract and ordering semantics without evidence
of a production cardinality problem.

### D9. Current documentation is the durable operational record

`docs/ARCHITECTURE.md` records the four methods, nested request, PATCH/shadow,
auth, and public-key decisions. `docs/SETUP.md` records setup, CLI/API examples,
precedence, DB-only deletion, YAML-shadow restoration, fail-open behavior,
backup/recovery, and unsupported-schema recovery. The dated source archive is
never edited.

**Rejected alternative:** place corrections only in the archived proposal or
an active-change README. Neither remains the live operator/design authority.

## Risks and mitigations

- **Contract generation widens a workflow model module.** Keep source schemas
  namespaced and additive; drift tests verify no existing workflow schema
  changes.
- **Component harness dependencies increase frontend test surface.** Use the
  existing Vitest toolchain with only jsdom and Testing Library dependencies;
  update both tracked npm and pnpm lockfiles used by CI/local workflows.
- **Mocked browser tests can overstate integration.** Pair them with FastAPI,
  client, and PostgreSQL suites and label evidence boundaries explicitly.
- **Private source data can leak through error strings.** Add negative contract
  and API assertions for both success and failure paths.

## Implementation dependency graph

```text
D1-D9 locked
  ├─ wp-contract ────────────────┬─ wp-web-component
  │                              └─ wp-web-browser
  ├─ wp-web-component-harness ───── wp-web-component
  ├─ wp-migration-evidence
  ├─ wp-operator-docs
  └─ wp-architecture-docs

all work packages ── wp-integration
```

Independent roots after the planning decision: WP1, WP2a, WP4, WP5, and WP6.
Maximum theoretical parallel width: 5. WP2b waits for WP1 and WP2a; WP3 waits
for WP1. Integration waits for all packages.
