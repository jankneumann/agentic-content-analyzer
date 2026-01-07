/**
 * Text Selection Hook
 *
 * Detects text selection within specified containers and provides
 * selection data for the review interface.
 *
 * Features:
 * - Detects text selection via Selection API
 * - Calculates popover position near selection
 * - Identifies which pane the selection is from
 * - Clears selection state when clicking elsewhere
 */

import { useState, useEffect, useCallback } from "react"

export interface TextSelection {
  /** Selected text content */
  text: string
  /** Pane identifier (left/right) */
  paneId: "left" | "right"
  /** Human-readable label for the pane */
  paneLabel: string
  /** Position for displaying popover */
  position: {
    x: number
    y: number
  }
}

interface UseTextSelectionOptions {
  /** Minimum characters for a valid selection */
  minLength?: number
  /** Container ref to scope selection detection */
  containerRef?: React.RefObject<HTMLElement | null>
  /** Whether selection is enabled */
  enabled?: boolean
}

/**
 * Hook to detect and manage text selection
 *
 * @param options - Configuration options
 * @returns Current selection state and clear function
 *
 * @example
 * const { selection, clearSelection } = useTextSelection({
 *   minLength: 3,
 *   containerRef: reviewContainerRef,
 * })
 */
export function useTextSelection(options: UseTextSelectionOptions = {}) {
  const { minLength = 3, containerRef, enabled = true } = options

  const [selection, setSelection] = useState<TextSelection | null>(null)

  /**
   * Get pane info from the selection's parent elements
   */
  const getPaneInfo = useCallback(
    (element: Node | null): { paneId: "left" | "right"; paneLabel: string } | null => {
      if (!element) return null

      // Walk up the DOM tree to find pane data attributes
      let current: Node | null = element
      while (current && current !== document.body) {
        if (current instanceof HTMLElement) {
          const paneId = current.dataset.paneId as "left" | "right" | undefined
          const paneLabel = current.dataset.paneLabel

          if (paneId && paneLabel) {
            return { paneId, paneLabel }
          }
        }
        current = current.parentNode
      }

      return null
    },
    []
  )

  /**
   * Handle selection change
   */
  const handleSelectionChange = useCallback(() => {
    if (!enabled) return

    const windowSelection = window.getSelection()

    // No selection or collapsed (just a cursor)
    if (!windowSelection || windowSelection.isCollapsed) {
      return
    }

    const text = windowSelection.toString().trim()

    // Check minimum length
    if (text.length < minLength) {
      return
    }

    // Get the anchor node (start of selection)
    const anchorNode = windowSelection.anchorNode

    // Check if selection is within our container (if specified)
    if (containerRef?.current) {
      if (!containerRef.current.contains(anchorNode)) {
        return
      }
    }

    // Get pane info
    const paneInfo = getPaneInfo(anchorNode)
    if (!paneInfo) {
      return
    }

    // Check if selection is enabled in this pane
    let current: Node | null = anchorNode
    while (current && current !== document.body) {
      if (current instanceof HTMLElement) {
        if (current.dataset.selectionEnabled === "false") {
          return
        }
      }
      current = current.parentNode
    }

    // Get selection rect for positioning
    const range = windowSelection.getRangeAt(0)
    const rect = range.getBoundingClientRect()

    // Calculate position (center-top of selection)
    const position = {
      x: rect.left + rect.width / 2,
      y: rect.top,
    }

    setSelection({
      text,
      paneId: paneInfo.paneId,
      paneLabel: paneInfo.paneLabel,
      position,
    })
  }, [enabled, minLength, containerRef, getPaneInfo])

  /**
   * Clear selection state
   */
  const clearSelection = useCallback(() => {
    setSelection(null)
    // Also clear the browser's selection
    window.getSelection()?.removeAllRanges()
  }, [])

  /**
   * Handle click to potentially clear selection
   */
  const handleClick = useCallback(
    (event: MouseEvent) => {
      // Don't clear if clicking on the popover
      const target = event.target as HTMLElement
      if (target.closest("[data-selection-popover]")) {
        return
      }

      // Small delay to allow selection to complete
      setTimeout(() => {
        const windowSelection = window.getSelection()
        if (!windowSelection || windowSelection.isCollapsed) {
          setSelection(null)
        }
      }, 10)
    },
    []
  )

  /**
   * Handle mouseup to detect selection completion
   */
  const handleMouseUp = useCallback(() => {
    if (!enabled) return

    // Small delay to ensure selection is complete
    setTimeout(() => {
      handleSelectionChange()
    }, 10)
  }, [enabled, handleSelectionChange])

  // Set up event listeners
  useEffect(() => {
    if (!enabled) return

    // Always listen on document for mouseup to catch all selections
    // The container check happens in handleSelectionChange
    document.addEventListener("mouseup", handleMouseUp)
    document.addEventListener("click", handleClick)

    return () => {
      document.removeEventListener("mouseup", handleMouseUp)
      document.removeEventListener("click", handleClick)
    }
  }, [enabled, handleMouseUp, handleClick])

  return {
    selection,
    clearSelection,
    hasSelection: selection !== null,
  }
}
