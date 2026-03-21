# Tasks: Digest Follow-Up Prompts

## Phase 1: Data Model

- [ ] 1.1 Add `followup_prompts: list[str] = Field(default_factory=list, description="LLM prompts for deeper analysis")` to `DigestSection` in `src/models/digest.py`
- [ ] 1.2 Add `max_followup_prompts: int = Field(default=3, description="Max follow-up prompts per section")` to `DigestRequest` in `src/models/digest.py`
- [ ] 1.3 Add unit test verifying `DigestSection` backward compatibility: deserializing a dict without `followup_prompts` yields empty list

## Phase 2: Prompt Template

- [ ] 2.1 Update digest creation user template in `src/config/prompts.yaml`:
  - Add `followup_prompts` array to each section type in the JSON output schema
  - Add `{{ max_followup_prompts }}` template variable reference
- [ ] 2.2 Add generation guidance to the system prompt in `src/config/prompts.yaml`:
  - Self-contained, specific, action-oriented, audience-aware criteria
  - Prompt variety guidelines (analysis, comparison, strategic, implementation)
- [ ] 2.3 Add unit test verifying `max_followup_prompts` is passed through to the prompt template context

## Phase 3: Markdown Generation

- [ ] 3.1 Update markdown generation in `src/processors/digest_creator.py` to append `<details>` blocks after each section when `followup_prompts` is non-empty
- [ ] 3.2 Skip `<details>` block when `followup_prompts` is empty (backward compatibility)
- [ ] 3.3 Add unit test for markdown generation with and without follow-up prompts

## Phase 4: Frontend

- [ ] 4.1 Update TypeScript types for digest sections to include `followup_prompts?: string[]`
- [ ] 4.2 Add collapsible follow-up prompts section to `DigestPane` component in `web/src/components/review/DigestPane.tsx`
  - Use shadcn/ui `Collapsible` component
  - Show prompt count in trigger label
  - Each prompt gets a copy-to-clipboard button with visual feedback
- [ ] 4.3 Add E2E test mock data with `followup_prompts` arrays in digest section factories
- [ ] 4.4 Add E2E test verifying prompts render and copy button works

## Phase 5: Integration Verification

- [ ] 5.1 Verify shared digest view (`/shared/digest/{token}`) renders `<details>` blocks from `markdown_html` — no template changes needed
- [ ] 5.2 Verify API response includes `followup_prompts` in section JSON — no route changes needed
- [ ] 5.3 Verify existing digests (without `followup_prompts` in DB) load without errors
