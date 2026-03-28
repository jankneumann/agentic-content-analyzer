/**
 * Offline Queue for Share Target
 *
 * When the save-url API call fails (network error, server down), the URL is
 * stored in Capacitor Preferences under `pending_shares`. On network reconnect,
 * the queue is flushed by retrying each pending URL.
 *
 * Deduplication: URLs are normalized (trimmed, trailing slash removed) before
 * storage to prevent duplicate entries.
 */

const QUEUE_KEY = "pending_shares"

async function getPreferences() {
  const { Preferences } = await import("@capacitor/preferences")
  return Preferences
}
const MAX_RETRIES = 5

export interface PendingShare {
  url: string
  queuedAt: string
  retryCount: number
}

/**
 * Normalize a URL for deduplication.
 * Trims whitespace, removes trailing slash, lowercases the origin.
 */
function normalizeUrl(url: string): string {
  try {
    const parsed = new URL(url.trim())
    // Lowercase origin (scheme + host) but preserve path case
    const origin = parsed.origin.toLowerCase()
    let path = parsed.pathname
    // Remove trailing slash from path (unless it's just "/")
    if (path.length > 1 && path.endsWith("/")) {
      path = path.slice(0, -1)
    }
    return `${origin}${path}${parsed.search}${parsed.hash}`
  } catch {
    return url.trim()
  }
}

/**
 * Read the current queue from Preferences.
 */
export async function getPending(): Promise<PendingShare[]> {
  try {
    const Preferences = await getPreferences()
    const { value } = await Preferences.get({ key: QUEUE_KEY })
    if (!value) return []
    return JSON.parse(value) as PendingShare[]
  } catch {
    return []
  }
}

/**
 * Persist the queue to Preferences.
 */
async function savePending(items: PendingShare[]): Promise<void> {
  const Preferences = await getPreferences()
  await Preferences.set({
    key: QUEUE_KEY,
    value: JSON.stringify(items),
  })
}

/**
 * Add a URL to the offline queue if it is not already queued.
 * Deduplicates by normalized URL string.
 */
export async function enqueue(url: string): Promise<void> {
  const pending = await getPending()
  const normalized = normalizeUrl(url)

  // Dedup: check if this URL is already queued
  const alreadyQueued = pending.some(
    (item) => normalizeUrl(item.url) === normalized,
  )
  if (alreadyQueued) return

  pending.push({
    url: url.trim(),
    queuedAt: new Date().toISOString(),
    retryCount: 0,
  })

  await savePending(pending)
}

/**
 * Remove a URL from the offline queue (after successful save).
 */
export async function dequeue(url: string): Promise<void> {
  const pending = await getPending()
  const normalized = normalizeUrl(url)
  const filtered = pending.filter(
    (item) => normalizeUrl(item.url) !== normalized,
  )
  await savePending(filtered)
}

/**
 * Flush the offline queue by retrying each pending URL.
 *
 * @param saveFn - Async function that attempts to save a URL. Returns true on success.
 * @returns Number of successfully saved URLs.
 */
export async function flushQueue(
  saveFn: (url: string) => Promise<boolean>,
): Promise<number> {
  const pending = await getPending()
  if (pending.length === 0) return 0

  let successCount = 0
  const remaining: PendingShare[] = []

  for (const item of pending) {
    try {
      const success = await saveFn(item.url)
      if (success) {
        successCount++
      } else {
        // Keep in queue with incremented retry count
        if (item.retryCount < MAX_RETRIES) {
          remaining.push({ ...item, retryCount: item.retryCount + 1 })
        }
        // Drop items that have exceeded max retries
      }
    } catch {
      if (item.retryCount < MAX_RETRIES) {
        remaining.push({ ...item, retryCount: item.retryCount + 1 })
      }
    }
  }

  await savePending(remaining)
  return successCount
}
