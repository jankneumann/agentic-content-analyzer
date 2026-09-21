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

`config.type` is the single discriminator. There is no duplicate top-level
`type`. This is the shape already used by FastAPI, CLI, web, and tests and is
therefore the only compatible `/api/v1` closeout choice.

**Rejected alternative:** retain the archived top-level `type` plus nested
`config.type`. It is redundant, was never accepted by the runtime, permits
disagreement between two discriminators, and would create a breaking client
change merely to match stale evidence.

### D2. PATCH is the sole enabled-state mutation

`PATCH /api/v1/sources/{key}` accepts exactly `{ "enabled": boolean }`.
POST remains full-config upsert; DELETE removes a database override. PATCH of a
YAML source without an override creates a self-describing shadow. Deleting that
shadow restores the YAML definition; deleting a DB-only source removes it.

Successful POST/PATCH responses carry `source_key`, `version`, `origin`, and
`enabled`. A new row begins at version 1 and each effective update advances the
version. DELETE returns `source_key` and `deleted=true`.

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

Ordinary sources use `<type>:<locator>`. Obsidian and any future private source
type use an HMAC-derived `src_[a-f0-9]{20}` key at public boundaries. Responses
and errors never expose `vault_id`, `vault_path`, `ingest_folder`, private tags,
or a caller-supplied private natural key. Path parameters are URL-encoded by
clients and bounded/validated by the server.

Write configuration remains distinct from read/mutation projections: an
authenticated full-config POST may carry worker-local configuration, but no
public response model echoes it.

**Rejected alternative:** describe every management key as a natural key, as
the archive does. That would regress the Obsidian privacy boundary.

### D6. Browser management is intentionally asymmetric

The add dialog supports every public source type, adding Readwise as the one
currently missing public type. Its fields are a reviewed quick-add subset;
advanced options remain available through YAML, CLI, or direct API use.

Obsidian creation/editing remains worker-local because a browser cannot browse
or validate the worker mount, allowed roots are deployment policy, and private
paths cannot be read back to prepopulate an edit form. Existing Obsidian rows
may be rendered with a generic label plus opaque key and may be enabled,
disabled, or deleted without exposing private configuration.

Component tests render `SourcesConfigurator` with Testing Library and a jsdom
environment. Playwright tests use deterministic API mocks for browser control
and error paths. Backend/API tests separately prove persisted shadow and delete
semantics; the browser suite does not pretend its mocks are database evidence.

**Rejected alternative:** browser-based Obsidian creation/editing. A safe UX
would first need a deployment-owned path-alias registry and worker readiness
contract, which is a separate feature rather than evidence closeout.

### D7. Prove the deployed migration chain on disposable PostgreSQL

The migration test uses the repository fixture that recreates a disposable
PostgreSQL schema with `alembic upgrade head`. It verifies:

- table and Alembic revision presence;
- PostgreSQL JSONB for `config`;
- column types, nullability, and server defaults;
- primary key, unique `source_key`, and `source_type` index;
- insert/default behavior and JSON round trip;
- preservation of an unrelated sentinel table/row;
- a second `alembic upgrade head` is a no-op.

A separate assertion documents that the historical migration's table-exists
guard supports only an already-compatible table. A manually created,
incompatible table is unsupported and must be backed up, removed or renamed,
and recreated through Alembic according to the runbook.

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
  pin through `pnpm-lock.yaml`.
- **Mocked browser tests can overstate integration.** Pair them with FastAPI,
  client, and PostgreSQL suites and label evidence boundaries explicitly.
- **Private source data can leak through error strings.** Add negative contract
  and API assertions for both success and failure paths.

## Implementation dependency graph

```text
D1-D9 locked
  ├─ wp-contract
  ├─ wp-web-component-harness ── wp-web-component
  ├─ wp-web-browser
  ├─ wp-migration-evidence
  ├─ wp-operator-docs
  └─ wp-architecture-docs

all work packages ── wp-integration
```

Independent roots after the planning decision: 6 work packages. Maximum
theoretical parallel width: 6. The component package is the only internal
two-step chain. Integration waits for all packages.
