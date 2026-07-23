# Change Context: restore-railway-frontend-deployment

## Requirement Traceability Matrix

| Req ID | Spec Source | Description | Contract Ref | Design Decision | Files Changed | Test(s) | Evidence |
|--------|-------------|-------------|--------------|-----------------|---------------|---------|----------|
| frontend-release-delivery.1 | `specs/frontend-release-delivery/spec.md` | Railway builds the isolated frontend from an uploaded committed, audit-gated lock without repository-level tools. | --- | D1, D2 | `.gitignore`, `package.json`, `pnpm-lock.yaml`, `web/package.json`, `web/package-lock.json` | `tests/config/test_frontend_deployment.py` | `evidence/production-deployment.md` — deployment `253e84a9-7946-48c6-b24a-cde6ca73313d` uploaded `web/package-lock.json`, selected Node 22.23.1, ran `npm ci`, built successfully, and reached `SUCCESS`. |
| frontend-release-delivery.2 | `specs/frontend-release-delivery/spec.md` | CI runs the production dependency audit, generated-contract drift, and exact production build. | `openspec/contracts/content-workflows/openapi/v1.yaml` | D3 | `.github/workflows/ci.yml` | `tests/config/test_frontend_ci.py` | `evidence/production-deployment.md` — exact candidate `648e2c9b02646c6f101957ff4816847992ac919e` passed GitHub `frontend-release` job `89328888655`; the clean local release gate also passed. |
| frontend-release-delivery.3 | `specs/frontend-release-delivery/spec.md` | Production discovers capabilities, submits canonical ingestion, and avoids retired mutations. | `openspec/contracts/content-workflows/openapi/v1.yaml` | D4, D5 | `web/src/lib/api/workflows.ts`, `web/src/routes/ingest.tsx` (verification only) | `web/src/lib/api/__tests__/workflow-contracts.test.ts`, `web/tests/e2e/workflow-surface.spec.ts` | `evidence/production-deployment.md` — production capability discovery returned 200, one visible canonical ingestion returned 202 and operation `104` completed, with zero retired-route calls. |

## Design Decision Trace

| Decision | Rationale | Implementation | Why This Approach |
|----------|-----------|----------------|-------------------|
| D1 | Match the isolated Railpack context. | npm lock plus manager-neutral build; npm and pnpm overrides converge on the audit-safe transitive dependency. | Production already selects npm and sees only `/web`, while repository workflows retain pnpm. |
| D2 | Keep artifact construction minimal. | Remove contract generation from the transitive production build. | Python/uv inputs are absent from the isolated static build. |
| D3 | Preserve both release gates. | Dedicated full-checkout frontend CI job. | CI has Node, Python, uv, and canonical generator inputs. |
| D4 | Promote only an immutable, recoverable revision. | Pre-deployment rollback manifest plus exact-SHA CI and Railway matching. | A local build cannot prove the deployed revision passed CI. |
| D5 | Prove the active network behavior. | One-shot labeled canary plus correlated browser/HTTP verification. | Source inspection alone cannot prove the served revision. |
| D6 | Keep proof reviewable without secrets. | Sanitized deployment and bounded-log evidence template. | Durable evidence supports rollback and later roadmap items. |

## Review Findings Summary

| Finding ID | Package | Type | Criticality | Disposition | Resolution |
|------------|---------|------|-------------|-------------|------------|
| PR-01 | wp-production-proof | correctness | blocker | fixed | Candidate deployment requires a draft-PR exact-SHA `frontend-release` success, a clean detached-SHA upload, and matching SHA-bearing Railway `meta.cliMessage` (CLI uploads expose no `commitHash`). |
| PR-02 | wp-production-proof | reliability | blocker | fixed | Rollback manifest and abort criteria must be captured before deployment. |
| PR-03 | wp-production-proof | observability | blocker | fixed | Added a sanitized evidence template and a planned completeness validator for correlated browser, request, operation, log, revision, and rollback fields. |
| PR-04 | wp-production-proof | safety | blocker | fixed | Specified one visible-form, non-repeated, uniquely marked URL canary and explicit retention/cleanup handling without claiming an unimplemented UI header. |
| PR-05 | wp-production-build | consistency | should-fix | fixed | Node 22 is required in package metadata, CI, specification, tests, and verification. |
| PR-06 | wp-ci-parity | testability | should-fix | fixed | Added an explicit non-watch workflow-client test command to package and integration gates. |
| PR-07 | wp-production-proof | correctness | blocker | fixed | Draft PR creation/check waiting and detached exact-SHA Railway upload/query steps are now executable. |
| PR-08 | wp-production-proof | testability | blocker | fixed | Evidence completeness is enforced by a tested repository validator, not file existence alone. |
| PR-09 | wp-ci-parity | consistency | should-fix | fixed | Focused-test result keys are included in package and integration outputs. |
| PR-10 | wp-production-build | correctness | blocker | fixed | Live Railpack evidence showed the CLI uploader omitted the tracked lock due to `.gitignore`; an explicit exception and Git-ignore regression now guard the upload boundary. |
| PR-11 | wp-production-build | security | blocker | fixed | The production npm graph pinned critically vulnerable `protobufjs` 8.0.0. Both npm and pnpm override/lock graphs now use 8.7.1, and CI blocks high or critical production audit findings. |
| PR-12 | wp-production-proof | correctness | blocker | fixed | The evidence contract now requires the uploaded lockfile path, exact `npm ci` command, and observed Node 22 runtime instead of inferring them from build success. |
| PR-13 | wp-production-proof | correctness | blocker | fixed | Correlation evidence now requires request IDs, parseable in-window UTC timestamps, browser attribution, canonical routes/statuses, and the durable operation ID. |

## Coverage Summary

- **Requirements traced**: 3/3
- **Tests mapped**: 3 requirements have planned automated or production verification
- **Evidence collected**: 3/3 requirements have passing evidence after the
  security remediation.
- **Gaps identified**: None for this change.
- **Deferred items**: Cross-surface release automation beyond this frontend proof
  belongs to `ri-04`. The remaining moderate OpenTelemetry audit chain is
  tracked in `#468`; nullable form-input console warnings observed during the
  first smoke are tracked in `#470`.
