# Architecture Impact: closeout-db-source-overrides-evidence

## Summary

This change publishes the existing source-management boundary in the canonical
content-workflows OpenAPI, keeps the FastAPI/CLI/web implementations aligned,
and adds evidence around the already-shipped source override migration. It does
not introduce a new service, registry, persistence path, or production database
migration.

## Affected boundaries

- API contract: additive GET/POST/PATCH/DELETE source operations, authenticated
  management keys, nested `config.type`, and legacy error families.
- Generated contracts: deterministic Python and TypeScript models generated
  from the canonical OpenAPI.
- Privacy boundary: Obsidian worker-local identity remains opaque in HTTP,
  browser, CLI, and audit output; audit normalization fails closed.
- Browser: Readwise is the only newly exposed quick-add form; Obsidian remains
  display/toggle/delete-only through a validated opaque key.
- Database: tests exercise the historical migration from its predecessor to
  head in an isolated PostgreSQL database. Production schema code is unchanged.

## Diagnostics

- Architecture freshness pipeline completed with no errors; PostgreSQL static
  analysis was unavailable because the generic analyzer expects a different
  migrations directory.
- Scoped flow validation reported 0 findings across the changed files.
- The repository has no `architecture-diff` Make target, so the new-cycle
  baseline producer was unavailable.
- Structural lint reported 15 advisory file-size nits on existing generated,
  lock, documentation, test-fixture, and monolithic files. No dependency,
  naming, broken-flow, or new-cycle failure was reported.

## Risk assessment

The primary risks are contract/runtime drift and private locator disclosure.
Generator drift checks, bidirectional Obsidian validation parity, authenticated
no-mutation tests, component/browser privacy tests, and deeply encoded audit
path regressions directly guard those risks.
