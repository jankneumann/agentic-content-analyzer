# Plan Review: add-tauri-desktop

You are reviewing a plan for adding Tauri v2 desktop shell support to an existing web application. Read the plan artifacts below and produce a JSON review findings document.

## Artifacts to Read

Read these files (all are read-only — do NOT modify them):

1. `openspec/changes/add-tauri-desktop/proposal.md` — What and why
2. `openspec/changes/add-tauri-desktop/design.md` — How, with design decisions
3. `openspec/changes/add-tauri-desktop/tasks.md` — Implementation tasks
4. `openspec/changes/add-tauri-desktop/specs/tauri-desktop/spec.md` — Main spec
5. `openspec/changes/add-tauri-desktop/specs/content-capture/spec.md` — Delta spec
6. `openspec/changes/add-tauri-desktop/specs/voice-input/spec.md` — Delta spec

## Codebase Context

Key facts about the current codebase:
- `web/src/lib/platform.ts` does NOT exist yet (referenced as coming from `add-capacitor-mobile` which is unimplemented)
- `web/src/hooks/use-voice-input.ts` EXISTS — wraps Web Speech API, has `startListening/stopListening/toggleListening`
- `src/api/upload_routes.py` EXISTS — document upload with magic bytes validation, auth required
- Capacitor (`@capacitor/core`) is NOT in `web/package.json`
- `add-notification-events` IS implemented (archived) — SSE endpoint exists
- `add-capacitor-mobile` is NOT implemented — still an open proposal
- Authentication uses session cookies + `X-Admin-Key` header

## Review Checklist

Evaluate the plan against these dimensions:

1. **Specification Completeness** — Are all requirements testable? Do they use SHALL/MUST language? Any ambiguity?
2. **Architecture Alignment** — Does the design follow existing codebase patterns? Any unnecessary dependencies?
3. **Security Review** — Input validation, auth for new features, OWASP considerations
4. **Correctness** — Any factual errors about Tauri v2 APIs, plugin names, or behavior?
5. **Dependency Risks** — Are declared dependencies on other proposals accurate? Are there hidden dependencies?
6. **Task Completeness** — Do tasks cover everything in the design and spec? Any gaps?

## Output Format

Output ONLY valid JSON (no markdown, no commentary) conforming to this structure:

```json
{
  "review_type": "plan",
  "target": "add-tauri-desktop",
  "reviewer_vendor": "<your-model-name>",
  "findings": [
    {
      "id": 1,
      "type": "<spec_gap|contract_mismatch|architecture|security|performance|style|correctness>",
      "criticality": "<high|medium|low>",
      "description": "Clear description of the issue found",
      "resolution": "Specific actionable resolution",
      "disposition": "<fix|regenerate|accept|escalate>"
    }
  ]
}
```

Finding types: `spec_gap` (missing/incomplete requirements), `architecture` (design/structural concern), `security` (vulnerability/missing protection), `correctness` (factual error), `performance` (potential issue), `style` (convention violation).

Dispositions: `fix` (author should fix), `accept` (minor, ok as-is), `escalate` (needs human decision).

Focus on HIGH and MEDIUM criticality findings. Include LOW only if they are genuinely useful.
