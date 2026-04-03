/**
 * ChatMessage Component
 *
 * Displays an individual chat message with:
 * - Role indicator (user/assistant)
 * - Message content with markdown support
 * - Timestamp
 * - Metadata (model, tokens, etc.)
 */

import { memo } from "react"
import { User, Bot, Clock, Zap, Globe } from "lucide-react"
import { cn } from "@/lib/utils"
import { CopyButton } from "@/components/ui/copy-button"
import type { ChatMessage as ChatMessageType } from "@/types"

interface ChatMessageProps {
  /** The message to display */
  message: ChatMessageType
  /** Whether this message is currently streaming */
  isStreaming?: boolean
  /** Additional CSS classes */
  className?: string
}

/**
 * Format timestamp to relative or absolute time
 */
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return "Just now"
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

/**
 * Individual chat message component.
 *
 * Memoized to prevent unnecessary re-renders of history messages
 * when parent renders (e.g., during streaming of new messages).
 */
export const ChatMessage = memo(function ChatMessage({
  message,
  isStreaming,
  className,
}: ChatMessageProps) {
  const isUser = message.role === "user"
  const isAssistant = message.role === "assistant"

  return (
    <div
      className={cn(
        "group flex gap-3 px-4 py-3",
        isUser && "flex-row-reverse",
        className
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Message content */}
      <div
        className={cn("flex max-w-[80%] flex-col gap-1", isUser && "items-end")}
      >
        {/* Message bubble */}
        <div
          className={cn(
            "rounded-2xl px-4 py-2",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-foreground",
            isStreaming && "animate-pulse"
          )}
        >
          {/* Content - could add markdown rendering here */}
          <div className="text-sm whitespace-pre-wrap">
            {message.content}
            {isStreaming && (
              <span className="ml-1 inline-block h-4 w-1 animate-pulse bg-current" />
            )}
          </div>
        </div>

        {/* Metadata row */}
        <div
          className={cn(
            "text-muted-foreground flex items-center gap-2 text-xs opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100",
            isUser && "flex-row-reverse"
          )}
        >
          {/* Timestamp */}
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatTimestamp(message.timestamp)}
          </span>

          {/* Assistant-specific metadata */}
          {isAssistant && message.metadata && (
            <>
              {message.metadata.model && (
                <span className="bg-muted/50 rounded px-1.5 py-0.5">
                  {message.metadata.model}
                </span>
              )}
              {message.metadata.tokenUsage && (
                <span className="flex items-center gap-1">
                  <Zap className="h-3 w-3" />
                  {message.metadata.tokenUsage}
                </span>
              )}
              {message.metadata.webSearchUsed && (
                <span className="flex items-center gap-1 text-blue-500">
                  <Globe className="h-3 w-3" />
                  Web
                </span>
              )}
            </>
          )}

          {/* Copy Button */}
          {!isStreaming && (
            <CopyButton content={message.content} className="h-6 w-6" />
          )}
        </div>
      </div>
    </div>
  )
})

/**
 * Streaming message placeholder
 *
 * Shows partial content while streaming is in progress.
 */
interface StreamingMessageProps {
  /** Content accumulated so far */
  content: string
  /** Optional class name */
  className?: string
}

export function StreamingMessage({
  content,
  className,
}: StreamingMessageProps) {
  return (
    <ChatMessage
      message={{
        id: "streaming",
        role: "assistant",
        content,
        timestamp: new Date().toISOString(),
      }}
      isStreaming={true}
      className={className}
    />
  )
}

/**
 * Typing indicator for when assistant is thinking
 */
export function TypingIndicator({ className }: { className?: string }) {
  return (
    <div
      className={cn("flex gap-3 px-4 py-3", className)}
      role="status"
      aria-live="polite"
      aria-label="Assistant is thinking"
    >
      <div
        className="bg-muted text-muted-foreground flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
        aria-hidden="true"
      >
        <Bot className="h-4 w-4" />
      </div>
      <div
        className="bg-muted flex items-center gap-1 rounded-2xl px-4 py-2"
        aria-hidden="true"
      >
        <span className="bg-muted-foreground h-2 w-2 animate-bounce rounded-full [animation-delay:0ms]" />
        <span className="bg-muted-foreground h-2 w-2 animate-bounce rounded-full [animation-delay:150ms]" />
        <span className="bg-muted-foreground h-2 w-2 animate-bounce rounded-full [animation-delay:300ms]" />
      </div>
      <span className="sr-only">Assistant is thinking...</span>
    </div>
  )
}
