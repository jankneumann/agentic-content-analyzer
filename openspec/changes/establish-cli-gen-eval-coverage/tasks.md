# Tasks: Establish CLI gen-eval coverage

> Change ID: `establish-cli-gen-eval-coverage`
> Selected approach: thin runner over an externally owned gen-eval checkout,
> with a three-state runnability probe and a repo-owned report validator

## Status

- [x] Planning
- [ ] Implementation
- [ ] Testing
- [ ] Review
- [ ] Done

## Phase 1 — Framework boundary (`wp-gen-eval-boundary`)

- [ ] 1.1 Write tests for the three-state runnability probe: `available`,
  `absent` (advisory skip locally, fatal under `ACA_GEN_EVAL_REQUIRE`), and
  `broken` (fatal everywhere). Assert a non-zero probe exit is never classified
  as absent. **(M)**
  **Spec scenarios:** Framework availability is classified in three states / all
  **Design decisions:** D3
- [ ] 1.2 Implement `evaluation/run-gate.sh` invoking the framework as
  `python -m gen_eval` via `uv run --project "$ACA_GEN_EVAL_PROJECT"`, with the
  documented default sibling path. **(M)**
  **Spec scenarios:** Framework invocation form / Framework location is
  configurable
  **Design decisions:** D1, D2
  **Dependencies:** 1.1
- [ ] 1.3 Add a test asserting no dependency, optional extra, or
  `[tool.uv.sources]` entry references the gen-eval package, and that the gate
  never invokes the `gen-eval` console script. **(S)**
  **Spec scenarios:** Dependency resolution without a framework checkout
  **Design decisions:** D1, D2
- [ ] 1.4 Record the consumption policy in `docs/decisions/` for this repository,
  citing the `agentic-assistant` ADR 0006 precedent and the broken console-script
  entry point, and write `evaluation/README.md`. **(S)**
  **Dependencies:** 1.2

## Phase 2 — Descriptor and read-only scenarios (`wp-gen-eval-readonly`)

- [ ] 2.1 Author `evaluation/descriptors/aca-cli.yaml` declaring the `aca` CLI
  service, its registered command groups, and `scenario_dirs`. Add a test that
  loads it through the framework's descriptor model. **(M)**
  **Spec scenarios:** Descriptor and scenarios are schema-valid
  **Design decisions:** D4
  **Dependencies:** 1.2
- [ ] 2.2 Add a drift test asserting every command group registered on the CLI
  application appears in the descriptor, or is listed in a reviewed exclusion
  set with a stated reason. **(M)**
  **Spec scenarios:** Plumbing and discovery coverage
  **Dependencies:** 2.1
- [ ] 2.3 Author the `plumbing` category: version output and a `--help` sweep
  across the top-level application and each registered command group. **(M)**
  **Spec scenarios:** Plumbing and discovery coverage
  **Dependencies:** 2.1
- [ ] 2.4 Author the `discovery` category: capability discovery, configured-source
  listing, and durable operation listing, including the no-cursor case that
  `ri-01` repaired. Assert single-JSON-document stdout purity. **(M)**
  **Spec scenarios:** Plumbing and discovery coverage
  **Design decisions:** D7
  **Dependencies:** 2.1
- [ ] 2.5 Author the `validation` category: malformed arguments, invalid
  pagination cursors, and omission of absent optional query values. **(M)**
  **Spec scenarios:** Validation coverage
  **Dependencies:** 2.1

## Phase 3 — Report contract and threshold (`wp-gen-eval-report`)

- [ ] 3.1 Write validator tests covering: schema-invalid report, zero-scenario
  report, below-minimum per-category counts, a descriptor-declared interface
  missing from tested interfaces, and pass rate below threshold. **(M)**
  **Spec scenarios:** A vacuous run is rejected / CI enforces the documented
  threshold
  **Design decisions:** D6
- [ ] 3.2 Add `openspec/contracts/cli-gen-eval/gen-eval-report.schema.json` and a
  fixture set under `tests/fixtures/`, following the `release-smoke` durable
  contract layout. **(M)**
  **Spec scenarios:** `make gen-eval` emits a validated report
  **Dependencies:** 3.1
- [ ] 3.3 Implement `scripts/validate_gen_eval_report.py`: schema validation,
  minimum scenario and per-category counts, interface-coverage assertion, then
  threshold. **(M)**
  **Spec scenarios:** A vacuous run is rejected
  **Design decisions:** D6
  **Dependencies:** 3.1, 3.2
- [ ] 3.4 Add the `gen-eval` Make target forwarding `CATEGORIES` and running the
  gate followed by the validator. Document the threshold and the minimum counts
  in `evaluation/README.md`. **(S)**
  **Spec scenarios:** `make gen-eval` emits a validated report
  **Dependencies:** 1.2, 3.3
- [ ] 3.5 Add a grouping test asserting the emitted report groups results by
  command and category. **(S)**
  **Spec scenarios:** `make gen-eval` emits a validated report
  **Dependencies:** 3.2

## Phase 4 — Mutation guard and staging scenarios (`wp-gen-eval-mutation`)

- [ ] 4.1 Write guard tests: mutating category with no target policy, with a
  production target class, and with a non-production target whose identity or
  origin resolves to a registered production identity or origin. Assert no
  workflow is submitted in any rejection path. **(M)**
  **Spec scenarios:** Mutating scenarios require a non-production target / all
  **Design decisions:** D5
- [ ] 4.2 Implement the guard by consuming `src/release_smoke` target-policy
  models and their production deny registries. Add a test asserting no
  independent target classification is introduced. **(M)**
  **Spec scenarios:** The production guard is single-sourced
  **Design decisions:** D5
  **Dependencies:** 4.1
- [ ] 4.3 Author the `workflow-submission` category covering every canonical
  workflow operation type, asserting each returns a durable operation handle.
  **(L)**
  **Spec scenarios:** Canonical workflow submission coverage
  **Dependencies:** 2.1, 4.2
- [ ] 4.4 Author the `operation-control` category covering the operation
  retrieval, wait, retry, and cancel commands, observing at least one operation
  through a terminal state. **(L)**
  **Spec scenarios:** Operation control coverage
  **Design decisions:** D7
  **Dependencies:** 4.3
- [ ] 4.5 Add a test asserting the default category selection excludes every
  mutating category. **(S)**
  **Spec scenarios:** The default pull-request run excludes mutating categories
  **Dependencies:** 4.2

## Phase 5 — CI wiring (`wp-gen-eval-ci`)

- [ ] 5.1 Add `.github/workflows/cli-gen-eval.yml`: a pull-request job running
  read-only categories with `ACA_GEN_EVAL_REQUIRE=1` and template-only mode, and
  a `workflow_dispatch` staging job for mutating categories using the
  `release-smoke-staging` environment pattern. **(L)**
  **Spec scenarios:** CI enforces the documented threshold / Continuous
  integration selects deterministic generation
  **Design decisions:** D3, D8
  **Dependencies:** 3.4, 4.5
- [ ] 5.2 Check out the framework at a pinned recorded ref in CI so an absent
  checkout cannot occur silently, and record the pinned ref in
  `evaluation/README.md`. **(M)**
  **Spec scenarios:** The framework checkout is absent under enforcement
  **Design decisions:** D3
  **Dependencies:** 5.1
- [ ] 5.3 Upload the validated report and failure grouping as a retained
  artifact. **(S)**
  **Spec scenarios:** CI enforces the documented threshold
  **Dependencies:** 5.1
- [ ] 5.4 Add a workflow-configuration test in `tests/config/` asserting the
  pull-request job selects only read-only categories, sets enforcement, and does
  not pass `--allow-mutations`, following the
  `tests/config/test_release_smoke_workflow.py` pattern. **(M)**
  **Spec scenarios:** The default pull-request run excludes mutating categories
  **Dependencies:** 5.1

## Phase 6 — Documentation and close-out (`wp-gen-eval-docs`)

- [ ] 6.1 Add a Testing-guide section for the evaluation suite: how to run it,
  how to author a scenario, category semantics, and the three availability
  states. **(S)**
  **Dependencies:** 3.4
- [ ] 6.2 Document the `operations get` versus `operations status` naming
  reconciliation and the upstream console-script defect, including the follow-up
  filed against `agentic-coding-tools`. **(S)**
  **Design decisions:** D2, D7
- [ ] 6.3 Run `openspec validate establish-cli-gen-eval-coverage --strict`, the
  full test suite, lint, and type checks. **(S)**
  **Dependencies:** all
