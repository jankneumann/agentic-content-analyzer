# Establish CLI gen-eval coverage

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `establish-cli-gen-eval-coverage`
> Effort: L
> Priority: 6
> Upstream prerequisites: `UPSTREAM.md`

## Summary

Add generator-evaluator (gen-eval) coverage for the `aca` CLI, split into two
layers with opposite distribution requirements:

- **The contract** — descriptor, scenarios, report schema, thresholds, and a
  validator — lives in this repository, pins a gen-eval contract version, and has
  no runtime dependency on gen-eval at all.
- **The runner** — the process that spawns the CLI and evaluates it — is acquired
  as a **pinned, versioned artifact** (`uv tool` / `uvx` from a git SHA now, an
  artifact index later). It is never resolved from a sibling checkout in any
  non-interactive context.

Read-only discovery and validation scenarios are categorized separately from
staging-only submission and terminal-workflow scenarios, and the mutation guard
reuses the target policy that `ri-04` established.

## Dependencies

- `ri-03` (reconciled OpenSpec inventory — actionable capability set)
- `ri-04` (`src/release_smoke` target policy and evidence-schema pattern)
- `UPSTREAM.md` UP-1 (working `gen-eval` console script) and UP-2 (published
  contract schemas), both in `agentic-coding-tools`

## Problem

The evaluation suite this roadmap item assumes has never existed here. `gen_eval`
is not importable, not declared in `pyproject.toml`, not vendored, and there is no
`make gen-eval` target. CLI behavior is measured only by mocked tests plus the
`ri-04` release-smoke gate, which covers deployed-artifact compatibility rather
than command-surface behavior.

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

### The problem with a sibling-checkout runner

An earlier revision of this proposal resolved gen-eval from
`../agentic-coding-tools/packages/gen-eval`, on the grounds that this avoided a
package dependency. That reasoning was wrong in an important way, and the
correction shapes the current design.

Avoiding a `[tool.uv.sources]` entry removes the *resolver-visible* dependency —
real, and necessary, because `uv lock` and `uv sync` must succeed for CI, Railway,
and Docker builds with no sibling repository present. But it does not remove the
dependency. It converts a declared, versioned dependency into an **undeclared,
unversioned filesystem adjacency**: not pinnable, not reproducible, invisible to
tooling, and unsatisfiable in a cloud harness, sandbox, VM, or container. The
advisory-skip mode that revision introduced is the symptom — an escape hatch
invented because the dependency is not reliably satisfiable. That is the same
mechanism that left `agentic-assistant`'s gate reporting green without ever
evaluating anything (`UPSTREAM.md`, final section).

### The decomposition

gen-eval's CLI transport spawns the command under test with
`asyncio.create_subprocess_exec`. The runner is therefore **required to be
co-located with the binary under test**, which rules out two otherwise attractive
options for this surface:

- A **central shared service** cannot drive CLI evaluation. It could host HTTP or
  MCP targets, or aggregate results, but not spawn this repository's CLI.
- A **container image** has the mirror problem: gen-eval inside a container cannot
  spawn the host's `aca`. Containerizing both is a heavier, different gate than
  this roadmap item.

What actually needs to be shared across repositories is the **contract**, not the
runtime. That is pure data and can be versioned and distributed independently,
which is what UP-2 delivers.

### Design decisions

**D1 — Contract layer in-repo, with zero dependency on gen-eval.**
The descriptor, scenario suites, report schema, threshold policy, and the
validator live in this repository and pin a gen-eval contract version. Validation
of all three artifact kinds uses the published JSON Schemas (UP-2) and requires no
gen-eval install. Consequences: schema conformance and threshold enforcement are
unconditionally checkable in CI even before a runner is resolved, and cross-repo
consistency comes from a shared schema version rather than a shared runtime.

**D2 — The runner is a pinned, versioned artifact, resolved by declared
precedence.** In order:

1. `ACA_GEN_EVAL_BIN` — explicit operator override.
2. A pinned `uv tool` / `uvx` install of a specific gen-eval version. Verified
   working today against a git SHA:
   `uv tool install "gen-eval @ git+https://github.com/jankneumann/agentic-coding-tools.git@<sha>#subdirectory=packages/gen-eval"`.
   The pin is recorded in a checked-in lock file, not passed ad hoc.
3. A sibling checkout — **developer convenience only**, never used when
   `ACA_GEN_EVAL_REQUIRE` is set, and therefore never in CI.

`uv tool` is what makes this a tool rather than a dependency: the runner installs
into an isolated environment, so `pyproject.toml` and `uv.lock` are untouched and
the runner's transitive deps cannot collide with this project's. Migrating to
`artifactory.rotkohl.ai` (or any index) later changes the resolution URL in the
lock file and nothing else — no redesign.

**D3 — No skip semantics in any enforcing context.**
The gate classifies the runner as `available`, `absent`, or `broken`:

| State | Meaning | Local, unset `ACA_GEN_EVAL_REQUIRE` | Enforcing (CI) |
|-------|---------|-------------------------------------|----------------|
| `available` | pinned version resolved and invocable | run suite | run suite |
| `absent` | no runner at any precedence level | advisory skip, exit 0 | hard fail |
| `broken` | resolved but invocation failed, or version mismatch | **hard fail** | hard fail |

CI resolves the pinned version explicitly, so `absent` cannot occur there. A crash
is never classified as an absence — the distinction that the precedent gate lacks.
Contract-layer checks (D1) run and enforce regardless of runner state.

**D4 — The runner is invoked through its published entry point.**
Once UP-1 lands, that is the `gen-eval` console script. Until then the gate
resolves `uvx --from gen-eval python -m gen_eval` as a documented interim form,
recorded in one place so it is a single-line change to retire. The gate asserts the
resolved runner's contract version matches the pinned one and treats a mismatch as
`broken`.

**D5 — Scenarios are discovered through the descriptor, not a CLI flag.**
gen-eval has no `--scenario` argument; suites resolve from the descriptor's
`scenario_dirs`, and subsets are chosen with `--categories`. The gate forwards
nothing the runner does not accept, so argument drift surfaces as `broken` rather
than as a skip.

**D6 — Single-source the production mutation guard on the `ri-04` target policy.**
`src/release_smoke/models.py` already defines
`TargetClass = Literal["production", "staging", "ephemeral", "local"]` plus the
`production_target_ids` / `production_origins` deny registries and validators that
reject a non-production target resolving to a production identity or origin.
Mutating categories consume that policy object, so exactly one place enforces
"production is not a mutation target".

**D7 — Validate the report before trusting the threshold.**
`--fail-threshold` alone is insufficient: a suite that discovers zero scenarios
yields a vacuous pass. The validator asserts schema validity against the pinned
report schema, minimum total and per-category scenario counts, and an empty
`unevaluated_interfaces`, and only then the pass rate. gen-eval already emits
`per_category`, `per_interface`, and `unevaluated_interfaces`, so coverage is read
from the report rather than recomputed.

**D8 — The command is `operations get`, not `operations status`.**
The roadmap acceptance outcome says "operation wait, status, retry, and cancel".
The implemented surface is `aca operations list|get|wait|retry|cancel`. Scenarios
target the real names; this records the reconciliation rather than adding an alias.

**D9 — CI runs `template-only` generation.**
Deterministic, no LLM spend, no vendor credentials. `cli-augmented` stays available
locally for scenario authoring.

### Scope

- `evaluation/contract/` — pinned gen-eval contract version, the three vendored
  JSON Schemas from UP-2, and the runner pin (version plus source URL).
- `evaluation/descriptors/aca-cli.yaml` — `InterfaceDescriptor` for the `aca` CLI.
- `evaluation/scenarios/` — categorized suites: `plumbing` (version, `--help`
  sweep), `discovery` (`capabilities`, `configured-sources`, `operations list`),
  `validation` (malformed arguments, bad cursors, JSON-purity of stdout),
  `workflow-submission` (staging-only, one per canonical `OperationType`),
  `operation-control` (staging-only, `get` / `wait` / `retry` / `cancel`).
- `evaluation/run-gate.sh` — runner resolution (D2), state classification (D3),
  invocation (D4/D5).
- `scripts/validate_gen_eval_contract.py` — D1 schema conformance for the
  descriptor and scenarios; runs with no runner present.
- `scripts/validate_gen_eval_report.py` — D7 report validation and threshold.
- `openspec/contracts/cli-gen-eval/` — the pinned schemas and fixtures as a
  durable contract domain.
- `make gen-eval` (full gate) and `make gen-eval-contract` (contract layer only).
- `.github/workflows/cli-gen-eval.yml` — pull-request job (contract layer plus
  read-only categories, enforcing) and `workflow_dispatch` staging job (mutating
  categories).
- `evaluation/README.md` and a `docs/decisions/` record for the D1/D2 policy.

### Out of scope

- The UPSTREAM.md work itself. Both items are `agentic-coding-tools` changes.
- Standing up `artifactory.rotkohl.ai` or any index. D2 is designed so adopting
  one is a lock-file edit; the git-SHA pin is the interim source.
- A standalone compiled runner, or a central evaluation service. Both remain
  plausible end-states; neither is required for a pinned-artifact runner, and the
  CLI subprocess constraint means a central service could never own this surface.
- gen-eval coverage for the HTTP, MCP, or frontend surfaces.
- Replacing any mocked CLI test. This adds a real-process boundary; it does not
  substitute for unit coverage.
- Provisioning a staging environment. Mutating categories consume the target
  policy and secrets `ri-04` established.

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
- No dependency, optional extra, or `[tool.uv.sources]` entry references gen-eval,
  and no enforcing context resolves it from a filesystem-adjacent checkout.
- The contract layer validates and enforces with no runner installed; a resolved
  runner whose contract version differs from the pin fails the gate.

## Risks

- **Upstream prerequisites.** UP-1 and UP-2 gate the clean form of D4 and D1
  respectively. Mitigated by the documented interim invocation and by vendoring
  the schemas at a pinned version, so ri-06 can land and then simplify.
- **Runner acquisition needs network and repo access.** A pinned git install
  requires reaching GitHub. Cloud harnesses without it fall to `absent`, which is
  fatal under enforcement — correct, but it must be visible. Mitigated by the
  contract layer remaining enforceable with no runner, so an unreachable runner
  never silently reduces coverage.
- **Vacuous green.** Addressed by D7's minimum-count and
  `unevaluated_interfaces` assertions.
- **Mutation escape.** Mitigated by D6 and by excluding mutating categories from
  the pull-request job by category rather than by convention.
- **Flake budget.** Real-process CLI startup against a deployed transport is
  slower and less deterministic than mocked tests. The pull-request job runs only
  the contract layer and read-only categories; the staging job is
  `workflow_dispatch`.

## Approval

Thin-runner-over-sibling-checkout was rejected by the operator on the grounds that
it still constitutes a dependency and cannot work in cloud harnesses, sandboxes,
or containers. Superseded by the two-layer design above: shared contract, pinned
artifact runner, with an artifact index as the intended eventual source.
