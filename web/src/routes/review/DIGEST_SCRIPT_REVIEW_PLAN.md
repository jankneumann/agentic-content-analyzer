# Digest & Script Review Architecture

## Overview

This document outlines the architecture for implementing digest and script review pages, following the same pattern established in the summary review page.

## Data Relationships

```
Newsletters (1) ─────> (1) Summaries
                              │
                              │ (many summaries within period)
                              ▼
                         Digests (1) ─────> (1) Scripts
```

### Digest Review Challenge

A digest combines **many summaries** from a time period. The left pane needs to display multiple source summaries for comparison.

### Script Review

A script is generated from **one digest**. The left pane shows the digest content.

---

## Digest Review Page (`/review/digest/:id`)

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ ← Back to Digests    Review Digest    ◀ 2 of 8 ▶           │
├─────────────────────────────┬───────────────────────────────┤
│                             │                               │
│   SOURCE SUMMARIES          │   DIGEST                      │
│   ───────────────           │   ──────                      │
│                             │                               │
│   ┌───────────────────────┐ │   Executive Overview          │
│   │ ▼ Newsletter Title 1  │ │   ─────────────────           │
│   │   Executive summary...│ │   The digest covers...        │
│   │   • Key theme 1       │ │                               │
│   │   • Key theme 2       │ │   Strategic Insights          │
│   └───────────────────────┘ │   ─────────────────           │
│                             │   ▸ Section 1                 │
│   ┌───────────────────────┐ │   ▸ Section 2                 │
│   │ ▸ Newsletter Title 2  │ │                               │
│   └───────────────────────┘ │   Technical Developments      │
│                             │   ─────────────────────       │
│   ┌───────────────────────┐ │   ▸ Development 1             │
│   │ ▸ Newsletter Title 3  │ │                               │
│   └───────────────────────┘ │   Emerging Trends             │
│                             │   ───────────────             │
│   [scrollable]              │   [scrollable]                │
│                             │                               │
├─────────────────────────────┴───────────────────────────────┤
│ Feedback Panel (same as summary review)                     │
└─────────────────────────────────────────────────────────────┘
```

### Components

#### Left Pane: `SummariesListPane`
- Collapsible accordion of all source summaries
- Each summary shows:
  - Newsletter title (collapsible header)
  - Publication name
  - Executive summary
  - Key themes
- Selection enabled for adding context

#### Right Pane: `DigestPane`
- Collapsible sections for:
  - Executive Overview
  - Strategic Insights (expandable subsections)
  - Technical Developments (expandable subsections)
  - Emerging Trends (expandable subsections)
  - Actionable Recommendations (by audience)
  - Sources list (expandable)

### Data Fetching

```typescript
// 1. Fetch digest details
const { data: digest } = useDigest(digestId)

// 2. Fetch summaries within the digest's period
const { data: summaries } = useSummaries({
  start_date: digest.period_start,
  end_date: digest.period_end,
  limit: 100, // Get all summaries in period
})
```

### API Additions

**Backend:**
```python
# GET /api/v1/digests/{digest_id}/sources
# Returns all summaries used in creating this digest
@router.get("/{digest_id}/sources")
async def get_digest_sources(digest_id: int) -> list[SummaryListItem]:
    """Get all source summaries for a digest."""
```

**Frontend:**
```typescript
// hooks/use-digests.ts
export function useDigestSources(digestId: string) {
  return useQuery({
    queryKey: ["digest", digestId, "sources"],
    queryFn: () => fetchDigestSources(digestId),
  })
}
```

---

## Script Review Page (`/review/script/:id`)

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ ← Back to Scripts    Review Script    ◀ 1 of 3 ▶           │
├─────────────────────────────┬───────────────────────────────┤
│                             │                               │
│   SOURCE DIGEST             │   PODCAST SCRIPT              │
│   ─────────────             │   ──────────────              │
│                             │                               │
│   Executive Overview        │   Title: "AI Weekly..."       │
│   ─────────────────         │   Length: 8 min | 1,247 words │
│   The week in AI...         │                               │
│                             │   ┌─ INTRO ────────────────┐  │
│   Strategic Insights        │   │ ALEX: Welcome to...    │  │
│   ─────────────────         │   │ SAM: Thanks Alex...    │  │
│   ▸ Section 1 title         │   └────────────────────────┘  │
│   ▸ Section 2 title         │                               │
│                             │   ┌─ STRATEGIC ────────────┐  │
│   Technical Developments    │   │ ALEX: Let's dive...    │  │
│   ─────────────────────     │   │ SAM: The key point...  │  │
│                             │   │ [emphasized: excited]  │  │
│   [scrollable]              │   └────────────────────────┘  │
│                             │                               │
│                             │   [scrollable]                │
│                             │                               │
├─────────────────────────────┴───────────────────────────────┤
│ Feedback Panel (adapted for script sections)                │
└─────────────────────────────────────────────────────────────┘
```

### Components

#### Left Pane: `DigestPane` (reused)
- Same component as digest review right pane
- Shows the source digest content

#### Right Pane: `ScriptPane`
- Script metadata (title, length, word count, duration)
- Collapsible sections:
  - Intro
  - Strategic sections (one per insight)
  - Technical sections
  - Trend sections
  - Outro
- Each dialogue turn shows:
  - Speaker (ALEX / SAM) with styling
  - Text content
  - Emphasis indicator (if set)
  - Pause indicator (if set)

### Data Fetching

```typescript
// 1. Fetch script details
const { data: script } = useScript(scriptId)

// 2. Fetch source digest
const { data: digest } = useDigest(script.digest_id)
```

---

## Shared Components

### Reusable Across All Review Types

| Component | Summary Review | Digest Review | Script Review |
|-----------|---------------|---------------|---------------|
| `ReviewLayout` | ✓ | ✓ | ✓ |
| `ReviewHeader` | ✓ | ✓ | ✓ |
| `SelectionPopover` | ✓ | ✓ | ✓ |
| `FeedbackPanel` | ✓ | ✓ (adapted) | ✓ (adapted) |
| `ContextChip` | ✓ | ✓ | ✓ |
| `NewsletterPane` | ✓ | - | - |
| `SummaryPane` | ✓ | - | - |

### New Components Needed

| Component | Purpose |
|-----------|---------|
| `SummariesListPane` | Collapsible list of summaries for digest review |
| `DigestPane` | Structured digest content display |
| `ScriptPane` | Dialogue-formatted script display |
| `DialogueTurn` | Single speaker turn in script |

---

## File Structure

```
web/src/
├── components/review/
│   ├── index.ts           # Updated exports
│   ├── ReviewLayout.tsx   # Existing
│   ├── ReviewHeader.tsx   # Existing
│   ├── SelectionPopover.tsx
│   ├── FeedbackPanel.tsx  # Updated for type-specific behavior
│   ├── ContextChip.tsx
│   │
│   │ # Content-specific panes
│   ├── NewsletterPane.tsx # Existing (summary review)
│   ├── SummaryPane.tsx    # Existing (summary review)
│   ├── SummaryPreview.tsx # Existing (summary review)
│   │
│   │ # NEW: Digest/Script panes
│   ├── SummariesListPane.tsx   # Collapsible summaries list
│   ├── DigestPane.tsx          # Digest content display
│   ├── DigestPreview.tsx       # Regenerated digest preview
│   ├── ScriptPane.tsx          # Script dialogue display
│   ├── ScriptPreview.tsx       # Regenerated script preview
│   └── DialogueTurn.tsx        # Single dialogue turn
│
├── routes/
│   ├── review.tsx              # Parent route
│   └── review/
│       ├── summary.$id.tsx     # Existing
│       ├── digest.$id.tsx      # NEW
│       └── script.$id.tsx      # NEW
│
├── hooks/
│   ├── use-newsletters.ts      # Existing
│   ├── use-summaries.ts        # Existing
│   ├── use-digests.ts          # Add: useDigest, useDigestSources, useDigestNavigation
│   └── use-scripts.ts          # Add: useScript, useScriptNavigation
│
└── lib/api/
    ├── digests.ts              # Add: fetchDigestSources, regenerateDigestWithFeedback
    └── scripts.ts              # Add: regenerateScriptWithFeedback
```

---

## Implementation Order

### Phase 1: Digest Review (Priority)
1. Create `DigestPane` component
2. Create `SummariesListPane` component
3. Add backend endpoint for digest sources
4. Create `/review/digest/:id` route
5. Add "Review" button to digests list
6. Wire up feedback/regeneration flow

### Phase 2: Script Review
1. Create `ScriptPane` and `DialogueTurn` components
2. Create `/review/script/:id` route
3. Add "Review" button to scripts list
4. Wire up feedback/regeneration flow

### Phase 3: Polish
1. Add navigation between items
2. Keyboard shortcuts (Cmd+Enter to generate)
3. Mobile responsive layout (tabs instead of side-by-side)
4. Loading states and error handling

---

## Backend API Additions

### Digest Endpoints

```python
# GET /api/v1/digests/{digest_id}/sources
# Returns summaries used to create the digest

# POST /api/v1/digests/{digest_id}/regenerate-with-feedback
# Regenerates digest sections with feedback (SSE streaming)

# POST /api/v1/digests/{digest_id}/commit-preview
# Saves regenerated content

# GET /api/v1/digests/{digest_id}/navigation
# Returns prev/next digest IDs for navigation
```

### Script Endpoints

```python
# POST /api/v1/scripts/{script_id}/regenerate-with-feedback
# Regenerates script sections with feedback

# POST /api/v1/scripts/{script_id}/commit-preview
# Saves regenerated script

# GET /api/v1/scripts/{script_id}/navigation
# Returns prev/next script IDs for navigation
```

---

## Feedback Adaptation by Type

| Review Type | Context Source | Regeneration Scope |
|-------------|---------------|-------------------|
| Summary | Newsletter + Summary | Full summary |
| Digest | Summaries + Digest | Individual sections |
| Script | Digest + Script | Individual sections |

### Digest Feedback Panel
- Can target specific sections (strategic_insights[0], etc.)
- Section-specific regeneration option
- Full digest regeneration option

### Script Feedback Panel
- Can target specific sections (intro, strategic[0], outro, etc.)
- Section-specific dialogue regeneration
- Full script regeneration option
