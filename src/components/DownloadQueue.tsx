import { Download } from '@/types';
import { DownloadItem } from './DownloadItem';

interface DownloadQueueProps {
  downloads: Map<string, Download>;
  onCancel: (jobId: string) => void;
}

export function DownloadQueue({ downloads, onCancel }: DownloadQueueProps) {
  const downloadArray = Array.from(downloads.values());

  if (downloadArray.length === 0) {
    return (
      <div className="text-center text-zinc-500 py-10">
        <p>No downloads yet.</p>
        <p>Paste a URL above to get started.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {downloadArray.map((download) => (
        <DownloadItem
          key={download.jobId}
          download={download}
          onCancel={onCancel}
        />
      ))}
    </div>
  );
}
