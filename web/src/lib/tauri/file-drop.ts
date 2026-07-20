/**
 * Tauri native file drag-and-drop handler
 *
 * Validates file extension and size before upload.
 * Uses tauri://file-drop and tauri://file-drop-hover events.
 */

// Supported file extensions (matching server-side FILE_SIGNATURES)
const SUPPORTED_EXTENSIONS = new Set([
  ".pdf",
  ".docx",
  ".pptx",
  ".xlsx",
  ".txt",
  ".md",
  ".html",
  ".epub",
  ".wav",
  ".mp3",
  ".msg",
])

const DEFAULT_MAX_SIZE_MB = 500
const BYTES_PER_MB = 1024 * 1024
const MEDIA_TYPES: Record<string, string> = {
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".epub": "application/epub+zip",
  ".html": "text/html",
  ".md": "text/markdown",
  ".mp3": "audio/mpeg",
  ".msg": "application/vnd.ms-outlook",
  ".pdf": "application/pdf",
  ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  ".txt": "text/plain",
  ".wav": "audio/wav",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

export type FileDropStatus = "valid" | "unsupported" | "oversized"

export interface FileDropValidation {
  file: string
  fileName: string
  extension: string
  sizeBytes: number
  status: FileDropStatus
  error?: string
}

export interface FileDropSummary {
  total: number
  uploaded: number
  rejected: number
  failed: number
  results: FileDropResult[]
}

export interface FileDropResult {
  fileName: string
  status: "uploaded" | "unsupported" | "oversized" | "upload_failed"
  error?: string
}

import {
  submitIngestion,
  uploadFile as createUpload,
} from "@/lib/api/workflows"
import type { OperationHandle } from "@/generated/workflow-contracts"

/**
 * Extract file name from a full path
 */
function getFileName(filePath: string): string {
  return filePath.split(/[/\\]/).pop() || filePath
}

/**
 * Extract file extension (lowercase, with dot)
 */
function getExtension(fileName: string): string {
  const dot = fileName.lastIndexOf(".")
  return dot >= 0 ? fileName.slice(dot).toLowerCase() : ""
}

/**
 * Validate a single file for extension and size
 */
export function validateFile(
  filePath: string,
  sizeBytes: number,
  maxSizeMB: number = DEFAULT_MAX_SIZE_MB
): FileDropValidation {
  const fileName = getFileName(filePath)
  const extension = getExtension(fileName)

  if (!SUPPORTED_EXTENSIONS.has(extension)) {
    return {
      file: filePath,
      fileName,
      extension,
      sizeBytes,
      status: "unsupported",
      error: `Unsupported file type: ${extension || "(no extension)"}`,
    }
  }

  const maxBytes = maxSizeMB * BYTES_PER_MB
  if (sizeBytes > maxBytes) {
    return {
      file: filePath,
      fileName,
      extension,
      sizeBytes,
      status: "oversized",
      error: `File too large: ${(sizeBytes / BYTES_PER_MB).toFixed(1)}MB (max ${maxSizeMB}MB)`,
    }
  }

  return {
    file: filePath,
    fileName,
    extension,
    sizeBytes,
    status: "valid",
  }
}

/**
 * Upload a file to the documents upload API
 */
export async function uploadFile(
  filePath: string
): Promise<{ ok: boolean; operation?: OperationHandle; error?: string }> {
  try {
    // In Tauri, we need to read the file and create a FormData
    const { readFile } = await import("@tauri-apps/plugin-fs")
    const contents = await readFile(filePath)
    const fileName = getFileName(filePath)
    const blob = new Blob([contents], { type: MEDIA_TYPES[getExtension(fileName)] })
    const file = new File([blob], fileName, { type: blob.type })

    const upload = await createUpload(file)
    const operation = await submitIngestion({
      kind: "files",
      upload_ids: [upload.id],
    })
    return { ok: true, operation }
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Upload failed",
    }
  }
}
