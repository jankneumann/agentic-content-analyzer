/**
 * URL Validation for Share Target
 *
 * Validates URLs received from the native share sheet.
 * Rejects non-http(s) schemes (javascript:, data:, file:) and enforces max length.
 */

const MAX_URL_LENGTH = 2048

const BLOCKED_PROTOCOLS = new Set([
  "javascript:",
  "data:",
  "file:",
  "blob:",
  "vbscript:",
])

export interface ValidationResult {
  valid: boolean
  error?: string
}

/**
 * Validate a URL for safe ingestion.
 *
 * Rules:
 * - Must be parseable as a URL
 * - Must use http: or https: protocol
 * - Must not exceed 2048 characters
 */
export function validateShareUrl(url: string): ValidationResult {
  const trimmed = url.trim()

  if (trimmed.length === 0) {
    return { valid: false, error: "URL is empty" }
  }

  if (trimmed.length > MAX_URL_LENGTH) {
    return {
      valid: false,
      error: `URL too long (max ${MAX_URL_LENGTH} characters)`,
    }
  }

  // Check for blocked protocols before parsing to catch edge cases
  const lowerUrl = trimmed.toLowerCase()
  for (const protocol of BLOCKED_PROTOCOLS) {
    if (lowerUrl.startsWith(protocol)) {
      return { valid: false, error: `Unsupported URL scheme: ${protocol}` }
    }
  }

  try {
    const parsed = new URL(trimmed)
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return { valid: false, error: `Unsupported URL scheme: ${parsed.protocol}` }
    }
    return { valid: true }
  } catch {
    return { valid: false, error: "Invalid URL format" }
  }
}

/**
 * Extract the first http(s) URL from a text string.
 *
 * Useful when the share sheet passes surrounding text along with the URL.
 * Returns null if no URL is found.
 */
export function extractUrl(text: string): string | null {
  const match = text.match(/https?:\/\/[^\s<>"{}|\\^`[\]]+/i)
  return match ? match[0] : null
}
