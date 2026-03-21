# Design: Digest Follow-Up Prompts

## Architecture Decision: Per-Section vs Per-Digest

**Choice**: Per-section prompts (strategic insights, technical developments, emerging trends).

**Rationale**: A single set of generic prompts for the whole digest would be shallow. The value is contextual prompts tied to specific insights — "This digest mentions X evolving toward Y; here's how to explore what that means for your stack." This matches how people use LLMs: they read something specific and want to go deeper on *that*.

## Architecture Decision: No Migration Required

**Choice**: Extend `DigestSection` Pydantic model only; no Alembic migration.

**Rationale**: `strategic_insights`, `technical_developments`, and `emerging_trends` are `JSON` columns on the `Digest` table storing `list[dict]`. Adding `followup_prompts` to `DigestSection` adds a new key to these dicts, which JSON columns absorb naturally. Existing rows without the key default to `[]` via Pydantic's `default_factory`.

## Architecture Decision: Inline Generation

**Choice**: Generate prompts as part of the existing digest creation LLM call.

**Rationale**: Adding a separate LLM call would increase latency and cost. The prompts are contextual to each section and generated naturally alongside the content. Token cost increase is ~50-100 tokens per section (~500 tokens total), negligible compared to the full digest generation.

## Data Flow

```
DigestRequest(max_followup_prompts=3)
  → digest_creator.py: build prompt with followup_prompts in JSON schema
  → LLM response: each section includes followup_prompts[]
  → DigestSection.followup_prompts populated
  → Markdown generation: <details> blocks appended after each section
  → Stored in Digest.markdown_content + JSON columns
  → Surfaces via:
      - Review UI (DigestPane with copy buttons)
      - Shared HTML (/shared/digest/{token} via markdown_html)
      - API JSON response (followup_prompts in section objects)
```

## Markdown Format

```markdown
### Strategic Insight: Multi-Modal RAG Architectures

Summary and details...

<details>
<summary>Follow-up prompts (3)</summary>

**1.** Given that multi-modal RAG architectures are shifting toward unified
embedding spaces, analyze how this impacts retrieval accuracy for enterprise
document search. What are the key trade-offs between separate vs. unified
pipelines?

**2.** Compare the cost and latency implications of using Gemini's native
multi-modal capabilities vs. a traditional RAG pipeline with separate
text/image encoders for a production system processing 10K documents/day.

**3.** Draft a 1-page brief for engineering leadership explaining the shift
toward multi-modal RAG and recommending whether to adopt now, pilot, or watch.

</details>
```

## Frontend Component Design

The `DigestPane` component renders each `DigestSection`. Below the existing details/themes, add:

```tsx
{section.followup_prompts?.length > 0 && (
  <Collapsible>
    <CollapsibleTrigger>
      Follow-up prompts ({section.followup_prompts.length})
    </CollapsibleTrigger>
    <CollapsibleContent>
      {section.followup_prompts.map((prompt, i) => (
        <div key={i} className="group relative">
          <p>{prompt}</p>
          <CopyButton text={prompt} />
        </div>
      ))}
    </CollapsibleContent>
  </Collapsible>
)}
```

Uses existing shadcn/ui `Collapsible` and clipboard API. No new dependencies.

## Prompt Generation Guidance

Added to the digest creation system prompt:

> For each insight/development/trend, generate 2-3 `followup_prompts`. Each prompt must be:
> - **Self-contained**: Includes enough context that the reader doesn't need to paste the entire digest
> - **Specific**: References concrete technologies, companies, or patterns from that section
> - **Action-oriented**: Asks the LLM to analyze implications, compare alternatives, generate plans, or evaluate risks
> - **Audience-aware**: Assumes a technical leader or senior engineer reader

Prompt variety guidelines to prevent repetitive structures:
- Mix analysis prompts ("Analyze how X impacts..."), comparison prompts ("Compare A vs B for..."), strategic prompts ("Draft a brief recommending..."), and implementation prompts ("Outline a migration plan from X to Y")
- Vary the scope: some prompts explore the topic broadly, others drill into specific implementation details
