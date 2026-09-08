# Contracts: change-visualization-graph-document

| File | Origin | Role |
|---|---|---|
| `graph-doc.schema.json` | `coldteadotai/pr-lens` `packages/schema/json-schema/graph-doc.schema.json`, schema contract `0.1.1`, package `@coldtea/pr-lens-schema@0.2.1`, MIT © 2026 Coldtea AI | The change graph document every projector output MUST validate against. Vendored verbatim; do not hand-edit. Re-vendor from the pinned package when the contract version is bumped. |
| `corrections.schema.json` | same source, `config.schema.json` | Shape of the human corrections overlay (`map.rename`, `map.exclude`, `map.lane`, `map.group`). Only the `map` object is used by the projector; `lenses`, `branding` and `github` are pr-lens hosted-app concerns and are ignored. |

The upstream JSON Schema is draft 2020-12. The Python projector validates with
the `jsonschema` library at draft 2020-12; the Node renderer validates with the
pinned `@coldtea/pr-lens-schema` package. Both MUST agree on the vendored
`version` field, which is the contract's `schemaVersion`.
