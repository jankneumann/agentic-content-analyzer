# Validation Report: add-cross-surface-release-smoke-tests

Date: 2026-07-23

## Result

PASS — implementation and focused integration gates are clean after independent
implementation and security rework.

## Behavioral and contract gates

- 143 release-smoke, workflow configuration, build identity, stamp, manual
  evidence, and health tests passed.
- 49 canonical `WorkflowApiClient` and real CLI command-boundary tests passed.
- 7 focused frontend workflow-contract tests passed.
- A real local Chromium fixture exercised direct API and frontend discovery,
  exact-origin routing, read-only enforcement, cross-origin redirect rejection,
  WebSocket denial, cookie policy, loaded HTML scanning, and manifest-complete
  asset retrieval.
- The production frontend build emitted an inventory exactly matching all
  generated JavaScript, including `/sw.js`, Workbox, entry, and lazy chunks.

## Static and structural gates

- Ruff check and format passed for all changed Python.
- mypy passed for the release runner, CLI/client, health, and validator paths.
- TypeScript typecheck and Vite production build passed.
- Strict OpenSpec validation passed.
- Work-package schema, dependency references, DAG, and lock-key validation
  passed at plan revision 3.
- `git diff --check` passed.

## Security evidence

- Independent security review exercised redirect credential forwarding,
  browser origin/credential boundaries, production identity aliases, streamed
  resource bounds, evidence log redaction, dependency pinning, and protected
  environment controls.
- Credentials remain environment-only and are absent from retained evidence.
- Invalid or missing evidence is discarded and replaced with a separately
  generated, validated fixed-field failure envelope before artifact upload;
  replacement remains a failed promotion signal.
- Production browser and direct runner paths cannot construct a workflow
  mutation; staging mutation requires protected identity/origin deny registries,
  explicit authorization, and the checked-in fixture.

## Deployment boundary

This change provides a manual verification gate for an already deployed pair
and intentionally performs no deployment. A live production/staging run
requires the protected GitHub environments and is an operator promotion action,
not an implementation-time validation prerequisite.
