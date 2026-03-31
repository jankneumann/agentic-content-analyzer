/**
 * RevisionChatPanel Component
 *
 * Collapsible AI revision interface that separates:
 * - Chat: Ask questions about content (with optional web search)
 * - Regeneration: Explicit button to generate preview using conversation as context
 *
 * Features:
 * - Collapsible panel design
 * - Context chips for selected text snippets
 * - Chat messages with web search capability
 * - Separate "Generate Preview" button
 * - Preview accept/reject flow
 */

import * as React from "react"
import {
  MessageSquare,
  Loader2,
  Sparkles,
  Check,
  X,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  Search,
  Bug,
} from "lucide-react"
import { API_BASE_URL } from "@/lib/api/client"
import { cn } from "@/lib/utils"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Toggle } from "@/components/ui/toggle"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ChatMessage, StreamingMessage, TypingIndicator } from "./ChatMessage"
import { CopyButton } from "@/components/ui/copy-button"
import { ContextChipList } from "@/components/review/ContextChip"
import { useReviewContext } from "@/contexts/ReviewContext"
import { REVIEW_LIMITS } from "@/types/review"
import type { ChatMessage as ChatMessageType, ArtifactType } from "@/types"

/** Model info for the model selector */
interface ChatModelInfo {
  id: string
  name: string
  provider: string
}

/** Debug context response from the API */
interface DebugContextData {
  system_prompt: string
  artifact_content: string
  full_context: string
  artifact_type: string
  artifact_id: number
  message_count: number
}

interface RevisionChatPanelProps {
  /** Array of messages to display */
  messages: ChatMessageType[]
  /** Whether the chat is loading initial data */
  isLoading?: boolean
  /** Whether a chat message is currently being streamed */
  isStreaming?: boolean
  /** Content being streamed (for assistant's response) */
  streamingContent?: string
  /** Error to display */
  error?: Error | null
  /** Callback when user sends a chat message (for questions, NOT regeneration) */
  onSendMessage: (
    content: string,
    options?: { enableWebSearch?: boolean; model?: string }
  ) => void
  /** Callback when user clicks "Generate Preview" button */
  onGeneratePreview: () => void
  /** Whether preview generation is in progress */
  isGenerating?: boolean
  /** Artifact type for context */
  artifactType?: ArtifactType
  /** Whether we're in preview mode (showing generated preview) */
  isPreviewMode?: boolean
  /** Callback to accept preview */
  onAcceptPreview?: () => void
  /** Callback to reject preview */
  onRejectPreview?: () => void
  /** Whether accepting is in progress */
  isAccepting?: boolean
  /** Whether the panel is expanded */
  isExpanded: boolean
  /** Callback to toggle expansion */
  onToggle: () => void
  /** Maximum message length */
  maxMessageLength?: number
  /** Additional CSS classes for the container */
  className?: string
  /** Currently selected model */
  selectedModel?: string
  /** Callback when model changes */
  onModelChange?: (model: string) => void
  /** Available models for selection */
  availableModels?: ChatModelInfo[]
  /** Conversation ID for debug context (optional) */
  conversationId?: string | null
}

export function RevisionChatPanel({
  messages,
  isLoading = false,
  isStreaming = false,
  streamingContent = "",
  error,
  onSendMessage,
  onGeneratePreview,
  isGenerating = false,
  artifactType = "summary",
  isPreviewMode = false,
  onAcceptPreview,
  onRejectPreview,
  isAccepting = false,
  isExpanded,
  onToggle,
  maxMessageLength = 2000,
  className,
  selectedModel,
  onModelChange,
  availableModels,
  conversationId,
}: RevisionChatPanelProps) {
  const [input, setInput] = React.useState("")
  const [webSearchEnabled, setWebSearchEnabled] = React.useState(false)
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const messagesEndRef = React.useRef<HTMLDivElement>(null)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)
  const charCountId = React.useId()

  // Debug context state
  const [debugDialogOpen, setDebugDialogOpen] = React.useState(false)
  const [debugContext, setDebugContext] =
    React.useState<DebugContextData | null>(null)
  const [isLoadingDebug, setIsLoadingDebug] = React.useState(false)

  // Get context from ReviewContext
  const {
    contextItems,
    removeContextItem,
    clearAllContext,
    totalContextChars,
  } = useReviewContext()

  // Auto-scroll to bottom on new messages or streaming content
  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streamingContent])

  // Get placeholder based on artifact type
  const placeholder = React.useMemo(() => {
    switch (artifactType) {
      case "summary":
        return "Ask about the content or summary..."
      case "digest":
        return "Ask about the digest or source summaries..."
      case "script":
        return "Ask about the script or source digest..."
      default:
        return "Ask a question..."
    }
  }, [artifactType])

  const canSubmit = input.trim().length > 0 && !isStreaming && !isPreviewMode
  const canGenerate = !isStreaming && !isGenerating && !isPreviewMode

  // Handle chat message submission
  const handleSubmit = React.useCallback(
    (e?: React.MouseEvent | React.KeyboardEvent) => {
      if (!canSubmit) {
        if (e) e.preventDefault()
        return
      }

      onSendMessage(input.trim(), {
        enableWebSearch: webSearchEnabled,
        model: selectedModel,
      })
      setInput("")

      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto"
      }
    },
    [canSubmit, input, webSearchEnabled, selectedModel, onSendMessage]
  )

  // Handle keyboard shortcuts
  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        handleSubmit(e)
      }
    },
    [handleSubmit]
  )

  // Auto-resize textarea
  const handleChange = React.useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = e.target.value
      if (newValue.length <= maxMessageLength) {
        setInput(newValue)
      }

      // Auto-resize
      const textarea = e.target
      textarea.style.height = "auto"
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`
    },
    [maxMessageLength]
  )

  // Handle "Try Again" - reject and immediately generate new preview
  const handleTryAgain = React.useCallback(() => {
    onRejectPreview?.()
    // Small delay to allow state to update before generating
    setTimeout(() => onGeneratePreview(), 100)
  }, [onRejectPreview, onGeneratePreview])

  const handleGeneratePreview = React.useCallback(
    (e?: React.MouseEvent | React.KeyboardEvent) => {
      if (!canGenerate) {
        if (e) e.preventDefault()
        return
      }
      onGeneratePreview()
    },
    [canGenerate, onGeneratePreview]
  )

  // Handle fetching debug context
  const handleFetchDebugContext = React.useCallback(async () => {
    if (!conversationId) return

    setIsLoadingDebug(true)
    setDebugDialogOpen(true)

    try {
      const response = await fetch(
        `${API_BASE_URL}/chat/conversations/${conversationId}/context`
      )
      if (!response.ok) {
        throw new Error(`Failed to fetch context: ${response.statusText}`)
      }
      const data = await response.json()
      setDebugContext(data)
    } catch (err) {
      console.error("Error fetching debug context:", err)
      setDebugContext(null)
    } finally {
      setIsLoadingDebug(false)
    }
  }, [conversationId])

  // Generate tooltip text based on state
  const generatePreviewTooltip = React.useMemo(() => {
    if (isStreaming) return "Please wait for the response to finish"
    if (isGenerating) return "Preview is currently generating"
    if (isPreviewMode) return "Please accept or reject the current preview"
    return "Generate a preview based on the chat context"
  }, [isStreaming, isGenerating, isPreviewMode])

  const panelId = React.useId()

  // Collapsed state
  if (!isExpanded) {
    return (
      <button
        type="button"
        aria-expanded={isExpanded}
        aria-controls={panelId}
        onClick={onToggle}
        className={cn(
          "bg-card hover:bg-muted/50 focus-visible:ring-ring flex w-full items-center justify-between rounded-lg border p-4 text-left transition-colors focus-visible:ring-2 focus-visible:outline-none",
          className
        )}
      >
        <div className="flex items-center gap-3">
          <div className="bg-primary/10 rounded-full p-2">
            <MessageSquare className="text-primary h-4 w-4" />
          </div>
          <div>
            <h3 className="font-medium">AI Assistant</h3>
            <p className="text-muted-foreground text-sm">
              {messages.length > 0
                ? `${messages.length} message${messages.length !== 1 ? "s" : ""}`
                : "Ask questions or generate revisions"}
              {contextItems.length > 0 &&
                ` · ${contextItems.length} selection${contextItems.length !== 1 ? "s" : ""}`}
            </p>
          </div>
        </div>
        <ChevronDown className="text-muted-foreground h-4 w-4" />
      </button>
    )
  }

  // Expanded state
  return (
    <div
      id={panelId}
      className={cn("bg-card flex flex-col rounded-lg border", className)}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <MessageSquare className="text-primary h-4 w-4" />
          <h3 className="font-medium">AI Assistant</h3>
          {messages.length > 0 && (
            <span className="text-muted-foreground text-xs">
              ({messages.length} message{messages.length !== 1 ? "s" : ""})
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Debug context button - only show when conversation exists */}
          {conversationId && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleFetchDebugContext}
                  className="h-7 w-7 p-0"
                >
                  <Bug className="text-muted-foreground h-4 w-4" />
                  <span className="sr-only">View LLM context</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>View LLM context</TooltipContent>
            </Tooltip>
          )}
          <button
            type="button"
            aria-expanded={isExpanded}
            aria-controls={panelId}
            onClick={onToggle}
            className="text-muted-foreground hover:text-foreground focus-visible:ring-ring flex items-center gap-1 rounded-sm text-sm focus-visible:ring-2 focus-visible:outline-none"
          >
            Collapse
            <ChevronUp className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Context chips (if any selected) */}
      {contextItems.length > 0 && (
        <div className="border-b px-4 py-3">
          <ContextChipList
            items={contextItems}
            onRemove={removeContextItem}
            onClearAll={clearAllContext}
            maxChars={REVIEW_LIMITS.MAX_TOTAL_CONTEXT_CHARS}
            usedChars={totalContextChars}
          />
        </div>
      )}

      {/* Preview mode content */}
      {isPreviewMode ? (
        <>
          <div className="px-4 py-6 text-center">
            <div className="bg-primary/10 mx-auto mb-3 w-fit rounded-full p-3">
              <Sparkles className="text-primary h-5 w-5" />
            </div>
            <h4 className="font-medium">Preview Generated</h4>
            <p className="text-muted-foreground mt-1 text-sm">
              {messages.length > 0 && (
                <span>
                  {messages.length} message{messages.length !== 1 ? "s" : ""}{" "}
                  used as context
                </span>
              )}
              {messages.length > 0 && contextItems.length > 0 && " · "}
              {contextItems.length > 0 && (
                <span>
                  {contextItems.length} text selection
                  {contextItems.length !== 1 ? "s" : ""}
                </span>
              )}
            </p>
            <p className="text-muted-foreground mt-2 text-sm">
              Review the changes in the right pane.
            </p>
          </div>

          {/* Preview actions */}
          <div className="bg-muted/30 border-t px-4 py-3">
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={onRejectPreview}
                disabled={isAccepting}
                className="gap-1.5"
              >
                <X className="h-4 w-4" />
                Reject
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleTryAgain}
                disabled={isAccepting}
                className="gap-1.5"
              >
                <RotateCcw className="h-4 w-4" />
                Try Again
              </Button>
              <Button
                size="sm"
                onClick={onAcceptPreview}
                disabled={isAccepting}
                className="gap-1.5"
              >
                {isAccepting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4" />
                )}
                Accept & Save
              </Button>
            </div>
          </div>
        </>
      ) : (
        <>
          {/* Messages area */}
          <ScrollArea ref={scrollRef} className="h-[250px] flex-1">
            <div className="py-2">
              {/* Loading state */}
              {isLoading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
                </div>
              )}

              {/* Empty state */}
              {!isLoading && messages.length === 0 && (
                <div className="flex flex-col items-center justify-center px-4 py-8 text-center">
                  <div className="bg-muted rounded-full p-3">
                    <Sparkles className="text-muted-foreground h-5 w-5" />
                  </div>
                  <p className="text-muted-foreground mt-3 max-w-xs text-sm">
                    Select text from the panes to add context, then ask
                    questions or click "Generate Preview" to create a revision.
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

          {/* Chat input area */}
          <div className="space-y-3 border-t p-3">
            <div className="relative">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={handleChange}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                aria-describedby={charCountId}
                disabled={isStreaming}
                className="max-h-[120px] min-h-[60px] resize-none pr-12 text-sm"
                rows={2}
              />
              <div className="absolute right-2 bottom-2">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleSubmit}
                      aria-disabled={!canSubmit}
                      className={cn(
                        "h-7 w-7 p-0",
                        !canSubmit &&
                          "hover:text-foreground cursor-not-allowed opacity-50 hover:bg-transparent"
                      )}
                      aria-label="Send message"
                    >
                      {isStreaming ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <MessageSquare className="h-4 w-4" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Send message</p>
                    <p className="text-muted-foreground text-xs">Press Enter</p>
                  </TooltipContent>
                </Tooltip>
              </div>
            </div>

            {/* Controls row */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {/* Model selector */}
                {availableModels && availableModels.length > 0 && (
                  <Select value={selectedModel} onValueChange={onModelChange}>
                    <SelectTrigger
                      className="h-8 w-[160px] text-xs"
                      aria-label="Select AI Model"
                    >
                      <SelectValue placeholder="Select model" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableModels.map((model) => (
                        <SelectItem key={model.id} value={model.id}>
                          <span className="flex items-center gap-1.5">
                            <span className="truncate">{model.name}</span>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                <Toggle
                  pressed={webSearchEnabled}
                  onPressedChange={setWebSearchEnabled}
                  size="sm"
                  className="h-8 gap-1.5 px-2 text-xs"
                  aria-label="Toggle web search"
                >
                  <Search className="h-3.5 w-3.5" />
                  Web Search
                </Toggle>
                <span
                  id={charCountId}
                  className={cn(
                    "text-muted-foreground text-xs transition-colors",
                    input.length > maxMessageLength * 0.9 &&
                      "font-medium text-amber-500",
                    input.length >= maxMessageLength && "text-destructive"
                  )}
                  aria-label={`${input.length} of ${maxMessageLength} characters`}
                >
                  {input.length}/{maxMessageLength}
                </span>
              </div>

              {/* Generate Preview button */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="sm"
                    onClick={handleGeneratePreview}
                    aria-disabled={!canGenerate}
                    className={cn(
                      "gap-1.5",
                      !canGenerate &&
                        "hover:bg-primary hover:text-primary-foreground cursor-not-allowed opacity-50"
                    )}
                  >
                    {isGenerating ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="h-4 w-4" />
                    )}
                    Generate Preview
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{generatePreviewTooltip}</p>
                </TooltipContent>
              </Tooltip>
            </div>
          </div>
        </>
      )}

      {/* Debug Context Dialog */}
      <Dialog open={debugDialogOpen} onOpenChange={setDebugDialogOpen}>
        <DialogContent className="flex max-h-[80vh] max-w-4xl flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Bug className="h-5 w-5" />
              LLM Context Debug
            </DialogTitle>
            <DialogDescription>
              View the full context being sent to the LLM for this conversation.
            </DialogDescription>
          </DialogHeader>
          <div className="flex-1 overflow-hidden">
            {isLoadingDebug ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
              </div>
            ) : debugContext ? (
              <ScrollArea className="h-[60vh]">
                <div className="space-y-4 p-1">
                  <div>
                    <h4 className="mb-2 text-sm font-medium">Artifact Info</h4>
                    <div className="bg-muted rounded p-2 font-mono text-xs">
                      Type: {debugContext.artifact_type} | ID:{" "}
                      {debugContext.artifact_id} | Messages:{" "}
                      {debugContext.message_count}
                    </div>
                  </div>
                  <div className="group relative">
                    <h4 className="mb-2 text-sm font-medium">System Prompt</h4>
                    <div className="absolute top-8 right-2 z-10 opacity-0 transition-opacity group-hover:opacity-100">
                      <CopyButton
                        content={debugContext.system_prompt}
                        size="sm"
                      />
                    </div>
                    <pre className="bg-muted relative overflow-x-auto rounded p-3 font-mono text-xs break-words whitespace-pre-wrap">
                      {debugContext.system_prompt}
                    </pre>
                  </div>
                  <div className="group relative">
                    <h4 className="mb-2 text-sm font-medium">
                      Artifact Content
                    </h4>
                    <div className="absolute top-8 right-2 z-10 opacity-0 transition-opacity group-hover:opacity-100">
                      <CopyButton
                        content={debugContext.artifact_content}
                        size="sm"
                      />
                    </div>
                    <pre className="bg-muted relative max-h-[40vh] overflow-x-auto overflow-y-auto rounded p-3 font-mono text-xs break-words whitespace-pre-wrap">
                      {debugContext.artifact_content}
                    </pre>
                  </div>
                </div>
              </ScrollArea>
            ) : (
              <div className="text-muted-foreground py-8 text-center">
                Failed to load context. Make sure the conversation exists.
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
