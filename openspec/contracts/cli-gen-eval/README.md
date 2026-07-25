# CLI Gen-Eval Contracts

This directory is the durable source of truth for the `aca` CLI evaluation contract.
Live application code, generators, and tests consume these files directly. Copies under
`openspec/changes/archive/` are historical snapshots and MUST NOT be used as runtime or
test inputs.

## Why these files exist here

The gen-eval framework is **not a dependency of this repository**. It is an external
tool, acquired as a pinned versioned artifact, and it is never resolved from a
filesystem-adjacent checkout in any enforcing context
(`establish-cli-gen-eval-coverage` D1/D2).

That split means schema conformance must not depend on the framework being installed.
Vendoring the schemas here lets CI validate the descriptor, the scenario suites, and the
emitted report using nothing but `jsonschema` — so a failed runner acquisition reduces
coverage *visibly* rather than passing silently. It is also what makes the contract
shareable across repositories without a shared runtime: another repository pins the same
contract version and validates its own artifacts the same way.

## Files

- `interface-descriptor.schema.json` — generated from
  `gen_eval.descriptor.InterfaceDescriptor`.
- `scenario.schema.json` — generated from `gen_eval.models.Scenario`.
- `eval-report.schema.json` — hand-assembled from `gen_eval.reports.generate_json_report`
  with the generated `ScenarioVerdict` embedded as a `$def`. Upstream `GenEvalReport` is a
  plain dataclass and cannot emit its own schema; see `UPSTREAM.md` UP-2 in the change
  directory, which proposes promoting it to pydantic so this file becomes fully generated.

Each file carries provenance annotations: `x-gen-eval-contract-version`,
`x-generated-from-ref`, `x-generated-from`, and `x-generator`.

The runtime copies at `src/cli_gen_eval/schemas/` MUST stay byte-identical to these
files; `tests/cli_gen_eval/test_contract.py` enforces that parity, matching the pattern
`openspec/contracts/release-smoke/` uses for its evidence schema.

## Regenerating

The pin lives in `evaluation/contract/pin.json`. Regeneration reaches the pinned gen-eval
ref through `uvx`, so the framework never enters this project's environment:

```bash
make gen-eval-contract-schemas         # regenerate both copies
make gen-eval-contract-schemas-check   # fail on drift (needs network)
make gen-eval-contract                 # validate descriptor + scenarios, no runner needed
```

Bump `contract_version` in `evaluation/contract/pin.json` whenever a regenerated schema
changes shape, and record the reason in the changelog below. `src/cli_gen_eval/__init__.py`
holds the same version as a module constant so runtime code can assert it without
depending on the repository layout; the parity test covers all three.

## Report-schema strictness

`eval-report.schema.json` sets `additionalProperties: true` — gen-eval may add report
keys, and an unknown key is not a contract violation. Every key that
`generate_json_report` writes unconditionally is `required`, so a report missing one is
malformed. `per_visibility` is optional because upstream only writes it when non-empty.

Note that schema validity is necessary but **not** sufficient. A zero-scenario report is
well-formed and would report `pass_rate` of `0.0`; rejecting a vacuous run is the report
validator's job (minimum scenario counts plus an empty `unevaluated_interfaces`), not this
schema's. `tests/cli_gen_eval/test_contract.py` pins that boundary explicitly.

## Changelog

- `1` — initial pin. Schemas generated from `agentic-coding-tools`
  `e5dcab80c5c6d847fa425a08b569595a224eb8cd` (gen-eval `0.1.0`), with the report schema
  hand-assembled pending UP-2.
