import { Download } from '@/types';
import { Progress } from './ui/Progress';
import { Button } from './ui/Button';
import { X, FileVideo } from 'lucide-react';

interface DownloadItemProps {
  download: Download;
  onCancel: (jobId: string) => void;
}

export function DownloadItem({ download, onCancel }: DownloadItemProps) {
  const { jobId, url, status, progress, speed, eta, error, filename, phase } = download;

  // Use the clean filename if available, otherwise fallback to URL
  const displayTitle = filename || url;
  
  // Dynamic status text logic
  let statusText = '';
  if (status === 'downloading') {
    const phaseText = phase ? phase : 'Downloading';
    statusText = `${phaseText} - ${speed} - ETA ${eta}`;
  } else if (status === 'completed') {
    statusText = 'Completed!';
  } else if (status === 'error') {
    statusText = `Error: ${error}`;
  } else if (status === 'cancelled') {
    statusText = 'Cancelled';
  } else if (status === 'pending') {
    statusText = 'Pending...';
  }

  return (
    <div className="flex items-center gap-4 p-3 bg-zinc-800 border border-zinc-700 rounded-md">
      <div className="h-10 w-10 flex-shrink-0 bg-zinc-700 rounded flex items-center justify-center text-zinc-400">
        <FileVideo className="h-6 w-6" />
      </div>
      
      <div className="flex-grow min-w-0">
        <div className="flex justify-between items-center mb-1">
             <p className="text-sm font-medium truncate text-zinc-100" title={displayTitle}>
                {displayTitle}
             </p>
             <span className="text-xs text-zinc-400 ml-2 font-mono">{progress.toFixed(1)}%</span>
        </div>
        
        <Progress value={progress} max="100" className="h-2" />
        
        <div className="flex justify-between items-center mt-1 h-4">
          <span className={`text-xs truncate ${status === 'error' ? 'text-red-400' : status === 'completed' ? 'text-green-400' : 'text-zinc-400'}`}>
            {statusText}
          </span>
        </div>
      </div>

      <div>
        {status === 'downloading' || status === 'pending' ? (
           <Button variant="ghost" size="icon" onClick={() => onCancel(jobId)} className="text-zinc-400 hover:text-red-400">
            <X className="h-4 w-4" />
          </Button>
        ) : null}
      </div>
    </div>
  );
}