/**
 * Drop Zone Overlay
 *
 * Shows a visual overlay when files are dragged over the Tauri window.
 * Renders as a fixed overlay covering the entire viewport.
 */

import { useTauriFileDrop } from '@/hooks/use-tauri-file-drop';

interface DropZoneProps {
  maxSizeMB?: number;
}

export function DropZone({ maxSizeMB }: DropZoneProps) {
  const { isDragOver, isUploading } = useTauriFileDrop({ maxSizeMB });

  if (!isDragOver && !isUploading) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="rounded-2xl border-2 border-dashed border-primary bg-card/90 p-12 text-center shadow-2xl">
        {isUploading ? (
          <>
            <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            <p className="text-lg font-medium text-foreground">
              Uploading files...
            </p>
          </>
        ) : (
          <>
            <svg
              className="mx-auto mb-4 h-16 w-16 text-primary"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
              />
            </svg>
            <p className="text-lg font-medium text-foreground">
              Drop files to upload
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              PDF, DOCX, PPTX, XLSX, TXT, MD, HTML, EPUB
            </p>
          </>
        )}
      </div>
    </div>
  );
}
