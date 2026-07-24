# Reconciliation: database source overrides

**Disposition**: Archive the implemented backend/CLI foundation with inaccurate
evidence tasks reopened. Continue closeout in
`closeout-db-source-overrides-evidence`.

## Verified foundation

- Validated source union, natural keys, model/service, YAML/DB precedence,
  disable shadows, fail-open behavior, authenticated POST/PATCH/DELETE runtime,
  and CLI commands.
- RI-03 focused gate, including `tests/api/test_source_write_api.py`, passed as
  part of 68 filtering/source-override tests.

## Reopened historical claims

OpenAPI request-shape alignment, migration execution evidence, settings
component/browser behavior, full UI acceptance, and setup documentation are
not complete. The historical enable/disable design also differs from the
implemented PATCH endpoint.

Only evidenced source-configuration requirements were manually merged into the
main spec. The old delta SHALL NOT be synchronized automatically.
