# Tasks: Repair canonical CLI transport behavior

> Change ID: `repair-canonical-cli-transport-behavior`
> Selected approach: repair the shared client boundary

## Phase 1 — Transport serialization (`wp-transport`)

- [x] 1.1 Write serialized-query regression tests for all three cursor-page client methods. **(S)**
  **Spec scenarios:** CLI capability discovery / First discovery page omits cursor; Explicit cursor is preserved
  **Contracts:** `openspec/contracts/content-workflows/openapi/v1.yaml`
  **Design decisions:** D1
  **Dependencies:** None
- [x] 1.2 Omit absent optional values in the shared workflow client. **(S)**
  **Dependencies:** 1.1
- [x] Checkpoint: run client tests; review the transport diff; verify scope.

## Phase 2 — Discovery and JSON output (`wp-cli-output`)

- [x] 2.1 Write the configured-source command-local JSON regression. **(S)**
  **Spec scenarios:** CLI capability discovery / Configured sources use command-local JSON
  **Contracts:** `openspec/contracts/content-workflows/openapi/v1.yaml`
  **Design decisions:** D2
  **Dependencies:** None
- [x] 2.2 Write pure machine-output regressions. **(S)**
  **Spec scenarios:** Output format / JSON output
  **Design decisions:** D3
  **Dependencies:** None
- [x] 2.3 Implement command-local discovery JSON. **(S)**
  **Dependencies:** 2.1
- [x] 2.4 Route diagnostics away from stdout. **(S)**
  **Dependencies:** 2.2
- [x] Checkpoint: run canonical workflow plus graph CLI tests; review the output diff; verify scope.

## Phase 3 — Hermetic CLI tests (`wp-test-isolation`)

- [x] 3.1 Make RSS curation tests select their transport explicitly. **(S)**
  **Spec scenarios:** Hermetic CLI transport tests / Ambient credentials do not select a live transport
  **Design decisions:** D4
  **Dependencies:** None
- [x] 3.2 Exercise the real graph coroutine consumer with async mocks. **(S)**
  **Spec scenarios:** Hermetic CLI transport tests / Async graph boundary is consumed
  **Design decisions:** D4
  **Dependencies:** None
- [x] Checkpoint: run curation plus graph tests with warnings enabled; review the test diff; verify scope.

## Phase 4 — Runtime warning hygiene (`wp-runtime-hygiene`)

- [x] 4.1 Add the optional dependency warning regression. **(S)**
  **Spec scenarios:** CLI dependency warning hygiene / Optional crawler dependencies are compatible
  **Design decisions:** D5
  **Dependencies:** None
- [x] 4.2 Add the canonical local profile regression. **(S)**
  **Spec scenarios:** CLI dependency warning hygiene / Tracked local profile uses canonical graph keys
  **Design decisions:** D5
  **Dependencies:** None
- [x] 4.3 Constrain the optional detector dependency. **(S)**
  **Dependencies:** 4.1
- [x] 4.4 Migrate the tracked local graph profile keys. **(S)**
  **Dependencies:** 4.2
- [x] Checkpoint: verify the lock, load the local profile, review the configuration diff.

## Phase 5 — Integration (`wp-integration`)

- [x] 5.1 Document the transport/output invariants. **(S)**
  **Spec scenarios:** Output format / JSON output; CLI capability discovery / First discovery page omits cursor
  **Design decisions:** D1, D3
  **Dependencies:** 1.2, 2.3, 2.4, 3.1, 3.2, 4.3, 4.4
- [x] 5.2 Run the full CLI verification gate with warning checks. **(M)**
  **Dependencies:** 5.1

## Gate 2 Approval

Approved through parent roadmap `roadmap-workflow-surface-reliability` on
2026-07-23. The item acceptance outcomes select the shared-client repair and
forbid transport-specific execution paths.
