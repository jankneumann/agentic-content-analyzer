# Upstream handoff: `agentic-coding-tools` prerequisites for ri-06

> Consuming change: `establish-cli-gen-eval-coverage` (ACA roadmap item `ri-06`)
> Target repo: `jankneumann/agentic-coding-tools`, package `packages/gen-eval`

## Status

| Item | State | Blocks ACA? |
|---|---|---|
| UP-1 console script | **LANDED** at `600744a5` | no |
| UP-2 published JSON Schema | **LANDED** at `600744a5` | no |
| UP-3 coverage fields populated | **LANDED** at `600744a5` | no |
| UP-4 optional `startup` | **LANDED** at `600744a5` | no |
| UP-5 report schema numeric bounds | open, low | no — enforced in ACA's report validator |
| UP-6 runs silently evaluate less than the suite | **open, high** | no — worked around, and now detected |

UP-5's gap is closed on ACA's side: `src/cli_gen_eval/report.py` rejects `pass_rate`
outside `[0, 1]`, `coverage_pct` outside `[0, 100]`, and negative counts, with tests
asserting each of those documents is schema-valid first. Upstream tightening the model
would make those checks redundant rather than wrong.

UP-6 is now *detected* as well as worked around. The gate records the selection before
invoking the runner and compares it to the report, so a dropped scenario is a named,
non-zero-exit failure rather than a quiet reduction. Verified against the real runner:
pushing the suite past the tier cap yields `gen-eval: PASS (100.0% >= 95.0%)` from the
runner and exit 5 from the gate, naming all twenty scenarios that vanished. That does not
reduce UP-6's priority — every other consumer still gets the quiet reduction, and ACA
still pays the batching cost that fitting the cap requires.

UP-6 is the one worth acting on. It is not blocking, because ACA now resolves scenario
selection itself and asserts the expected count, but the workaround cost genuine
reporting granularity and the underlying defect misleads any consumer that trusts
`--categories`.

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

## UP-6 — A run silently evaluates less than the suite it was given (open, HIGH priority)

Found while authoring ACA's read-only suite in Phase 3. Four independent mechanisms
reduce what a run covers, none of them reported, all of them exiting 0. The first is a
correctness bug; the rest are unreachable configuration.

### 6a. `--categories` does nothing

`__main__.py` passes `args.categories` into `GenEvalConfig(categories=...)` and no code
reads it again. The only path into `TemplateGenerator._filter`'s `focus_areas` is
`feedback.suggested_focus`, which is `None` on the first iteration, and `max_iterations`
defaults to 1. So the filter is unreachable in a default run.

Verified against ACA's suite at ref `600744a5`:

```
$ gen-eval --descriptor evaluation/descriptors/aca-cli.yaml --categories discovery …
total_scenarios: 16 — {'discovery': 3, 'plumbing': 9, 'validation': 4}
```

Three scenarios were requested; sixteen ran, spanning every category.

This is the highest-severity item because the flag's *stated* purpose is a safety
boundary. ACA's design keeps mutating scenarios — ones that submit durable work — in the
same `scenario_dirs` tree and relies on selection to hold them back. Had we trusted the
flag, every `make gen-eval` would have submitted real workflow operations against
whatever database was configured. We now resolve the selection ourselves and synthesize a
per-run descriptor (`src/cli_gen_eval/selection.py`), so ACA is safe either way, but any
other consumer reading the `--help` text would not be.

Suggested fix: pass `self.config.categories` as `focus_areas` when no feedback focus
exists, so the existing `_filter` logic applies. Worth a regression test asserting that
`--categories X` evaluates only category X, since nothing currently covers it.

### 6b. `max_scenarios_per_iteration` is not settable, and the tier split makes it smaller
than it looks

`GenEvalConfig.max_scenarios_per_iteration` defaults to 50 and is absent from the
argparse surface, so a CLI consumer cannot raise it. `TemplateGenerator.generate` returns
`scenarios[:count]` with no warning when it truncates.

The bigger surprise is `Orchestrator._prioritize_scenarios`, which then buckets what
survives:

```python
max_tier1 = int(max_total * 0.40)   # interfaces in --changed-features-ref
max_tier2 = int(max_total * 0.35)   # priority <= 1
max_tier3 = max_total - max_tier1 - max_tier2
result = tier1[:max_tier1] + tier2[:max_tier2] + tier3[:max_tier3]
```

Without `--changed-features-ref`, `tier1` is empty and its 20 slots are simply unspent —
they do not reflow. A run's real capacity is 17 + 13 = **30 of a nominal 50**, and only 13
of those may be non-critical.

ACA hit this concretely: a 39-scenario suite reported

```
total_scenarios: 21
pass_rate: 1.0
gen-eval: PASS (100.0% >= 95.0%)
```

Eighteen scenarios were dropped, seventeen declared interfaces went unevaluated, and the
run exited 0. Restructuring the suite to fit cost real coverage granularity — commands are
now batched several per scenario, so a failing one masks the rest of its batch, which is a
worse report than one scenario per command would give.

Suggested fix: expose `--max-scenarios` and let unused tier allocation reflow into the
following tiers (`tier3` cap becomes `max_total - len(tier1_taken) - len(tier2_taken)`).
Both are small and neither changes behaviour for a run that fits today.

### 6c. Dropped work is logged, never reported

`_load_templates`, `_expand_parameters`, and `_validate` each `logger.warning` and
continue on unparseable YAML, a Jinja2 render error, and a model-validation failure
respectively. A consumer parsing the JSON report cannot tell any of them happened.

Suggested fix: count them and surface the totals on the report — `templates_loaded`,
`templates_rejected`, `expansions_dropped`, `scenarios_truncated`. A non-zero
`scenarios_truncated` in particular should probably be fatal by default, since it means
the reported pass rate covers an unnamed subset.

### 6d. `GenEvalConfig.from_yaml` is unreachable from the CLI

The classmethod exists and would solve 6b generically, but `__main__.py` only ever builds
the config from argparse. A `--config` flag would expose every field at once.

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
