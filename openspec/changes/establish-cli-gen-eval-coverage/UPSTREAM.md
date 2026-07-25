# Upstream handoff: `agentic-coding-tools` prerequisites for ri-06

> Consuming change: `establish-cli-gen-eval-coverage` (ACA roadmap item `ri-06`)
> Target repo: `jankneumann/agentic-coding-tools`, package `packages/gen-eval`
> Status at time of writing: gen-eval `0.1.0`, `uv_build` backend, 5 core deps

ri-06 consumes gen-eval as a **versioned artifact**, not a sibling checkout. Two
gaps block that. Both are small and independently landable; neither depends on
ACA.

Verification baseline used below — installing from a pinned SHA already works:

```bash
uv tool install "gen-eval @ git+https://github.com/jankneumann/agentic-coding-tools.git@<sha>#subdirectory=packages/gen-eval"
# → Installed 1 executable: gen-eval
```

---

## UP-1 — The `gen-eval` console script is broken (blocker)

`pyproject.toml` declares:

```toml
[project.scripts]
gen-eval = "gen_eval.__main__:main"
```

but `main` is `async def main(args: argparse.Namespace) -> int`. The generated
launcher calls `main()` with no arguments, so **every** invocation of the
installed executable fails:

```
$ ~/.local/bin/gen-eval --help
TypeError: main() missing 1 required positional argument: 'args'
```

Only the `if __name__ == "__main__"` block at the bottom of `__main__.py` wires
`parse_args()` and `asyncio.run()` — so `python -m gen_eval` works and the
console script never has. The pyproject comment already states the intent
("`gen-eval` becomes a thin convenience over `python -m gen_eval`"); the wiring
just never landed.

### Why this blocks ri-06

Under a sibling-checkout model this is routable-around with `python -m gen_eval`.
Under a tool install the console script **is** the published interface.
`uvx --from gen-eval python -m gen_eval` does still work, but shipping a
distribution whose advertised entry point is broken and whose working entry point
is undocumented is not a contract worth building a CI gate on.

### Fix

Rename the async body and add a sync `main()` that the console script can call.
In `packages/gen-eval/src/gen_eval/__main__.py`:

```python
async def run(args: argparse.Namespace) -> int:      # was: async def main(args)
    ...unchanged body...


def main() -> int:
    """Console-script entry point (`gen-eval`)."""
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
```

Keep `run()` public — `mcp_service.py` / `coordinator.py` may invoke the async
body directly; check callers before renaming.

### Tests

- `gen-eval --help` exits 0 and prints usage.
- `gen-eval` with no `--descriptor` exits 2 (argparse) — regression guard on
  `parse_args()` still being reached.
- `--openspec-change` with an invalid change-id still exits 64 (`EX_USAGE`); the
  custom `parser.error` override must survive the refactor.
- An installed-artifact test: build a wheel, install it into a throwaway venv,
  and assert the console script runs. This is the check that would have caught
  the defect — the existing suite only ever exercises the module path.

---

## UP-2 — Publish the contract as versioned JSON Schema

ri-06 (and any other consumer) needs to validate its own descriptor, scenarios,
and reports **without installing gen-eval**. Today those schemas exist only as
Python models inside the package, so schema conformance and runtime availability
are coupled for no reason.

### What to publish

Three JSON Schema documents plus a contract version, under
`packages/gen-eval/src/gen_eval/contracts/` (shipped in the wheel *and*
readable straight from the repo/raw URL):

| File | Source | Method |
|---|---|---|
| `interface-descriptor.schema.json` | `descriptor.InterfaceDescriptor` | `model_json_schema()` — verified: 8 properties, 9 `$defs` |
| `scenario.schema.json` | `models.Scenario` | `model_json_schema()` — verified: 12 properties, 6 `$defs` |
| `eval-report.schema.json` | `reports.GenEvalReport` | **hand-authored** — see below |
| `VERSION` | — | contract version, bumped on any breaking schema change |

`GenEvalReport` is a plain `@dataclass`, not a pydantic model, so it cannot
self-emit. Two options, in order of preference:

1. **Promote `GenEvalReport` to `pydantic.BaseModel`.** Its fields are already
   plain types plus `list[ScenarioVerdict]` (pydantic) and
   `dict[str, VisibilityBreakdown]`. This makes all three schemas generated and
   drift-proof. `generate_json_report()` then collapses to
   `report.model_dump_json(indent=2)` — note the current hand-built dict omits
   `per_visibility` unless non-empty, so preserve that or accept the shape change
   as a contract bump.
2. Hand-author `eval-report.schema.json` and add a conformance test asserting
   `json.loads(generate_json_report(fixture))` validates against it. Cheaper now,
   but it can drift.

### Generator + drift guard

- `scripts/generate_contract_schemas.py` writes all three files.
- A test regenerates into a temp dir and diffs against the checked-in copies,
  failing on drift. Same pattern as ACA's `make workflow-contracts-check`.
- Expose the version for runtime assertions:
  `gen-eval --print-contract-version` (exit 0, one line on stdout).

### Consumer contract this enables

A repo pins `contract_version: "1"` and validates its descriptor, scenarios, and
emitted reports against the pinned schemas using nothing but the stdlib plus a
JSON Schema validator. Cross-repo consistency without cross-repo runtime
coupling — which is the whole point.

---

## UP-3 — Confirm what ri-06 relies on (no change expected)

Please sanity-check these, since ri-06's report validator is built on them:

- `GenEvalReport.per_category` and `.per_interface` are populated on every run,
  including runs where all scenarios pass.
- `GenEvalReport.unevaluated_interfaces` lists descriptor-declared interfaces
  that no scenario touched. ri-06 asserts this is empty rather than recomputing
  coverage, so its semantics matter.
- `total_scenarios == 0` behaviour: `pass_rate` is `0.0` when `total == 0` in
  `ScenarioSummary`, but `GenEvalReport.pass_rate` is a plain field. Confirm a
  zero-scenario run cannot report `pass_rate == 1.0` and exit 0. ri-06 guards
  this independently, but a framework-level guarantee is better.

---

## Related, different repo: `agentic-assistant`

Not part of this handoff, but found while investigating and worth filing there:
`evaluation/run-gate.sh` reports success against a complete gen-eval checkout.

```
$ EVAL_GATE_REQUIRE=0 bash evaluation/run-gate.sh
eval-gate: SKIP — gen-eval at .../packages/gen-eval is not runnable (stub checkout?)
EXIT=0
```

Two causes: its runnability probe is the UP-1-broken console script, so a crash
is classified as an absent checkout; and it passes `--scenario`, which is not a
gen-eval argument (suites resolve from the descriptor's `scenario_dirs`). So the
gate has never evaluated anything. UP-1 fixes the probe's proximate cause, but
the gate also needs the argument fix and a state where "present but unrunnable"
is fatal rather than skipped.
