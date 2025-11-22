import { Download } from '@/types';
import { DownloadItem } from './DownloadItem';
import { DownloadGridItem } from './DownloadGridItem';

interface DownloadQueueProps {
  downloads: Map<string, Download>;
  onCancel: (jobId: string) => void;
  viewMode: 'list' | 'grid';
}

export function DownloadQueue({ downloads, onCancel, viewMode }: DownloadQueueProps) {
  const downloadArray = Array.from(downloads.values());

  if (downloadArray.length === 0) {
    return (
      <div className="text-center text-zinc-500 py-10">
        <p>No downloads yet.</p>
        <p>Paste a URL above to get started.</p>
      </div>
    );
  }

  if (viewMode === 'grid') {
      return (
        <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-3 animate-fade-in">
            {downloadArray.map((download) => (
                <DownloadGridItem
                    key={download.jobId}
                    download={download}
                    onCancel={onCancel}
                />
            ))}
        </div>
      );
  }

  // Default List View
  return (
    <div className="space-y-2 animate-fade-in">
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