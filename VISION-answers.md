# VISION.md review answers

Author: Jan Neumann (repository owner). Verdicts arrive through the host question tool; the review board (`VISION-review.html`) is the reading surface only.

## Round 1 (H-1, H-2, H-3)

### H-1 - Drop the Comcast-leadership framing and name it a general platform

Verdict: **In vision**

Reasoning (verbatim): "trend analysis and leadership advice is still my main goal of this repo, but as I made it public on GitHub and the focus is described by customizable prompts I think if it more as a general management system for both external curated knowledge and extraction of knowledge from memories and observations."

Principles distilled:
- The core purpose stays trend analysis and leadership advice; the audience widens because the repository is public.
- The system is a general knowledge-management system with two inputs: externally curated content and knowledge extracted from memories and observations.
- Domain focus lives in customizable prompts, not in code.

### H-2 - Reach for the specialist-agent framework inside a narrow feature

Verdict: **In vision**

Reasoning (verbatim): "the vision is to be as deterministic as possible, as agentic / adaptive as possible, so a combination of deterministic pipeline structures with agentic specialists that provide scalable judgement and escalation to human decisions where needed is my vision"

Principles distilled:
- Pipeline structure is deterministic.
- Agentic specialists supply scalable judgment inside that structure.
- Judgment that should not be made alone escalates to a human decision.

### H-3 - Add WAL archiving now for near-zero recovery point objective

Verdict: **Off mission**

Reasoning (verbatim): "we want to find the right balance between evolutionary design and building for our current scale, where we favor simplicity with in clean abstractions that allow for more complexity when it is needed"

Principles distilled:
- No permanent stance on any one recovery mechanism; the durable principle is evolutionary design.
- Build for current scale; favor simplicity.
- Keep abstractions clean so added complexity is an addition, not a rewrite.

## Round 2 (H-4, H-5, H-6)

### H-4 - Prefer explicit provider configuration over auto-detection

Verdict: **In vision**

Reasoning (verbatim): "database providers have a major impact on the capabilities and the build process. Choosing them explicitly and intentionally is worth the effort to create alignment through the stack"

Principles distilled:
- A provider that shapes capabilities or the build is chosen explicitly and intentionally, never inferred.
- The explicit choice is what creates alignment through the stack.
- The add-neon-provider "less DX-friendly" rejection of explicit config is reversed for capability-shaping providers.

### H-5 - Build a compatibility adapter for a specific broken external consumer

Verdict: **In vision**

Reasoning (verbatim): "generally I prefer to introduce thin abstraction layers so individual modules can be changed in line with contracts but as the tool is being used by others we will need to move to more standard revision and upgrade mechanisms"

Principles distilled:
- Thin abstraction layers with contracts, so a module can change in line with its contract.
- Because others use the tool, external consumers are served through standard revision and upgrade mechanisms rather than ad hoc refusals or ad hoc shims.
- An adapter is acceptable as a standard, versioned, dated mechanism; what is refused is the unversioned, undated one.

### H-6 - Accept a vendor-specific build risk to avoid a heavier self-hosted service

Verdict: **In vision**

Reasoning (verbatim): "each provider we choose will need dedicated build paths , so again choosing thin abstractions will make it easier to find the right tradeoff between specific provider capabilities and using repeatable and portable patterns"

Principles distilled:
- Each chosen provider gets a dedicated build path.
- Thin abstractions are what make the trade between provider-specific capability and portable, repeatable patterns decidable case by case.
- Vendor neutrality means the stack outside the adapter does not learn the provider's name; it does not mean refusing provider-specific capability.

## Changelog

- H-1 In vision -> identity opener rewritten: purpose is "trend analysis and leadership advice"; audience is "technical leaders and practitioners first, and anyone who points it at their own sources and prompts"; the owned surface now includes "external content, memories, and observations"; Scope gains "It is not a system whose domain is fixed in code".
- H-2 In vision -> the "Every mutation is durable by construction" section is replaced by "The structure is deterministic and durable, the judgment is agentic, the decisions are human", keeping the durable-queue lines and adding the deterministic-structure, specialist-judgment, approval-gate, and focused-lookup lines; closing test gains "lets a model decide what the pipeline runs next".
- H-3 Off mission -> no WAL-specific line; new section "Built for today's scale, behind abstractions that can carry tomorrow's"; closing tests gain "is sized to the scale that exists" and "adds a subsystem for a scale that has not arrived".
- H-4 In vision -> vendor section retitled "Providers are chosen explicitly and held behind thin abstractions"; new line "A provider that shapes capabilities or the build is named explicitly in configuration, never inferred from other settings"; closing test gains "infers a provider instead of naming it".
- H-5 In vision -> the compatibility line in the history section now reads "served through standard revision and upgrade mechanisms: versioned contracts, compatibility windows stated in writing, and thin adapters that carry a retirement date", and "retired contract shapes do not quietly come back as an adapter" becomes "does not come back unversioned, undated, or by accident"; scale section gains "Boundaries between modules are thin abstraction layers with a contract".
- H-6 In vision -> "A design that trades a portable option for a vendor's proprietary feature is rejected unless the portable option is proven not viable" is replaced by "Each provider gets a dedicated build path behind the same thin abstraction, so a provider-specific capability can be used where it earns its place without the rest of the stack learning that provider's name"; closing tests swap "keeps a vendor swappable" for "keeps a provider behind its abstraction" and "hardcodes a single vendor's feature" for "teaches the stack a vendor's name outside its adapter".
