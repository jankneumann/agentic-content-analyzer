# Revision Panel Redesign

**Date**: 2025-01-08
**PR**: [#9](https://github.com/jankneumann/agentic-newsletter-aggregator/pull/9)
**Status**: Completed

## Summary

Redesign the AI revision panel in the review pages to separate **chat** (asking questions with web search) from **regeneration** (explicit button click). The panel should be collapsible and include context chips for selected text.

---

## Requirements

1. **Collapsible panel** - Use CollapsibleChatPanel design pattern
2. **Separate chat from regeneration**:
   - Chat: Ask questions about content, enhanced with web search
   - Regeneration: Explicit "Generate Preview" button only
3. **Context chips** - Selected text snippets shown in panel
4. **Conversation as context** - When generating, use full chat history + context chips
5. **Preview flow** - Accept/reject generated preview before saving

---

## Component Design

### RevisionChatPanel (Redesigned)

The panel has three modes:
1. **Collapsed** - Minimal bar showing message count
2. **Expanded (Chat)** - Full chat with context chips and generate button
3. **Preview** - Shows accept/reject buttons

```
┌──────────────────────────────────────────────────────────────────┐
│ 💬 AI Assistant                              [Collapse] [Chat ▾]  │
├──────────────────────────────────────────────────────────────────┤
│ Context: [chip: "Lorem..."] [chip: "Theme 1..."] [× Clear All]   │
│          ↳ 847 / 2000 characters                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Messages area (scrollable)                                      │
│  - User: "What does this section mean?"                          │
│  - Assistant: "This section discusses..."                        │
│  - User: "Make it more concise"                                  │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│ [🔍 Web Search] [Input: Ask a question...          ] [Send ➤]   │
├──────────────────────────────────────────────────────────────────┤
│                              [✨ Generate Preview]               │
└──────────────────────────────────────────────────────────────────┘
```

### Preview State

```
┌──────────────────────────────────────────────────────────────────┐
│ 💬 AI Assistant                                        [Collapse] │
├──────────────────────────────────────────────────────────────────┤
│  Preview generated using:                                        │
│  - 3 chat messages as context                                    │
│  - 2 selected text snippets                                      │
│                                                                  │
│  Review the changes in the right pane.                           │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│            [✗ Reject] [↻ Try Again] [✓ Accept & Save]           │
└──────────────────────────────────────────────────────────────────┘
```

### Key Behaviors

| Action | What Happens |
|--------|--------------|
| Send chat message | AI responds (with optional web search), NO regeneration |
| Click "Generate Preview" | Uses conversation + context to regenerate artifact |
| Accept preview | Commits changes, clears chat & context |
| Reject preview | Returns to chat mode, preserves history |
| Try Again | Reject + immediately generate new preview |

---

## Files Modified

| File | Changes |
|------|---------|
| `web/src/components/chat/RevisionChatPanel.tsx` | Redesigned to separate chat from regeneration, added collapsible UI |
| `web/src/routes/review/summary.$id.tsx` | Updated to use new panel design with separate chat/generate handlers |
| `web/src/routes/review/digest.$id.tsx` | Updated to use new panel design |
| `web/src/routes/review/script.$id.tsx` | Updated to use new panel design |

## New Files Created

| File | Purpose |
|------|---------|
| `web/src/components/ui/toggle.tsx` | Toggle component from shadcn/ui for web search toggle |

---

## Implementation Details

### RevisionChatPanel Props

```typescript
interface RevisionChatPanelProps {
  // Existing
  messages: ChatMessage[]
  isStreaming?: boolean
  streamingContent?: string
  error?: Error | null
  artifactType?: ArtifactType

  // Chat handlers (separate from regeneration)
  onSendMessage: (content: string, options?: { enableWebSearch?: boolean }) => void

  // Regeneration handlers (explicit button)
  onGeneratePreview: () => void
  isGenerating?: boolean

  // Preview mode
  isPreviewMode?: boolean
  onAcceptPreview?: () => void
  onRejectPreview?: () => void
  isAccepting?: boolean

  // Collapsible
  isExpanded: boolean
  onToggle: () => void
}
```

### Key Implementation Decisions

1. **Separation of concerns**: `onSendMessage` handles chat Q&A, `onGeneratePreview` handles regeneration
2. **Web search toggle**: Users can enable/disable web search for chat responses
3. **Conversation as context**: When generating, all user messages are concatenated as feedback
4. **Context chips integration**: Uses existing `ReviewContext` for selected text snippets

---

## API Usage

### Chat (questions, no regeneration)
```typescript
// Local state for now, will integrate with chat API
onSendMessage(content, { enableWebSearch: true })
// Adds user message, simulates AI response
```

### Generate Preview (explicit button click)
```typescript
// Uses existing regenerate API
POST /api/summaries/{id}/regenerate
{
  "feedback": "concatenated user messages",
  "context_selections": [...],
  "preview_only": true
}
```

---

## Future Work

- Wire up chat API for actual Q&A responses with web search
- Implement digest regeneration endpoint
- Implement script regeneration endpoint
- Persist chat history via API
