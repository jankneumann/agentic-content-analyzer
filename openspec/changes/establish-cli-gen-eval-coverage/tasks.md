# Tasks: Establish CLI gen-eval coverage

> Change ID: `establish-cli-gen-eval-coverage`
> Selected approach: repository-local evaluation contract plus a pinned,
> versioned runner artifact — no filesystem-adjacent resolution in any
> enforcing context
> Upstream prerequisites: `UPSTREAM.md` (UP-1, UP-2)

## Status

- [x] Planning
- [ ] Implementation
- [ ] Testing
- [ ] Review
- [ ] Done

## Phase 1 — Contract layer, runner-independent (`wp-gen-eval-contract`)

Deliverable: schema conformance and enforcement that work with no runner
installed. This phase must be independently green before Phase 2 begins.

- [x] 1.1 Vendor the UP-2 schemas into `openspec/contracts/cli-gen-eval/` at a
  pinned contract version, with the pin declared in `evaluation/contract/pin.json`.
  UP-2 has not landed, so they are generated from the pinned runner source via
  `scripts/generate_gen_eval_contract_schemas.py`, which reaches the ref through
  `uvx` and records provenance annotations on every schema. **(M)**
  **Spec scenarios:** The pinned contract version is declared
  **Design decisions:** D1
  **Deviation:** the pin is `evaluation/contract/pin.json`, not a plain-text
  `VERSION` file — it must carry the runner source, subdirectory, ref, and
  generating ref alongside the version, which a one-line file cannot express.
- [x] 1.2 Write validator tests: schema-invalid descriptor, schema-invalid
  scenario, and the no-runner-present case asserting a definite pass or fail
  rather than a skip. **(M)**
  **Spec scenarios:** Contract validation with no runner installed
  **Design decisions:** D1
  **Dependencies:** 1.1
  **Landed as:** `tests/cli_gen_eval/test_contract.py`, 32 tests — also covers
  three-way contract-version agreement (pin / module constant / schema
  annotation), durable-vs-runtime byte parity, a static AST check that no
  contract-layer module imports `gen_eval`, and the zero-scenario boundary
  between schema validity and Phase 4 sufficiency.
- [x] 1.3 Implement `scripts/validate_gen_eval_contract.py` — descriptor and
  scenario conformance against the pinned schemas, stdlib plus a JSON Schema
  validator only, no gen-eval import. **(M)**
  **Spec scenarios:** Descriptor and scenarios are schema-valid
  **Dependencies:** 1.2
- [x] 1.4 Add `make gen-eval-contract` and a test asserting no dependency,
  optional extra, or package source entry references gen-eval. **(S)**
  **Spec scenarios:** Dependency resolution without a runner
  **Design decisions:** D1
  **Dependencies:** 1.3
  **Landed as:** `make gen-eval-contract`, plus
  `gen-eval-contract-schemas{,-check}` for regeneration and drift. New
  `gen-eval` optional extra, deliberately jsonschema-only so the contract layer
  installs without a browser. The hygiene test compares PEP 508 distribution
  names rather than substrings, because the extra is itself named `gen-eval`.
- [x] 1.5 Add the Phase 1 descriptor skeleton `evaluation/descriptors/aca-cli.yaml`
  so the contract layer is demonstrable end-to-end and `make gen-eval-contract` is
  green. **(S)**
  **Deviation:** unplanned, and partially overlaps 3.1. Added because leaving a
  documented Make target failing is worse than a skeleton, and because the
  alternative — teaching the validator to tolerate an absent descriptor — would
  reintroduce exactly the skip semantics D3 removes. `commands` and
  `scenario_dirs` are empty; 3.1 and 3.2 populate them.

## Phase 2 — Runner acquisition and state classification (`wp-gen-eval-runner`)

- [x] 2.1 Write resolution-precedence tests: explicit override wins; pinned
  artifact next; adjacent checkout used only when enforcement is not requested and
  never otherwise. **(M)**
  **Spec scenarios:** Runner resolution precedence / An adjacent checkout under
  enforcement
  **Design decisions:** D2
- [x] 2.2 Write three-state classification tests: `absent` (advisory skip locally,
  fatal under enforcement), `broken` (fatal always), `available`. Assert a non-zero
  probe exit is never classified as absent, and that contract checks ran in every
  case. **(M)**
  **Spec scenarios:** Runner availability is classified in three states / all
  **Design decisions:** D3
  **Landed as:** `tests/cli_gen_eval/test_runner.py`, 36 tests. Includes a stub
  reproducing the real upstream failure (present, executable, exits 1 with the
  `TypeError`) and asserts it classifies `broken` with exit 3 under both
  enforcement settings — plus that a broken high-precedence candidate does not
  fall through to a working lower-precedence one, which would hide a
  misconfigured override.
- [x] 2.3 Record the pinned runner version and source, plus a test asserting the
  gate never installs an unpinned version. **(M)**
  **Spec scenarios:** Runner resolution precedence
  **Design decisions:** D2
  **Deviation:** the pin was added to the existing `evaluation/contract/pin.json`
  rather than a separate `evaluation/contract/runner.lock`. A second file would
  have duplicated `runner_source`, `runner_subdirectory`, and `runner_ref`, and
  two files that must agree is precisely the drift hazard this change argues
  against elsewhere.
- [x] 2.4 Implement the gate's resolution and classification. Installation via
  `uv tool` / `uvx` into an isolated environment; assert the project manifest and
  lock file are unmodified afterwards. **(L)**
  **Spec scenarios:** The runner is isolated from project dependencies
  **Design decisions:** D2, D3
  **Deviation:** the logic lives in `src/cli_gen_eval/runner.py` and
  `scripts/run_gen_eval_gate.py`; `evaluation/run-gate.sh` is a thin wrapper over
  them. Resolution and three-state classification are subtle enough to deserve
  unit tests and type checking, which shell cannot provide. The shell script
  remains the stable command CI, Make, and operators call.
- [x] 2.5 Record the runner entry point in one declared location, with the interim
  module form documented as such so retiring it after UP-1 is a single-line change.
  **(S)**
  **Spec scenarios:** The runner is invoked through its published entry point
  **Design decisions:** D4
  **Landed as:** `entry_point` in `pin.json`, consumed only by
  `runner._entry_argv`. Task 7.3 is now literally flipping `"module"` to
  `"console-script"`; a test guards against flipping it by accident.
- [x] 2.6 Implement and test the contract-version handshake: resolved runner
  version compared against the pin, mismatch classified `broken` and reporting both
  versions. **(M)**
  **Spec scenarios:** Runner contract version mismatch
  **Design decisions:** D2, D4
  **Note:** three outcomes, not two. `--print-contract-version` does not exist
  upstream yet (UP-2), so a pinned candidate is verified *by construction* from
  its ref; anything else is `unverifiable`, tolerated locally and refused under
  enforcement so CI cannot evaluate against an unknown runner.
- [x] 2.7 Write `evaluation/README.md` and a `docs/decisions/` record for D1/D2:
  why gen-eval is a pinned artifact and not a dependency or an adjacent checkout,
  and how to migrate the pin to an artifact index. **(S)**
  **Landed as:** `evaluation/README.md` and
  `docs/decisions/0001-gen-eval-is-a-pinned-artifact.md` — the first ADR in this
  repository; format mirrors `agentic-assistant`'s `docs/decisions/`.

## Phase 3 — Descriptor and read-only scenarios (`wp-gen-eval-readonly`)

- [ ] 3.1 Author `evaluation/descriptors/aca-cli.yaml` declaring the `aca` CLI
  service, its registered command groups, and `scenario_dirs`. Validate it through
  the Phase 1 contract validator. **(M)**
  **Spec scenarios:** Descriptor and scenarios are schema-valid
  **Design decisions:** D5
  **Dependencies:** 1.3
- [ ] 3.2 Add a drift test asserting every command group registered on the CLI
  application appears in the descriptor or in a reviewed exclusion set with a
  stated reason. **(M)**
  **Spec scenarios:** The descriptor tracks the registered command surface
  **Dependencies:** 3.1
- [ ] 3.3 Author the `plumbing` category: version output and a `--help` sweep
  across the top-level application and each registered command group. **(M)**
  **Spec scenarios:** Plumbing and discovery coverage
  **Dependencies:** 3.1
- [ ] 3.4 Author the `discovery` category: capability discovery, configured-source
  listing, and durable operation listing, including the no-cursor case `ri-01`
  repaired. Assert single-JSON-document stdout purity. **(M)**
  **Spec scenarios:** Plumbing and discovery coverage
  **Dependencies:** 3.1
- [ ] 3.5 Author the `validation` category: malformed arguments, invalid pagination
  cursors, and omission of absent optional query values. **(M)**
  **Spec scenarios:** Validation coverage
  **Dependencies:** 3.1

## Phase 4 — Report validation and threshold (`wp-gen-eval-report`)

- [ ] 4.1 Write validator tests: schema-invalid report, zero-scenario report,
  below-minimum per-category counts, a non-empty `unevaluated_interfaces`, and pass
  rate below threshold. **(M)**
  **Spec scenarios:** A vacuous run is rejected
  **Design decisions:** D7
  **Dependencies:** 1.1
- [ ] 4.2 Add report fixtures under `tests/fixtures/`, following the
  `release-smoke` durable contract layout. **(M)**
  **Spec scenarios:** `make gen-eval` emits a validated report
  **Dependencies:** 4.1
- [ ] 4.3 Implement `scripts/validate_gen_eval_report.py`: schema validation,
  minimum total and per-category counts, empty `unevaluated_interfaces`, then
  threshold. Read coverage from the report rather than recomputing it. **(M)**
  **Spec scenarios:** A vacuous run is rejected
  **Design decisions:** D7
  **Dependencies:** 4.1, 4.2
- [ ] 4.4 Add the `gen-eval` Make target — contract layer, then gate, then report
  validation — forwarding `CATEGORIES`. Document the threshold and minimum counts.
  **(S)**
  **Spec scenarios:** `make gen-eval` emits a validated report
  **Dependencies:** 2.4, 4.3
- [ ] 4.5 Add a grouping test asserting the emitted report groups results by command
  and category. **(S)**
  **Spec scenarios:** `make gen-eval` emits a validated report
  **Dependencies:** 4.2

## Phase 5 — Mutation guard and staging scenarios (`wp-gen-eval-mutation`)

- [ ] 5.1 Write guard tests: mutating category with no target policy, with a
  production target class, and with a non-production target whose identity or origin
  resolves to a registered production identity or origin. Assert no workflow is
  submitted in any rejection path. **(M)**
  **Spec scenarios:** Mutating scenarios require a non-production target / all
  **Design decisions:** D6
- [ ] 5.2 Implement the guard by consuming `src/release_smoke` target-policy models
  and their production deny registries. Add a test asserting no independent target
  classification is introduced. **(M)**
  **Spec scenarios:** The production guard is single-sourced
  **Design decisions:** D6
  **Dependencies:** 5.1
- [ ] 5.3 Author the `workflow-submission` category covering every canonical
  workflow operation type, asserting each returns a durable operation handle. **(L)**
  **Spec scenarios:** Canonical workflow submission coverage
  **Dependencies:** 3.1, 5.2
- [ ] 5.4 Author the `operation-control` category covering the operation retrieval,
  wait, retry, and cancel commands, observing at least one operation through a
  terminal state. **(L)**
  **Spec scenarios:** Operation control coverage
  **Design decisions:** D8
  **Dependencies:** 5.3
- [ ] 5.5 Add a test asserting the default category selection includes the contract
  layer and read-only categories and excludes every mutating category. **(S)**
  **Spec scenarios:** The default pull-request run excludes mutating categories
  **Dependencies:** 5.2

## Phase 6 — CI wiring (`wp-gen-eval-ci`)

- [ ] 6.1 Add `.github/workflows/cli-gen-eval.yml`: a pull-request job running the
  contract layer plus read-only categories with enforcement requested and
  template-only generation, and a `workflow_dispatch` staging job for mutating
  categories using the `release-smoke-staging` environment pattern. **(L)**
  **Spec scenarios:** Continuous integration enforces without a skip path /
  Continuous integration selects deterministic generation
  **Design decisions:** D3, D9
  **Dependencies:** 4.4, 5.5
- [ ] 6.2 Install the runner in CI from the checked-in pin only — no adjacent
  checkout, no unpinned resolution — and assert the contract layer runs and enforces
  even when runner installation fails. **(M)**
  **Spec scenarios:** No runner is resolvable under enforcement / Contract
  validation with no runner installed
  **Design decisions:** D2, D3
  **Dependencies:** 6.1
- [ ] 6.3 Upload the validated report and failure grouping as a retained artifact.
  **(S)**
  **Spec scenarios:** Continuous integration enforces without a skip path
  **Dependencies:** 6.1
- [ ] 6.4 Add a workflow-configuration test in `tests/config/` asserting the
  pull-request job selects only the contract layer and read-only categories, sets
  enforcement, and does not permit mutations — following
  `tests/config/test_release_smoke_workflow.py`. **(M)**
  **Spec scenarios:** The default pull-request run excludes mutating categories
  **Dependencies:** 6.1

## Phase 7 — Documentation and close-out (`wp-gen-eval-docs`)

- [ ] 7.1 Add a Testing-guide section: how to run the suite, how to author a
  scenario, category semantics, the three runner states, and how to bump the runner
  pin. **(S)**
  **Dependencies:** 4.4
- [ ] 7.2 Record the `operations get` versus `operations status` naming
  reconciliation, and link `UPSTREAM.md` to the filed `agentic-coding-tools` issues.
  **(S)**
  **Design decisions:** D4, D8
- [x] 7.3 After UP-1 lands, retire the interim entry-point form at its single
  declared location and drop the interim note from the README. **(S)**
  **Spec scenarios:** The runner is invoked through its published entry point
  **Dependencies:** 2.5, UP-1
  **Landed as:** UP-1 through UP-4 all shipped at runner ref `600744a5`. The pin
  moved there, `entry_point` flipped to `console-script`, the vendored schemas
  became verbatim copies of the published `gen_eval.contracts` (so the generator
  derives nothing), the descriptor's no-op `startup` block was removed, and the
  version handshake is now a reported match rather than verified by construction.
  Raised UP-5 upstream: the published report schema carries no numeric bounds, so
  range sanity stays with the report validator rather than being tightened in our
  vendored copy.
- [ ] 7.4 Run `openspec validate establish-cli-gen-eval-coverage --strict`, the full
  test suite, lint, and type checks. **(S)**
  **Dependencies:** all
