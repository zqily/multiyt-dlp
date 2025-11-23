import { useState, useEffect, useCallback } from 'react';
import { listen } from '@tauri-apps/api/event';
import { Download, DownloadCompletePayload, DownloadErrorPayload, DownloadProgressPayload, DownloadFormatPreset } from '@/types';
import { startDownload as apiStartDownload, cancelDownload as apiCancelDownload } from '@/api/invoke';

export function useDownloadManager() {
  const [downloads, setDownloads] = useState<Map<string, Download>>(new Map());

  const updateDownload = (jobId: string, newProps: Partial<Download>) => {
    setDownloads((prev) => {
      const newMap = new Map(prev);
      const existing = newMap.get(jobId);
      if (existing) {
        newMap.set(jobId, { ...existing, ...newProps });
      }
      return newMap;
    });
  };

  useEffect(() => {
    const unlistenProgress = listen<DownloadProgressPayload>('download-progress', (event) => {
      updateDownload(event.payload.jobId, {
        status: 'downloading',
        progress: event.payload.percentage,
        speed: event.payload.speed,
        eta: event.payload.eta,
        filename: event.payload.filename,
        phase: event.payload.phase,
      });
    });

    const unlistenComplete = listen<DownloadCompletePayload>('download-complete', (event) => {
      updateDownload(event.payload.jobId, {
        status: 'completed',
        progress: 100,
        outputPath: event.payload.outputPath,
        phase: 'Done',
      });
    });

    const unlistenError = listen<DownloadErrorPayload>('download-error', (event) => {
      updateDownload(event.payload.jobId, {
        status: 'error',
        error: event.payload.error,
      });
    });

    return () => {
      unlistenProgress.then((f) => f());
      unlistenComplete.then((f) => f());
      unlistenError.then((f) => f());
    };
  }, []);

  const startDownload = useCallback(async (
    url: string, 
    downloadPath: string | undefined, 
    formatPreset: DownloadFormatPreset = 'best',
    videoResolution: string,
    embedMetadata: boolean = false,
    embedThumbnail: boolean = false,
    filenameTemplate: string
  ) => {
    try {
      const jobId = await apiStartDownload(
          url, 
          downloadPath, 
          formatPreset,
          videoResolution, 
          embedMetadata, 
          embedThumbnail,
          filenameTemplate
      ); 
      
      setDownloads((prev) => {
        const newMap = new Map(prev);
        newMap.set(jobId, {
          jobId,
          url,
          status: 'pending',
          progress: 0,
          // Save config for potential retry
          preset: formatPreset,
          videoResolution,
          downloadPath,
          filenameTemplate,
          embedMetadata,
          embedThumbnail
        });
        return newMap;
      });
    } catch (error) {
      console.error('Failed to start download:', error);
    }
  }, []);

  const cancelDownload = useCallback(async (jobId: string) => {
    try {
      await apiCancelDownload(jobId);
      updateDownload(jobId, { status: 'cancelled' });
    } catch (error) {
      console.error('Failed to cancel download:', error);
      updateDownload(jobId, { status: 'error', error: 'Failed to cancel.' });
    }
  }, []);

  // Used to clear finished jobs or remove jobs before retrying
  const removeDownload = useCallback((jobId: string) => {
      setDownloads((prev) => {
          const newMap = new Map(prev);
          newMap.delete(jobId);
          return newMap;
      });
  }, []);

  return { downloads, startDownload, cancelDownload, removeDownload };
}