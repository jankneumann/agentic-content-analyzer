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

All three are **verbatim copies** of the schemas gen-eval publishes in
`gen_eval.contracts` (UP-2), plus provenance annotations. Nothing here is derived or
hand-authored locally — upstream generates them from the pydantic models that actually
produce and consume the data, and drift-tests them there.

- `interface-descriptor.schema.json` — `gen_eval.descriptor.InterfaceDescriptor`.
- `scenario.schema.json` — `gen_eval.models.Scenario`.
- `eval-report.schema.json` — `gen_eval.reports.GenEvalReport`.

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

Schema validity is necessary but **not** sufficient, in two distinct ways that
`tests/cli_gen_eval/test_contract.py` pins explicitly.

*Vacuity.* A zero-scenario report is well-formed and reports `pass_rate` of `0.0`.
Rejecting a vacuous run is the report validator's job — minimum scenario counts plus an
empty `unevaluated_interfaces` — not this schema's. This is precisely why
`--fail-threshold` alone cannot be trusted.

*Numeric ranges.* The published schema is generated from models that declare no bounds,
so `pass_rate: 1.5` and a negative `total_scenarios` are schema-valid. We deliberately do
not tighten the vendored copy: a locally-stricter schema would disagree with upstream's
drift test and defeat the point of a shared contract. Range sanity therefore also belongs
to the report validator. Raised upstream as `UPSTREAM.md` UP-5.

## Changelog

- `1` — initial pin. Originally generated locally from `agentic-coding-tools`
  `e5dcab80c5c6d847fa425a08b569595a224eb8cd` with the report schema hand-assembled,
  because gen-eval did not publish schemas yet. Repointed at
  `600744a55418938f8691d70f0266c48410e6a545` once UP-2 landed; the files are now verbatim
  copies of the published contract. Same contract version — the upstream publication was
  the first, not a change to an existing one. `startup` also dropped out of the
  descriptor's `required` list (UP-4), a widening at the same version.
