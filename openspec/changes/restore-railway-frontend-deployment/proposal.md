# Restore the Railway frontend deployment

> Parent roadmap: `roadmap-workflow-surface-reliability`
> Change ID: `restore-railway-frontend-deployment`
> Effort: M
> Priority: 2

## Summary

Make the frontend build reproducible under the documented Railway configuration, move generated-contract drift enforcement to a context with the complete toolchain, and deploy the current capability-driven ingestion UI.

## Dependencies

- None

## Acceptance Outcomes

- A clean Railway frontend build succeeds from the checked-in service configuration.
- CI runs both the production frontend build and the generated workflow-contract drift check.
- The active production frontend revision discovers capabilities and submits POST /api/v1/ingestions.
- Production traffic no longer calls POST /api/v1/contents/ingest or POST /api/v1/content/save-url.

## Rationale

Production is serving an old frontend that calls retired mutations because the corrected frontend cannot build in Railway.
