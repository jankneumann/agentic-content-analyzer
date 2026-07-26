# Upstream handoff: `agentic-coding-tools` prerequisites for ri-06

> Consuming change: `establish-cli-gen-eval-coverage` (ACA roadmap item `ri-06`)
> Target repo: `jankneumann/agentic-coding-tools`, package `packages/gen-eval`

## Status

**UP-1, UP-2, UP-3, and UP-4 all landed on `origin/main` at
`600744a55418938f8691d70f0266c48410e6a545`** (commits `c2213c5f`, `e5fabe3d`).
ACA's pin was moved to that ref. Verified from ACA rather than taken on trust:

```
$ uvx --from "gen-eval @ git+…@600744a5#subdirectory=packages/gen-eval" gen-eval --help
usage: gen-eval [-h] [--print-contract-version] --descriptor DESCRIPTOR …

$ uvx --from "…" gen-eval --print-contract-version
1
```

Consequent changes in ACA, all landed:

- `pin.json` `entry_point` flipped `module` → `console-script` (task 7.3, complete).
- The vendored schemas are now **verbatim copies** of `gen_eval.contracts`, annotated
  with provenance. `scripts/generate_gen_eval_contract_schemas.py` derives nothing and
  refuses to write when upstream's `CONTRACT_VERSION` disagrees with the pin.
- The contract-version handshake is now a *reported* match rather than verified by
  construction. Confirmed the failure path fires: pinning `2` against a runner
  reporting `1` yields `BROKEN — runner reports contract version '1' but the pin is '2'`.
- The descriptor's three no-op `startup` commands are gone (UP-4).

The sections below are kept as the record of what was asked and why.

---

## UP-5 — The published report schema does not bound numeric ranges (open, low priority)

`eval-report.schema.json` is generated from `GenEvalReport`, whose numeric fields carry
no constraints, so the published schema is:

```json
"pass_rate":       {"title": "Pass Rate", "type": "number"},
"coverage_pct":    {"title": "Coverage Pct", "type": "number"},
"total_scenarios": {"title": "Total Scenarios", "type": "integer"}
```

A report with `pass_rate: 1.5`, `coverage_pct: -12`, or `total_scenarios: -1` is
schema-valid. ACA hand-assembled bounds before UP-2 landed and has now dropped them:
vendoring a locally-stricter copy would disagree with upstream's own drift test and
defeat the point of a shared contract. Range sanity moved to ACA's report validator,
and `tests/cli_gen_eval/test_contract.py` records the gap explicitly.

Suggested fix: annotate the model — `pass_rate: float = Field(ge=0.0, le=1.0)`,
`coverage_pct: float = Field(ge=0.0, le=100.0)`, counts `Field(ge=0)`. pydantic emits
`minimum`/`maximum` automatically, so the schema tightens with no generator change.

This is a **narrowing**, so it is a breaking contract change by the stated versioning
rule and would need `CONTRACT_VERSION` `2`. Given that no consumer can legitimately be
emitting out-of-range values, it may be worth folding into the next bump rather than
spending one on it alone. Entirely upstream's call — ACA is unaffected either way.

---

## UP-1 — The `gen-eval` console script is broken *(LANDED)*

`pyproject.toml` declared `gen-eval = "gen_eval.__main__:main"` while `main` was
`async def main(args: argparse.Namespace) -> int`. The generated launcher called it with
no arguments, so every invocation of the installed executable failed:

```
$ ~/.local/bin/gen-eval --help
TypeError: main() missing 1 required positional argument: 'args'
```

Only `python -m gen_eval` ever worked. Under a sibling-checkout model that is
routable-around; under a pinned tool install the console script *is* the published
interface, which is what made this blocking.

Fixed by renaming the async body to `run()` and adding a synchronous zero-arg `main()`
owning `parse_args()` + `asyncio.run()`.

## UP-2 — Publish the contract as versioned JSON Schema *(LANDED)*

Shipped as `src/gen_eval/contracts/` with `interface-descriptor.schema.json`,
`scenario.schema.json`, `eval-report.schema.json`, `VERSION`, a `load_schema()`
accessor, and `--print-contract-version`. `GenEvalReport` was promoted to a pydantic
`BaseModel`, so all three schemas are generated rather than hand-authored, and a drift
test keeps them honest.

This is what decouples schema conformance from runtime availability: ACA validates its
descriptor, scenarios, and received reports with nothing but `jsonschema`.

## UP-3 — Confirmations *(LANDED)*

`per_category`, `per_interface`, and `unevaluated_interfaces` are populated on every
run; ACA's report validator reads coverage from `unevaluated_interfaces` rather than
recomputing it.

## UP-4 — `startup` should be optional *(LANDED)*

`InterfaceDescriptor.startup` was required, so a CLI-only project had to supply a
`StartupConfig` it never used. Worse than three inert strings: the health check runs
even under `--no-services`, so the placeholder had to genuinely succeed.

`startup` now defaults to `None` and the orchestrator skips startup, health check,
seeding, and teardown when absent. Shipped in the same PR as UP-2, so it is a widening
at version 1 with no migration — every previously-valid descriptor still validates.

---

## Related, different repo: `agentic-assistant`

Still open, and now more tractable. `evaluation/run-gate.sh` reports success against a
complete gen-eval checkout:

```
$ EVAL_GATE_REQUIRE=0 bash evaluation/run-gate.sh
eval-gate: SKIP — gen-eval at .../packages/gen-eval is not runnable (stub checkout?)
EXIT=0
```

Two causes. Its runnability probe was the UP-1-broken console script, so a crash was
classified as an absent checkout — UP-1 fixes that proximate cause. But it also passes
`--scenario`, which is not a gen-eval argument (suites resolve from the descriptor's
`scenario_dirs`), so it will still fail once the probe starts succeeding. And the
underlying design flaw remains: "present but unrunnable" is indistinguishable from
"absent", so any future breakage returns to reporting green.

ACA's `evaluation/run-gate.sh` and `src/cli_gen_eval/runner.py` are a worked example of
the three-state alternative if that repo wants to borrow it.
