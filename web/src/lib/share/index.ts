/**
 * Share Target Module
 *
 * Receives URLs from the native share sheet (iOS/Android) and saves them
 * via the save-url API. Failed saves are queued offline and retried on
 * network reconnect.
 *
 * Usage:
 *   import { initShareTarget } from "@/lib/share"
 *   initShareTarget()  // Call once during app init; no-op on web
 */

export { initShareTarget } from "./share-handler"
export { validateShareUrl, extractUrl } from "./url-validator"
export { enqueue, dequeue, getPending, flushQueue } from "./offline-queue"
export type { PendingShare } from "./offline-queue"
export type { ValidationResult } from "./url-validator"
