## Context
We need an authenticated Substack ingestion path that can read a user's subscriptions (including paid content) and sync them into the existing source configuration system. The unofficial `substack_api` dependency introduces new auth handling and data modeling.

## Goals / Non-Goals
- Goals:
  - Support Substack subscription discovery and sync into `sources.d/substack.yaml`.
  - Support ingestion of recent posts from enabled Substack sources.
  - Provide a clear workflow for session cookie configuration.
  - Deduplicate Substack posts by canonical URL.
- Non-Goals:
  - Implement Substack comment ingestion.
  - Build a UI for managing Substack sources.

## Decisions
- Decision: Use `sources.d/substack.yaml` (Substack.yml) with `type: substack` entries, mirroring existing source configuration patterns.
- Decision: Store the session cookie in environment configuration (e.g., `SUBSTACK_SESSION_COOKIE`) and never in YAML files.
- Decision: Deduplicate Substack ingestion by canonical URL before writing Content records.
- Alternatives considered: Substack RSS-only ingestion (insufficient for paid content and subscription discovery).

## Risks / Trade-offs
- Risk: Unofficial API changes may break ingestion.
  - Mitigation: Wrap API access in a client layer with clear error handling and log actionable warnings.
- Risk: Session cookie storage requires user guidance.
  - Mitigation: Provide step-by-step instructions and validation errors when missing/expired.

## Migration Plan
1. Introduce new source type and config file.
2. Add sync command to populate `sources.d/substack.yaml`.
3. Document cookie setup and enable/disable controls.

## Open Questions
- Should subscription sync preserve manual tags or overwrite them?
- What is the default `max_entries` for Substack sources?
