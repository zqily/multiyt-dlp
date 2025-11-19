import { Download } from '@/types';
import { Progress } from './ui/Progress';
import { Button } from './ui/Button';
import { X } from 'lucide-react';

interface DownloadItemProps {
  download: Download;
  onCancel: (jobId: string) => void;
}

export function DownloadItem({ download, onCancel }: DownloadItemProps) {
  const { jobId, url, status, progress, speed, eta, error } = download;

  return (
    <div className="flex items-center gap-4 p-3 bg-zinc-800 border border-zinc-700 rounded-md">
      <div className="flex-grow">
        <p className="text-sm font-medium truncate" title={url}>{url}</p>
        <div className="flex items-center gap-2 mt-1">
          <Progress value={progress} max="100" className="w-full" />
          <span className="text-xs text-zinc-400 w-12 text-right">{progress.toFixed(1)}%</span>
        </div>
        <div className="text-xs text-zinc-400 mt-1 h-4">
          {status === 'downloading' && `${speed} - ETA ${eta}`}
          {status === 'completed' && <span className="text-green-400">Completed!</span>}
          {status === 'error' && <span className="text-red-400 truncate">Error: {error}</span>}
          {status === 'cancelled' && <span className="text-yellow-400">Cancelled</span>}
          {status === 'pending' && <span>Pending...</span>}
        </div>
      </div>
      <div>
        {status === 'downloading' && (
           <Button variant="ghost" size="icon" onClick={() => onCancel(jobId)}>
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
