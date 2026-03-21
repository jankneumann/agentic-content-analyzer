# Tasks: Digest Follow-Up Prompts

## Phase 1: Data Model

- [x] 1.1 Add `followup_prompts: list[str] = Field(default_factory=list, description="LLM prompts for deeper analysis")` to `DigestSection` in `src/models/digest.py`
- [x] 1.2 Add `max_followup_prompts: int = Field(default=3, description="Max follow-up prompts per section")` to `DigestRequest` in `src/models/digest.py`
- [x] 1.3 Add unit test verifying `DigestSection` backward compatibility: deserializing a dict without `followup_prompts` yields empty list

## Phase 2: Prompt Template

- [x] 2.1 Update digest creation user template in `src/config/prompts.yaml`:
  - Add `followup_prompts` array to each section type in the JSON output schema
  - Add `{{ max_followup_prompts }}` template variable reference
- [x] 2.2 Add generation guidance to the system prompt in `src/config/prompts.yaml`:
  - Self-contained, specific, action-oriented, audience-aware criteria
  - Prompt variety guidelines (analysis, comparison, strategic, implementation)
- [x] 2.3 `max_followup_prompts` passed through to prompt template context via `digest_creator.py`

## Phase 3: Markdown Generation

- [x] 3.1 Update markdown generation in `src/utils/digest_markdown.py` to append `<details>` blocks after each section when `followup_prompts` is non-empty
- [x] 3.2 Skip `<details>` block when `followup_prompts` is empty (backward compatibility)
- [x] 3.3 Add unit test for markdown generation with and without follow-up prompts

## Phase 4: Frontend

- [x] 4.1 Update TypeScript types for digest sections to include `followup_prompts?: string[]`
- [x] 4.2 Add collapsible follow-up prompts section to `DigestPane` component in `web/src/components/review/DigestPane.tsx`
  - Use shadcn/ui `Collapsible` component
  - Show prompt count in trigger label
  - Each prompt gets a copy-to-clipboard button with visual feedback
- [x] 4.3 Add E2E test mock data with `followup_prompts` arrays in digest section factories
- [ ] 4.4 Add E2E test verifying prompts render and copy button works

## Phase 5: Integration Verification

- [x] 5.1 Shared digest view (`/shared/digest/{token}`) renders `<details>` blocks from `markdown_html` — no template changes needed (uses `{{ markdown_html | safe }}`)
- [x] 5.2 API response includes `followup_prompts` in section JSON — no route changes needed (JSON columns pass through)
- [x] 5.3 Existing digests without `followup_prompts` load without errors — verified via backward compatibility tests
