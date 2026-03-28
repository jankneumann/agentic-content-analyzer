/**
 * React hook for Tauri native file drag-and-drop
 *
 * Manages file drop events, validation, upload state, and toast notifications.
 */

import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import type { FileDropResult, FileDropSummary } from '@/lib/tauri/file-drop';
import { validateFile, uploadFile } from '@/lib/tauri/file-drop';

interface UseTauriFileDropOptions {
  maxSizeMB?: number;
  enabled?: boolean;
}

interface UseTauriFileDropResult {
  isDragOver: boolean;
  isUploading: boolean;
  lastSummary: FileDropSummary | null;
}

export function useTauriFileDrop(
  options: UseTauriFileDropOptions = {},
): UseTauriFileDropResult {
  const { maxSizeMB = 500, enabled = true } = options;
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [lastSummary, setLastSummary] = useState<FileDropSummary | null>(null);

  const handleDrop = useCallback(
    async (paths: string[]) => {
      setIsDragOver(false);
      if (paths.length === 0) return;

      setIsUploading(true);
      const results: FileDropResult[] = [];
      let uploaded = 0;
      let rejected = 0;
      let failed = 0;

      for (const filePath of paths) {
        // Get file size via Tauri fs API
        let sizeBytes = 0;
        try {
          const { stat } = await import('@tauri-apps/plugin-fs');
          const info = await stat(filePath);
          sizeBytes = info.size;
        } catch {
          // If we can't stat, try uploading anyway
          sizeBytes = 0;
        }

        const validation = validateFile(filePath, sizeBytes, maxSizeMB);

        if (validation.status !== 'valid') {
          rejected++;
          results.push({
            fileName: validation.fileName,
            status: validation.status,
            error: validation.error,
          });
          toast.error(validation.error || `Cannot upload ${validation.fileName}`);
          continue;
        }

        const uploadResult = await uploadFile(filePath);
        if (uploadResult.ok) {
          uploaded++;
          results.push({ fileName: validation.fileName, status: 'uploaded' });
          if (paths.length === 1) {
            toast.success(`Uploaded ${validation.fileName}`);
          }
        } else {
          failed++;
          results.push({
            fileName: validation.fileName,
            status: 'upload_failed',
            error: uploadResult.error,
          });
          toast.error(`Failed to upload ${validation.fileName}: ${uploadResult.error}`);
        }
      }

      // Summary toast for multi-file drops
      if (paths.length > 1) {
        const parts: string[] = [];
        if (uploaded > 0) parts.push(`${uploaded} uploaded`);
        if (rejected > 0) parts.push(`${rejected} rejected`);
        if (failed > 0) parts.push(`${failed} failed`);
        toast.info(`Drop complete: ${parts.join(', ')}`);
      }

      const summary: FileDropSummary = {
        total: paths.length,
        uploaded,
        rejected,
        failed,
        results,
      };
      setLastSummary(summary);
      setIsUploading(false);
    },
    [maxSizeMB],
  );

  useEffect(() => {
    if (!enabled) return;

    let unlisten: (() => void) | undefined;
    let unlistenHover: (() => void) | undefined;
    let unlistenCancel: (() => void) | undefined;

    const setup = async () => {
      try {
        const { getCurrentWebviewWindow } = await import(
          '@tauri-apps/api/webviewWindow'
        );
        const appWindow = getCurrentWebviewWindow();

        unlisten = await appWindow.onDragDropEvent((event) => {
          if (event.payload.type === 'drop') {
            handleDrop(event.payload.paths);
          } else if (event.payload.type === 'over') {
            setIsDragOver(true);
          } else if (event.payload.type === 'leave') {
            setIsDragOver(false);
          }
        });
      } catch {
        // Not in Tauri context — no-op
      }
    };

    setup();

    return () => {
      unlisten?.();
      unlistenHover?.();
      unlistenCancel?.();
    };
  }, [enabled, handleDrop]);

  return { isDragOver, isUploading, lastSummary };
}
