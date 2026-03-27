# Plan Review: add-capacitor-mobile

You are reviewing the plan artifacts for the `add-capacitor-mobile` OpenSpec change. Your job is to produce structured findings as a JSON array.

## Input Artifacts (Read-Only)

Read these files in the repository:

- `openspec/changes/add-capacitor-mobile/proposal.md`
- `openspec/changes/add-capacitor-mobile/design.md`
- `openspec/changes/add-capacitor-mobile/tasks.md`
- `openspec/changes/add-capacitor-mobile/specs/capacitor-mobile/spec.md`
- `openspec/changes/add-capacitor-mobile/specs/content-capture/spec.md`
- `openspec/changes/add-capacitor-mobile/specs/native-share-target/spec.md`
- `openspec/changes/add-capacitor-mobile/specs/voice-input/spec.md`

## Codebase Context

For grounding your review, check:

- `web/src/lib/voice/engine.ts` — existing STT engine interface (already reserves `"native"` ID)
- `src/api/save_routes.py` — existing save-url API endpoint
- `src/api/notification_routes.py` — existing notification event system (device registration exists)
- `src/services/notification_service.py` — existing notification service (SSE-based, no APNs)
- `.github/workflows/ci.yml` — existing CI (ubuntu-only)
- `web/package.json` — no Capacitor dependencies yet

## Review Dimensions

Evaluate against:

1. **Specification Completeness** — SHALL/MUST language, testable requirements, no ambiguity
2. **Architecture Alignment** — follows codebase patterns, no unnecessary dependencies, complete error handling
3. **Security** — input validation, auth for new endpoints, no secrets in config
4. **Correctness** — logical errors, missing tasks, numbering gaps
5. **Performance** — startup impact, lazy loading, resource usage

## Output Format

Output ONLY valid JSON conforming to this structure:

```json
{
  "review_type": "plan",
  "target": "add-capacitor-mobile",
  "reviewer_vendor": "<your-model-name>",
  "findings": [
    {
      "id": 1,
      "type": "spec_gap|contract_mismatch|architecture|security|performance|style|correctness",
      "criticality": "high|medium|low",
      "description": "What is wrong and why it matters",
      "resolution": "Specific fix recommendation",
      "disposition": "fix|regenerate|accept|escalate"
    }
  ]
}
```

Do NOT modify any input files. Output only the JSON findings.
