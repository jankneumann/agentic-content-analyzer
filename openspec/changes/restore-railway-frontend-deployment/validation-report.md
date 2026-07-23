# Validation Report: restore-railway-frontend-deployment

**Date**: 2026-07-23 16:56:00 EDT
**Production candidate**: 648e2c9b02646c6f101957ff4816847992ac919e
**Branch**: openspec/restore-railway-frontend-deployment
**Scope**: full, including production deployment

## Phase Results

- ✓ Spec Compliance: 3/3 requirements have passing evidence in
  `change-context.md`; strict OpenSpec validation passed.
- ✓ Security Remediation: npm and pnpm graphs now pin `protobufjs` 8.7.1;
  `npm audit --omit=dev --audit-level=high` passes, and CI enforces the gate.
- ✓ Evidence Contract: observed lock/install/runtime facts and attributed,
  in-window backend correlation are now mandatory.
- ✓ Production Build: Railway uploaded `web/package-lock.json`, selected Node
  22.23.1, ran `npm ci`, and completed the exact Vite/PWA build.
- ✓ CI Release Gate: GitHub `frontend-release` job `89328888655` passed for the
  exact production candidate SHA.
- ✓ Production Deployment: Railway deployment
  `253e84a9-7946-48c6-b24a-cde6ca73313d` reached `SUCCESS` and recorded the
  exact candidate in its CLI release message.
- ✓ Production Behavior: capability discovery returned 200; exactly one visible
  canonical ingestion returned 202; durable operation `104` completed; bounded
  logs show zero calls to both retired mutation routes.
- ✓ Rollback Readiness: the active deployment and independently known-good
  revision, detached-upload command, and abort criteria were recorded before
  mutation and reverified.
- ✓ Focused Regression Gate: 46 Python configuration/evidence tests and 6
  workflow-contract Vitest tests passed.
- ✓ Contract and Evidence Gates: generated contracts are current and the
  strengthened production evidence validator passed.
- ✓ Static Quality: Ruff, Mypy, strict package/OpenSpec validation, work-package
  scope/lock validation, and `git diff --check` passed.
- ⚠ Local Runtime: the clean install ran under local Node 25 and emitted the
  expected engine warning; CI and Railway use the required Node 22 major.
- ⚠ Deferred Findings: 10 moderate OpenTelemetry audit findings remain tracked
  in `#468`; nullable form-input console warnings observed during the first
  smoke are tracked in `#470`.
- ○ Browser Plugin: initialization failed before navigation, so repository
  Playwright supplied the production browser proof. The failure and fallback are
  recorded in the evidence artifact.

## Result

**PASS** — ri-02 restores a deterministic, high-severity-audit-gated Railway
frontend release, proves the exact corrected candidate through CI and
production, and satisfies every local acceptance outcome with recoverable
release evidence.
