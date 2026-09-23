# Implementation refinement findings

## Iteration 1

Three independent read-only reviews covered contract/security, frontend
behavior, and evidence adequacy. All medium-or-higher findings were resolved.

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| I1 | High | Migration evidence skipped on PostgreSQL connection or database-creation failure. | The dedicated fixture now fails closed; a fresh Claimable PostgreSQL run completed with 2 passed and no skips. |
| I2 | Medium | The canonical config schema accepted invalid per-type payloads such as RSS without url. | Published the per-type discriminated union and regenerated Python/TypeScript artifacts; parity tests reject missing required fields. |
| I3 | Medium | Generated request models preserved siblings that FastAPI ignores. | Added explicit ignored-extra generation for POST/PATCH request envelopes and round-trip assertions. |
| I4 | Medium | Inline 422 items collapsed to untyped dictionaries. | Added LegacyValidationErrorItem and malformed-item rejection tests. |
| I5 | Medium | Nested percent encoding could evade audit-path redaction. | Audit normalization now decodes to a bounded fixed point and conservatively redacts Obsidian-prefixed identities; ASGI coverage proves persistence behavior. |
| I6 | Medium | Write-route authentication and no-mutation evidence did not cover both credential modes and member mutations. | Added admin/session lifecycle coverage plus 401/403 PATCH/DELETE state-and-version preservation assertions. |
| I7 | Medium | Malformed Obsidian keys could be displayed and same-row PATCH/DELETE operations could race. | The UI validates the opaque-key shape, redacts/disables malformed rows, and locks both controls while either mutation is pending. |
| I8 | Medium | Browser tests allowed global operations and notification-stream traffic to reach a real backend. | Added deterministic mocks; focused Chromium completed 7/7 without proxy fall-through. |
| I9 | Medium | Canonical pnpm commands could not execute while esbuild approval and effective security overrides were absent. | Kept the pnpm 11 workspace policy explicit (`esbuild: true` plus serialize-javascript/protobufjs overrides); canonical component, typecheck, and Playwright commands now pass. |
| I10 | Medium | Change context still described implementation as pending. | Final implementation and evidence mappings are populated before integration validation completes. |
| I11 | Medium | The initial implementation invented a 512-character HTTP key bound contrary to D5. | Removed the OpenAPI/runtime bound and regenerated artifacts, preserving the existing nonempty/no-NUL behavior. |

## Iteration 2

The convergence review found three remaining contract/privacy gaps. All were
closed with focused regression evidence.

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| I12 | Medium | TypeScript request objects rejected compatibility siblings that Python/runtime accept and ignore. | TypeScript generation again emits an unknown-property index signature while Python retains ignore semantics; contract tests assert both behaviors. |
| I13 | Medium | Generated Obsidian configuration omitted inherited fields and accepted values rejected by runtime validators. | Added inherited fields, exclusive numeric bounds, safe-path validation, and nested byte-limit validation to the canonical/generated model with bidirectional parity tests. |
| I14 | Medium | Audit redaction's decoding cap could expose an extremely deeply encoded Obsidian locator. | Increased the bounded decode allowance and fail closed whenever decoding does not stabilize; a 40-layer ASGI regression remains fully redacted. |

## Verification

- Contract/API/audit/CLI focused suite: 116 passed after the complete rerun;
  contract-only confirmation: 34 passed.
- Rendered component suite: 10 passed.
- Chromium source-settings journey: 7 passed.
- Disposable PostgreSQL migration evidence: 2 passed, no skips.
- Contract generation/check: current and deterministic.
- Frontend typecheck: passed.
- Archived source change: untouched.

## Residual notes

- Canonical `pnpm --dir web` checkpoints execute under pnpm 11 with the explicit
  workspace build approval and security overrides.
- Node 22.23.2 satisfies jsdom 30.1.0. The broader existing 22.x engine range
  remains a low-severity repository policy concern outside this closeout.
