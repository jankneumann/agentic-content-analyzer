# Establish CLI gen-eval coverage

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `establish-cli-gen-eval-coverage`
> Effort: L
> Priority: 6

## Summary

Add generator-evaluator (gen-eval) coverage for the `aca` CLI: a checked-in
interface descriptor, a categorized scenario suite, a `make gen-eval` target, a
report schema with threshold enforcement, and a CI workflow. The gen-eval
framework itself is consumed as an **external tool**, never as a package
dependency. Read-only discovery and validation scenarios are categorized
separately from staging-only submission and terminal-workflow scenarios, and the
mutation guard reuses the target policy that `ri-04` already established.

## Dependencies

- `ri-03` (reconciled OpenSpec inventory — actionable capability set)
- `ri-04` (`src/release_smoke` target policy and evidence-schema pattern)

## Problem

The evaluation suite this roadmap item assumes has never existed in this
repository. `gen_eval` is not importable, not declared in `pyproject.toml`, not
vendored, and there is no `make gen-eval` target. CLI behavior is therefore
measured only by mocked tests plus the `ri-04` release-smoke gate, which covers
deployed-artifact compatibility rather than command-surface behavior.

Two failure modes this leaves open:

- **Command-surface regressions.** 28 Typer sub-apps plus top-level
  `capabilities` / `configured-sources`. `ri-01` fixed production discovery
  commands that mocked tests reported as healthy; nothing today would catch the
  next instance of that class.
- **Operation-control regressions.** `aca operations list|get|wait|retry|cancel`
  and the eight canonical `OperationType` submissions are the entire external
  workflow contract. No test executes them as a real process against a real
  transport.

## Approach

Adopt the thin-runner topology proven in `agentic-assistant`: check in the
descriptor, scenarios, and gate script; resolve the framework from a sibling
checkout at run time. Do **not** create an inter-repo package dependency.

### Design decisions

**D1 — gen-eval is a consumer of this repo, not a dependency.**
No `[tool.uv.sources]` path entry, no vendored copy. `agentic-assistant`
originally took the path-dependency route and it broke `uv lock` / `uv sync` on
standalone clones; the dependency was removed under its ADR 0006. ACA's lockfile
must stay resolvable for CI, Railway builds, and Docker without any sibling
repository present. The framework is located via `ACA_GEN_EVAL_PROJECT`,
defaulting to `../agentic-coding-tools/packages/gen-eval`.

**D2 — invoke `python -m gen_eval`, never the `gen-eval` console script.**
The package declares `gen-eval = "gen_eval.__main__:main"`, but `main` is
`async def main(args: argparse.Namespace) -> int`. The console script calls it
with no arguments and dies with
`TypeError: main() missing 1 required positional argument: 'args'`. Only the
`if __name__ == "__main__"` path wires `parse_args()` and `asyncio.run()`.
Every invocation and every probe in this change uses the module form. An
upstream fix is desirable but is not a precondition for this change, and this
change must not regress if the console script starts working.

**D3 — the runnability probe is three-state, and a crash is never "absent".**
The gate classifies the framework as `available`, `absent`, or `broken`:

| State | Meaning | Local | CI (`ACA_GEN_EVAL_REQUIRE=1`) |
|-------|---------|-------|-------------------------------|
| `available` | module imports and `--help` parses | run suite | run suite |
| `absent` | project directory or module missing | advisory skip, exit 0 | hard fail |
| `broken` | present but invocation failed | **hard fail** | hard fail |

This exists because the precedent gate conflates `broken` with `absent`:
its probe is the D2-broken console script, so it reports
`SKIP — not runnable (stub checkout?)` and exits 0 against a complete checkout.
A gate whose failure mode is indistinguishable from its absence mode reports
green forever. CI additionally pins the sibling checkout to a recorded ref so
"absent" cannot occur silently there.

**D4 — scenarios are discovered through the descriptor, not a CLI flag.**
gen-eval's argparse has no `--scenario` option; suites are resolved from the
descriptor's `scenario_dirs`, and subsets are chosen with `--categories`. The
gate exposes category selection and forwards nothing that the framework does not
accept, so an argument-shape drift surfaces as `broken` rather than as a skip.

**D5 — reuse the `ri-04` target policy for the production guard.**
`src/release_smoke/models.py` already defines
`TargetClass = Literal["production", "staging", "ephemeral", "local"]` plus the
`production_target_ids` / `production_origins` deny registries and the
validators that reject a non-production target resolving to a production
identity or origin. Mutating gen-eval scenarios consume that same policy object
rather than a second target model, so there is exactly one place where
"production is not a mutation target" is enforced.

**D6 — the threshold is enforced by the framework *and* validated repo-side.**
`--fail-threshold` alone is insufficient: a suite that discovers zero scenarios
produces a vacuous pass. A repo-owned validator asserts the report is
schema-valid, that scenario count and per-category counts meet declared minima,
that every descriptor-declared interface appears in `interfaces_tested`, and only
then that the pass rate meets the documented threshold.

**D7 — the command is `operations get`, not `operations status`.**
The roadmap acceptance outcome says "operation wait, status, retry, and cancel".
The implemented surface is `aca operations list|get|wait|retry|cancel`. Scenarios
target the real command names; this proposal records the reconciliation rather
than adding an alias.

**D8 — CI runs `template-only` mode.**
Deterministic, no LLM spend, no vendor credentials. `cli-augmented` remains
available locally for scenario authoring.

### Scope

- `evaluation/descriptors/aca-cli.yaml` — `InterfaceDescriptor` for the `aca`
  CLI service, declaring the command surface under evaluation.
- `evaluation/scenarios/` — categorized suites: `plumbing` (version, `--help`
  sweep), `discovery` (`capabilities`, `configured-sources`, `operations list`),
  `validation` (malformed arguments, bad cursors, JSON-purity of stdout),
  `workflow-submission` (staging-only, one per canonical `OperationType`),
  `operation-control` (staging-only, `get` / `wait` / `retry` / `cancel`).
- `evaluation/run-gate.sh` — the D2/D3/D4 runner.
- `make gen-eval` — the documented entry point, forwarding `CATEGORIES`.
- `openspec/contracts/cli-gen-eval/gen-eval-report.schema.json` plus
  `scripts/validate_gen_eval_report.py` — the D6 validator.
- `.github/workflows/cli-gen-eval.yml` — pull-request job for non-mutating
  categories; `workflow_dispatch` staging job for mutating categories.
- `evaluation/README.md` and a `docs/decisions/` record stating the D1 policy for
  this repository.

### Out of scope

- Fixing the upstream `gen-eval` console-script entry point (tracked in
  `agentic-coding-tools`; D2 makes this change independent of it).
- Adding gen-eval coverage for the HTTP, MCP, or frontend surfaces. The
  descriptor schema supports them; this change is CLI-only per the roadmap item.
- Replacing any existing mocked CLI test. gen-eval is an additional real-process
  boundary, not a substitute for unit coverage.
- Provisioning a staging environment. Mutating categories consume the target
  policy and secrets that `ri-04` already established.

## Acceptance Outcomes

- `make gen-eval` executes the checked-in descriptor and scenario suite and emits
  a schema-valid report.
- Scenarios cover version and help, discovery, validation, every canonical
  workflow operation type, and the operation `wait`, `get`, `retry`, and `cancel`
  commands.
- CI enforces a documented pass-rate threshold and publishes failures grouped by
  command and category.
- Mutating scenarios require an explicit staging or ephemeral target and reject
  production by default.
- A missing framework checkout skips advisorily in local runs and hard-fails in
  CI; a present-but-unrunnable framework hard-fails everywhere.

## Risks

- **Upstream drift.** gen-eval is externally owned; its argparse surface or
  descriptor schema can change under us. Mitigated by D3 (`broken` is fatal, not
  a skip) and by CI pinning the sibling checkout to a recorded ref, so drift
  appears as a red gate naming the failing invocation.
- **Vacuous green.** Addressed by D6's minimum-count and interface-coverage
  assertions.
- **Mutation escape.** A staging-targeted scenario reaching production. Mitigated
  by D5: no second target model, and mutating categories are excluded from the
  pull-request job by category, not by convention.
- **Flake budget.** Real-process CLI startup against a deployed transport is
  slower and less deterministic than mocked tests. The pull-request job runs
  only non-mutating categories; the staging job is `workflow_dispatch`.

## Approval

Approved for implementation planning as roadmap item `ri-06`. Thin-runner
topology confirmed by the operator, consistent with `agentic-assistant` ADR 0006.
