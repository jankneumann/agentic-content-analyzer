# Chat Context Injection and Conversation Persistence

**Date**: 2025-01-09
**Status**: Completed
**PR**: TBD

## Overview

This plan covers two related features for the AI revision chat in review pages:
1. **Context Injection**: Inject artifact content (newsletter, summary, digest, script) into the LLM context
2. **Conversation Persistence**: Persist chat conversations so users can continue where they left off

---

## Problem 1: Missing Context

The chat in review pages didn't have access to the actual content being reviewed. The LLM received:
1. A generic system prompt
2. Conversation history
3. **NO actual artifact content**

Result: Generic responses because the LLM had nothing to reference.

### Solution

Inject artifact content into the system prompt when generating responses.

### Files Modified

| File | Changes |
|------|---------|
| `src/api/chat_routes.py` | Added `get_artifact_content()` helper, inject content into system prompt |
| `src/config/prompts.yaml` | Updated prompts to reference "Content Being Reviewed" section |

### Implementation Details

```python
def get_artifact_content(db, artifact_type: str, artifact_id: int) -> str:
    """Fetch and format artifact content for LLM context."""
    if artifact_type == "summary":
        # Fetch newsletter + summary, format with 10k char limit
    elif artifact_type == "digest":
        # Fetch digest with all sections
    elif artifact_type == "script":
        # Fetch script with 15k char limit
    return formatted_content
```

The content is injected into the system prompt:
```python
system_prompt = f"""{base_prompt}

## Content Being Reviewed

{artifact_content}
"""
```

### Debug Feature

Added a debug endpoint and UI button to view what context is sent to the LLM:
- `GET /api/v1/chat/conversations/{id}/context` - Returns full context
- Bug icon button in RevisionChatPanel header

---

## Problem 2: Lost Conversations

When users returned to a review page, previous chat conversations were lost. The chat started fresh every time.

### Root Cause

Review pages managed chat state manually instead of using the existing `useChatSession` hook which already handles conversation persistence.

### Solution

Replace manual conversation state management with `useChatSession` hook.

### Files Modified

| File | Changes |
|------|---------|
| `web/src/routes/review/summary.$id.tsx` | Use `useChatSession` hook |
| `web/src/routes/review/digest.$id.tsx` | Use `useChatSession` hook |
| `web/src/routes/review/script.$id.tsx` | Use `useChatSession` hook |

### Before (Manual State)

```typescript
const [messages, setMessages] = React.useState<ChatMessage[]>([])
const [conversationId, setConversationId] = React.useState<string | null>(null)
const [isStreaming, setIsStreaming] = React.useState(false)
// ... more manual state

const handleSendMessage = async (content: string) => {
  let convId = conversationId
  if (!convId) {
    const conversation = await createConversation({...})
    convId = conversation.id
    setConversationId(convId)
  }
  // Manual streaming handling...
}
```

### After (Using Hook)

```typescript
const chat = useChatSession("summary", summaryId.toString())

React.useEffect(() => {
  if (chat.hasConversation && !chat.conversationId) {
    chat.startOrContinue()
  }
}, [chat.hasConversation, chat.conversationId, chat.startOrContinue])

const handleSendMessage = async (content: string) => {
  await chat.send(content, { model: selectedModel })
}

// Use: chat.messages, chat.isStreaming, chat.streamingContent, chat.error
```

---

## Issue: Navigation Not Reloading Conversations

When using prev/next navigation buttons, the conversation didn't reload - it kept showing the old conversation.

### Root Cause

React doesn't remount components when only props change. The `useChatSession` hook was initialized with the original artifact ID and didn't reinitialize when navigating.

### Solution

Add a `key` prop to force component remount when artifact ID changes:

```tsx
<ReviewContent
  key={summary.id}  // Forces remount on navigation
  summary={summary}
  // ...
/>
```

---

## UX Improvement: Collapsed Panel by Default

Changed the chat panel to start collapsed for a cleaner initial view:

```typescript
// Before
const [isPanelExpanded, setIsPanelExpanded] = React.useState(true)

// After
const [isPanelExpanded, setIsPanelExpanded] = React.useState(false)
```

---

## Lessons Learned

### 1. React Key Prop for Component Reset

When a component needs to fully reset its state based on a prop change (like navigating between items), use a `key` prop instead of complex `useEffect` logic:

```tsx
// Instead of this (complex, error-prone):
useEffect(() => {
  resetAllState()
}, [itemId])

// Do this (simple, reliable):
<Component key={itemId} item={item} />
```

### 2. Prefer Existing Hooks Over Manual State

Before implementing manual state management, check if existing hooks already handle the use case. The `useChatSession` hook already had:
- Conversation fetching by artifact
- Automatic conversation loading
- Streaming state management
- Error handling

### 3. Merge Local and Persisted State

For the summary page with preview mode, we needed both:
- Persisted messages from `chat.messages`
- Local system messages (accept/reject feedback)

Solution: Merge and sort by timestamp:
```typescript
const allMessages = React.useMemo(() => {
  return [...chat.messages, ...systemMessages].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  )
}, [chat.messages, systemMessages])
```

### 4. Token Considerations for Context

Content injected into LLM context needs limits:
- Newsletter content: ~10,000 chars
- Script content: ~15,000 chars
- Consider model context windows (200k Claude, 1M Gemini)

---

## Backend Infrastructure (Already Existed)

No backend changes were needed for persistence:
- Conversations are persisted to database
- `GET /conversations?artifact_type=X&artifact_id=Y` endpoint exists
- Conversations returned ordered by most recent

The context injection required backend changes to fetch and format artifact content.
