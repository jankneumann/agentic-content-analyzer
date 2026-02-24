# Validation Report: add-image-generator-service

**Date**: 2026-02-24 05:05:00
**Commit**: 470026c
**Branch**: openspec/add-image-generator-service
**PR**: #219 (OPEN)

## Phase Results

### ✓ Deploy
- API started from worktree with DEBUG logging
- 3 image generation endpoints registered in OpenAPI spec:
  - `POST /api/v1/images/generate`
  - `POST /api/v1/images/suggest`
  - `POST /api/v1/images/{image_id}/regenerate`
- Health: 200, Ready: 200

### ⚠ Smoke
- Health/readiness: PASS (200)
- Auth enforcement: Development mode allows unauthenticated access (expected for `ENVIRONMENT=development`)
- Image endpoints return 500 when `IMAGE_GENERATION_ENABLED=false` (default)
  - **Finding**: `ValueError` from `get_image_generator()` should be caught and returned as 422 or 503, not 500
  - Error response is sanitized correctly: `{"error": "Internal Server Error", "detail": "An internal error occurred"}`
- Error sanitization: PASS (no sensitive info leaked in 404 responses)
- CORS preflight: PASS (200)

### ✓ Unit Tests (local)
- `tests/services/test_image_generator.py`: **21 passed**
- `tests/services/test_image_generation_prompts.py`: **8 passed**
- Total: **29 passed** in 3.87s

### ✓ API Tests (local)
- `tests/api/test_image_generation_api.py`: **13 passed** in 2.62s

### ✗ CI/CD
**test job: FAIL**
- `test_default_initialization_succeeds` — `KeyError: <ModelStep.IMAGE_SUGGESTION>`
- `test_get_all_models_returns_all_steps` — `IMAGE_SUGGESTION` not in `get_all_models()` dict

**Root cause**: `ModelConfig.__init__()` in `src/config/models.py:283-302` hardcodes all model step mappings but `IMAGE_SUGGESTION` was never added. The `ModelStep` enum and `model_registry.yaml` were updated, but the constructor dict was not.

**Fix required**: Add `image_suggestion` parameter to `ModelConfig.__init__()` and add the `ModelStep.IMAGE_SUGGESTION` entry to `self._models` dict.

**Other CI results:**
- lint: PASS
- validate-profiles: PASS
- SonarCloud: PASS
- contract-test: FAIL (pre-existing `settings_overrides` Hypothesis health check — not related to this feature)

### ○ E2E
SKIP — No frontend changes in this feature; no E2E tests applicable.

### ○ Architecture
SKIP — Architecture validation scripts not available (`scripts/validate_flows.py` not found).

### ○ Spec Compliance
SKIP — No spec delta files found at `openspec/changes/add-image-generator-service/specs/`.

### ⚠ Log Analysis
- Total log lines: 1,692
- Warnings: 6
- Errors: 104 (all from smoke test hitting disabled feature endpoint)
- Critical: 0
- Stack traces: 24 (all from `ValueError: Image generation is disabled`)
- Deprecations: 5 (pre-existing `datetime.utcnow()` in `digest_routes.py`, `theme_routes.py`)

**Note**: All errors/stack traces are from the smoke test intentionally calling endpoints with the feature disabled. No unexpected errors observed.

## Prerequisites Check

| Prerequisite | Status |
|---|---|
| Feature branch exists | ✓ |
| Implementation commits | ✓ (3 commits) |
| Docker available | ✓ |
| Security review report | ✗ Missing |

## Findings Summary

### Blocking (must fix)

1. **`ModelConfig.__init__` missing `IMAGE_SUGGESTION`** — Causes 2 CI test failures. The `ModelStep.IMAGE_SUGGESTION` enum value and `model_registry.yaml` entry exist, but `ModelConfig.__init__()` was not updated to include the new step in `self._models`. This is a straightforward fix: add `image_suggestion: str | None = None` parameter and corresponding dict entry.

### Non-blocking (should fix)

2. **Feature-disabled endpoints return 500 instead of informative error** — When `IMAGE_GENERATION_ENABLED=false`, the API routes let `ValueError` from `get_image_generator()` propagate as a 500. Should catch and return 422 with message like "Image generation is disabled" or 503 (Service Unavailable).

3. **Missing security review report** — No `security-review-report.md` found. Run `/security-review add-image-generator-service` before final merge.

### Informational

4. **Deferred tasks noted in tasks.md** — Rate limiting (4.2) and review workflow integration (5.1-5.2) are explicitly deferred with rationale.
5. **Pre-existing deprecation warnings** — `datetime.utcnow()` in `digest_routes.py` and `theme_routes.py` (not from this feature).
6. **Contract test flakiness** — `settings_overrides` Hypothesis health check failure is pre-existing and not caused by this feature.

## Result

**FAIL** — 1 blocking finding must be addressed before merge.

### Next Steps

```
Option 1: Fix and re-validate
  /iterate-on-implementation add-image-generator-service
  /validate-feature add-image-generator-service

Option 2: Fix the specific issue
  1. Add IMAGE_SUGGESTION to ModelConfig.__init__() in src/config/models.py
  2. Optionally catch ValueError in image generation routes for better error codes
  3. Push and re-run CI
```
