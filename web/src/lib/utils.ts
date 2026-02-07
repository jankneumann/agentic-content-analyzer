/**
 * Utility functions for the ACA (AI Content Analyzer) Web UI
 *
 * This module provides helper functions used throughout the application,
 * particularly for styling and class management with Tailwind CSS.
 */

import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Combines class names using clsx and tailwind-merge
 *
 * This function is essential for shadcn/ui components. It:
 * 1. Uses clsx to conditionally join class names
 * 2. Uses tailwind-merge to intelligently merge Tailwind classes
 *    (e.g., resolving conflicts like "p-2" vs "p-4")
 *
 * @example
 * // Basic usage
 * cn("px-2 py-1", "text-sm")
 * // => "px-2 py-1 text-sm"
 *
 * @example
 * // With conditionals
 * cn("base-class", isActive && "active-class", isDisabled && "disabled-class")
 * // => "base-class active-class" (if isActive is true)
 *
 * @example
 * // Merging conflicting Tailwind classes
 * cn("p-2", "p-4")
 * // => "p-4" (tailwind-merge resolves the conflict)
 *
 * @param inputs - Class values to combine (strings, objects, arrays, etc.)
 * @returns Combined and merged class string
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
