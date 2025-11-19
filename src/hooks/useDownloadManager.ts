import { useState, useEffect, useCallback } from 'react';
import { listen } from '@tauri-apps/api/event';
import { Download, DownloadCompletePayload, DownloadErrorPayload, DownloadProgressPayload } from '@/types';
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
      });
    });

    const unlistenComplete = listen<DownloadCompletePayload>('download-complete', (event) => {
      updateDownload(event.payload.jobId, {
        status: 'completed',
        progress: 100,
        outputPath: event.payload.outputPath,
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

  const startDownload = useCallback(async (url: string) => {
    try {
      const jobId = await apiStartDownload(url);
      setDownloads((prev) => {
        const newMap = new Map(prev);
        newMap.set(jobId, {
          jobId,
          url,
          status: 'pending',
          progress: 0,
        });
        return newMap;
      });
    } catch (error) {
      console.error('Failed to start download:', error);
      // Here you might want to show a toast notification
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

  return { downloads, startDownload, cancelDownload };
}
