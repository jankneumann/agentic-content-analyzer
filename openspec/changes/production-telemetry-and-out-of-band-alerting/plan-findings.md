# Plan findings

## Iteration 1

All critical/high findings from the scaffold review were addressed:

- Replaced post-commit best-effort notification hooks with atomic minimal event intent.
- Selected one concrete v1 sink and documented honest at-least-once/idempotent-receiver semantics.
- Added lifecycle/result precedence, retry-attempt identity, and pipeline graph aggregation.
- Added allowlist-first payload, diagnostic-origin, SSRF, secret, and transport constraints.
- Added delivery lease, crash recovery, response policy, exhaustion, and retention requirements.
- Preserved reconciliation dry-run purity and tied applied events to immutable action evidence.
- Separated low-cardinality workflow telemetry from raw-error metrics and Langfuse traces.
- Added sanitized staging evidence plus deterministic failure/duplicate behavior.

Residual low-risk note: implementation must validate the exact operation-root query used
for graph alert suppression against the 10,001-row test fixture before retaining an index.
