/**
 * ChatPanel Component
 *
 * Main chat interface for AI revision conversations.
 * Combines message list, streaming display, and input.
 *
 * Features:
 * - Message history display
 * - Real-time streaming of assistant responses
 * - Auto-scroll to latest message
 * - Loading states
 * - Empty state
 */

import * as React from "react"
import { MessageSquare, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ChatMessage, StreamingMessage, TypingIndicator } from "./ChatMessage"
import { ChatInput } from "./ChatInput"
import type { ChatMessage as ChatMessageType, ArtifactType } from "@/types"

interface ChatPanelProps {
  /** Array of messages to display */
  messages: ChatMessageType[]
  /** Whether the chat is loading initial data */
  isLoading?: boolean
  /** Whether a message is currently being streamed */
  isStreaming?: boolean
  /** Content being streamed (for assistant's response) */
  streamingContent?: string
  /** Error to display */
  error?: Error | null
  /** Callback when user sends a message */
  onSendMessage: (content: string, options?: { enableWebSearch?: boolean }) => void
  /** Callback to regenerate last response */
  onRegenerate?: () => void
  /** Artifact type for context */
  artifactType?: ArtifactType
  /** Whether web search is available */
  webSearchEnabled?: boolean
  /** Maximum message length */
  maxMessageLength?: number
  /** Additional CSS classes for the container */
  className?: string
  /** Additional CSS classes for the messages area */
  messagesClassName?: string
}

export function ChatPanel({
  messages,
  isLoading = false,
  isStreaming = false,
  streamingContent = "",
  error,
  onSendMessage,
  artifactType = "summary",
  webSearchEnabled = false,
  maxMessageLength = 2000,
  className,
  messagesClassName,
}: ChatPanelProps) {
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const messagesEndRef = React.useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages or streaming content
  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streamingContent])

  // Get placeholder based on artifact type
  const placeholder = React.useMemo(() => {
    switch (artifactType) {
      case "summary":
        return "How can I improve this summary?"
      case "digest":
        return "What changes should I make to this digest?"
      case "script":
        return "How can I enhance this script?"
      default:
        return "Type a message..."
    }
  }, [artifactType])

  return (
    <div className={cn("flex h-full flex-col", className)}>
      {/* Messages area */}
      <ScrollArea
        ref={scrollRef}
        className={cn("flex-1", messagesClassName)}
      >
        <div className="py-4">
          {/* Loading state */}
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {/* Empty state */}
          {!isLoading && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="rounded-full bg-muted p-4">
                <MessageSquare className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="mt-4 text-lg font-medium">Start a conversation</h3>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                Ask for revisions, clarifications, or improvements to the content.
                The AI will help refine it based on your feedback.
              </p>
            </div>
          )}

          {/* Messages list */}
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}

          {/* Streaming message */}
          {isStreaming && streamingContent && (
            <StreamingMessage content={streamingContent} />
          )}

          {/* Typing indicator (when streaming but no content yet) */}
          {isStreaming && !streamingContent && <TypingIndicator />}

          {/* Scroll anchor */}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Error message */}
      {error && (
        <div className="border-t bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {error.message || "An error occurred"}
        </div>
      )}

      {/* Input area */}
      <div className="border-t bg-background p-4">
        <ChatInput
          onSubmit={onSendMessage}
          isLoading={isStreaming}
          placeholder={placeholder}
          webSearchEnabled={webSearchEnabled}
          maxLength={maxMessageLength}
        />
      </div>
    </div>
  )
}

/**
 * Collapsible chat panel variant
 *
 * Can be minimized to save space in the review UI.
 */
interface CollapsibleChatPanelProps extends ChatPanelProps {
  /** Whether the panel is expanded */
  isExpanded: boolean
  /** Callback to toggle expansion */
  onToggle: () => void
  /** Title for the collapsed state */
  title?: string
}

export function CollapsibleChatPanel({
  isExpanded,
  onToggle,
  title = "AI Assistant",
  ...props
}: CollapsibleChatPanelProps) {
  if (!isExpanded) {
    return (
      <button
        type="button"
        aria-expanded={isExpanded}
        onClick={onToggle}
        className="flex w-full items-center justify-between rounded-lg border bg-card p-4 text-left transition-colors hover:bg-muted/50"
      >
        <div className="flex items-center gap-3">
          <div className="rounded-full bg-primary/10 p-2">
            <MessageSquare className="h-4 w-4 text-primary" />
          </div>
          <div>
            <h3 className="font-medium">{title}</h3>
            <p className="text-sm text-muted-foreground">
              {props.messages.length > 0
                ? `${props.messages.length} messages`
                : "Click to start a conversation"}
            </p>
          </div>
        </div>
        <span className="text-sm text-muted-foreground">Expand</span>
      </button>
    )
  }

  return (
    <div className="flex flex-col rounded-lg border bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-primary" />
          <h3 className="font-medium">{title}</h3>
        </div>
        <button
          type="button"
          aria-expanded={isExpanded}
          onClick={onToggle}
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          Collapse
        </button>
      </div>

      {/* Chat content */}
      <ChatPanel {...props} className="h-[400px]" />
    </div>
  )
}
