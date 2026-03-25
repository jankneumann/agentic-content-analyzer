# Change: Add Digest Follow-Up Prompts

## Why

When a digest is shared with someone (via public link, email, or export), the reader gets a summary but no clear path to explore further. Most technical leaders already use LLM tools (ChatGPT, Claude, Gemini) daily. By embedding ready-to-use follow-up prompts alongside each digest section, we turn a passive summary into an active springboard for deeper analysis — without building any LLM integration ourselves.

This is high-leverage: the prompts are generated alongside digest content (no extra LLM call), require no database migration (JSON columns absorb the new field), and appear on every existing output surface via markdown rendering.

## What Changes

- **MODIFIED**: `DigestSection` Pydantic model — add `followup_prompts: list[str]` field
- **MODIFIED**: Digest creation prompt template — extend JSON output schema with `followup_prompts` per section, add generation guidance
- **MODIFIED**: Digest markdown generation — append `<details>` collapsible blocks with follow-up prompts after each section
- **MODIFIED**: Frontend `DigestPane` component — render follow-up prompts with copy-to-clipboard buttons
- **MODIFIED**: `DigestRequest` model — add `max_followup_prompts` parameter (default 3)

## Impact

- **Affected specs**: `content-sharing` (shared digests now include prompts via markdown), `pipeline` (digest creation output schema changes)
- **New files**: None
- **Affected code**:
  - `src/models/digest.py` — `DigestSection` model, `DigestRequest` model
  - `src/config/prompts.yaml` — digest creation prompt template
  - `src/processors/digest_creator.py` — markdown generation logic
  - `web/src/components/review/DigestPane.tsx` — section rendering
- **Dependencies**: None (builds on existing digest pipeline)
- **Breaking changes**: None — `followup_prompts` defaults to empty list, existing digests unaffected
- **Migration**: Not required — `DigestSection` is stored as JSON within existing columns

## Non-Goals

- **No "click to ask" integration** — the reader's LLM is external; copy-paste is the right UX
- **No per-digest-level prompts** — section-level prompts are more specific and useful
- **No reader personalization** — prompts target the existing multi-audience structure (leadership, teams, ICs)
- **No separate LLM call** — prompts generated as part of existing digest creation
