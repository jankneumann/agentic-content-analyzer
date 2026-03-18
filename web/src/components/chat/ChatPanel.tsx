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
  onSendMessage: (
    content: string,
    options?: { enableWebSearch?: boolean }
  ) => void
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
      <ScrollArea ref={scrollRef} className={cn("flex-1", messagesClassName)}>
        <div className="py-4">
          {/* Loading state */}
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
            </div>
          )}

          {/* Empty state */}
          {!isLoading && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="bg-muted rounded-full p-4">
                <MessageSquare className="text-muted-foreground h-8 w-8" />
              </div>
              <h3 className="mt-4 text-lg font-medium">Start a conversation</h3>
              <p className="text-muted-foreground mt-2 max-w-sm text-sm">
                Ask for revisions, clarifications, or improvements to the
                content. The AI will help refine it based on your feedback.
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
        <div className="bg-destructive/10 text-destructive border-t px-4 py-2 text-sm">
          {error.message || "An error occurred"}
        </div>
      )}

      {/* Input area */}
      <div className="bg-background border-t p-4">
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
  const panelId = React.useId()

  if (!isExpanded) {
    return (
      <button
        type="button"
        aria-expanded={isExpanded}
        aria-controls={panelId}
        onClick={onToggle}
        className="bg-card hover:bg-muted/50 focus-visible:ring-ring flex w-full items-center justify-between rounded-lg border p-4 text-left transition-colors focus-visible:ring-2 focus-visible:outline-none"
      >
        <div className="flex items-center gap-3">
          <div className="bg-primary/10 rounded-full p-2">
            <MessageSquare className="text-primary h-4 w-4" />
          </div>
          <div>
            <h3 className="font-medium">{title}</h3>
            <p className="text-muted-foreground text-sm">
              {props.messages.length > 0
                ? `${props.messages.length} messages`
                : "Click to start a conversation"}
            </p>
          </div>
        </div>
        <span className="text-muted-foreground text-sm">Expand</span>
      </button>
    )
  }

  return (
    <div id={panelId} className="bg-card flex flex-col rounded-lg border">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <MessageSquare className="text-primary h-4 w-4" />
          <h3 className="font-medium">{title}</h3>
        </div>
        <button
          type="button"
          aria-expanded={isExpanded}
          aria-controls={panelId}
          onClick={onToggle}
          className="text-muted-foreground hover:text-foreground focus-visible:ring-ring rounded-sm text-sm focus-visible:ring-2 focus-visible:outline-none"
        >
          Collapse
        </button>
      </div>

      {/* Chat content */}
      <ChatPanel {...props} className="h-[400px]" />
    </div>
  )
}
