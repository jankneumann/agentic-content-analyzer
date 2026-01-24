/**
 * Review Context
 *
 * Provides state management for the review interface including:
 * - Context items (selected text snippets)
 * - Feedback text
 * - Preview state
 * - Generation status
 */

import * as React from "react"
import { createContext, useContext, useReducer, useCallback } from "react"
import type { ContextItem } from "@/types/review"
import { REVIEW_LIMITS } from "@/types/review"
import type { Summary } from "@/types/summary"

// Generate unique IDs for context items
let contextIdCounter = 0
function generateContextId(): string {
  return `ctx-${Date.now()}-${++contextIdCounter}`
}

/**
 * Truncate text to max length with ellipsis
 */
function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength - 3) + "..."
}

// --- State Types ---

interface ReviewState {
  /** Selected text snippets for context */
  contextItems: ContextItem[]
  /** Current feedback text */
  feedback: string
  /** Preview of regenerated summary (null if not in preview mode) */
  previewContent: Summary | null
  /** Whether preview generation is in progress */
  isGenerating: boolean
  /** Error message if generation failed */
  error: string | null
}

// --- Actions ---

type ReviewAction =
  | { type: "ADD_CONTEXT_ITEM"; payload: Omit<ContextItem, "id"> }
  | { type: "REMOVE_CONTEXT_ITEM"; payload: string }
  | { type: "CLEAR_ALL_CONTEXT" }
  | { type: "SET_FEEDBACK"; payload: string }
  | { type: "SET_PREVIEW"; payload: Summary | null }
  | { type: "SET_GENERATING"; payload: boolean }
  | { type: "SET_ERROR"; payload: string | null }
  | { type: "RESET" }

// --- Reducer ---

const initialState: ReviewState = {
  contextItems: [],
  feedback: "",
  previewContent: null,
  isGenerating: false,
  error: null,
}

function reviewReducer(state: ReviewState, action: ReviewAction): ReviewState {
  switch (action.type) {
    case "ADD_CONTEXT_ITEM": {
      // Check limits
      if (state.contextItems.length >= REVIEW_LIMITS.MAX_CONTEXT_ITEMS) {
        return state
      }

      const truncatedText = truncateText(
        action.payload.text,
        REVIEW_LIMITS.MAX_CHARS_PER_SELECTION
      )

      const totalChars =
        state.contextItems.reduce((sum, item) => sum + item.text.length, 0) +
        truncatedText.length

      if (totalChars > REVIEW_LIMITS.MAX_TOTAL_CONTEXT_CHARS) {
        return state
      }

      const newItem: ContextItem = {
        ...action.payload,
        id: generateContextId(),
        text: truncatedText,
      }

      return {
        ...state,
        contextItems: [...state.contextItems, newItem],
      }
    }

    case "REMOVE_CONTEXT_ITEM":
      return {
        ...state,
        contextItems: state.contextItems.filter(
          (item) => item.id !== action.payload
        ),
      }

    case "CLEAR_ALL_CONTEXT":
      return {
        ...state,
        contextItems: [],
      }

    case "SET_FEEDBACK":
      return {
        ...state,
        feedback: action.payload.slice(0, REVIEW_LIMITS.MAX_FEEDBACK_LENGTH),
      }

    case "SET_PREVIEW":
      return {
        ...state,
        previewContent: action.payload,
        isGenerating: false,
      }

    case "SET_GENERATING":
      return {
        ...state,
        isGenerating: action.payload,
        error: action.payload ? null : state.error,
      }

    case "SET_ERROR":
      return {
        ...state,
        error: action.payload,
        isGenerating: false,
      }

    case "RESET":
      return initialState

    default:
      return state
  }
}

// --- Context Types ---

interface ReviewContextValue extends ReviewState {
  /** Total characters used in context */
  totalContextChars: number
  /** Whether we can add more context items */
  canAddContext: boolean
  /** Remaining context characters available */
  remainingContextChars: number

  // Actions
  addContextItem: (item: Omit<ContextItem, "id">) => boolean
  removeContextItem: (id: string) => void
  clearAllContext: () => void
  setFeedback: (text: string) => void
  setPreview: (preview: Summary | null) => void
  setGenerating: (generating: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

// --- Context ---

const ReviewContext = createContext<ReviewContextValue | null>(null)

// --- Provider ---

interface ReviewProviderProps {
  children: React.ReactNode
}

export function ReviewProvider({ children }: ReviewProviderProps) {
  const [state, dispatch] = useReducer(reviewReducer, initialState)

  // Computed values
  const totalContextChars = state.contextItems.reduce(
    (sum, item) => sum + item.text.length,
    0
  )
  const remainingContextChars =
    REVIEW_LIMITS.MAX_TOTAL_CONTEXT_CHARS - totalContextChars
  const canAddContext =
    state.contextItems.length < REVIEW_LIMITS.MAX_CONTEXT_ITEMS &&
    remainingContextChars > 0

  // Actions
  const addContextItem = useCallback(
    (item: Omit<ContextItem, "id">): boolean => {
      if (!canAddContext) return false

      const truncatedLength = Math.min(
        item.text.length,
        REVIEW_LIMITS.MAX_CHARS_PER_SELECTION
      )
      if (totalContextChars + truncatedLength > REVIEW_LIMITS.MAX_TOTAL_CONTEXT_CHARS) {
        return false
      }

      dispatch({ type: "ADD_CONTEXT_ITEM", payload: item })
      return true
    },
    [canAddContext, totalContextChars]
  )

  const removeContextItem = useCallback((id: string) => {
    dispatch({ type: "REMOVE_CONTEXT_ITEM", payload: id })
  }, [])

  const clearAllContext = useCallback(() => {
    dispatch({ type: "CLEAR_ALL_CONTEXT" })
  }, [])

  const setFeedback = useCallback((text: string) => {
    dispatch({ type: "SET_FEEDBACK", payload: text })
  }, [])

  const setPreview = useCallback((preview: Summary | null) => {
    dispatch({ type: "SET_PREVIEW", payload: preview })
  }, [])

  const setGenerating = useCallback((generating: boolean) => {
    dispatch({ type: "SET_GENERATING", payload: generating })
  }, [])

  const setError = useCallback((error: string | null) => {
    dispatch({ type: "SET_ERROR", payload: error })
  }, [])

  const reset = useCallback(() => {
    dispatch({ type: "RESET" })
  }, [])

  const value: ReviewContextValue = {
    ...state,
    totalContextChars,
    canAddContext,
    remainingContextChars,
    addContextItem,
    removeContextItem,
    clearAllContext,
    setFeedback,
    setPreview,
    setGenerating,
    setError,
    reset,
  }

  return (
    <ReviewContext.Provider value={value}>{children}</ReviewContext.Provider>
  )
}

// --- Hook ---

export function useReviewContext(): ReviewContextValue {
  const context = useContext(ReviewContext)
  if (!context) {
    throw new Error("useReviewContext must be used within a ReviewProvider")
  }
  return context
}
