/**
 * Generated TypeScript interfaces for Mobile Content Capture contracts.
 *
 * These types mirror the existing API client in web/src/lib/api/contents.ts.
 * This file serves as the contract reference.
 */

export interface SaveURLRequest {
  url: string;
  title?: string | null;
  excerpt?: string | null;
  tags?: string[] | null;
  notes?: string | null;
  source?:
    | "chrome_extension"
    | "ios_shortcut"
    | "bookmarklet"
    | "web_save_page"
    | "api"
    | null;
}

export interface SavePageRequest {
  url: string;
  /** Rendered DOM HTML (max 5 MB) */
  html: string;
  title?: string | null;
  excerpt?: string | null;
  tags?: string[] | null;
  notes?: string | null;
  source?: string | null;
}

export interface SaveURLResponse {
  content_id: number;
  status: "queued" | "exists";
  message: string;
  duplicate: boolean;
}

export interface ContentStatusResponse {
  content_id: number;
  status: "pending" | "parsing" | "parsed" | "failed";
  title?: string | null;
  word_count?: number | null;
  error?: string | null;
}

export interface RateLimitError {
  detail: string;
  retry_after: number;
}
