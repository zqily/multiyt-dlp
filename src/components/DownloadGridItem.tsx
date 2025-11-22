import { Download } from '@/types';
import { X, CheckCircle2, AlertCircle, Hourglass, MonitorPlay, Headphones, Tags, FileOutput, Image as ImageIcon, Activity } from 'lucide-react';
import { twMerge } from 'tailwind-merge';

interface DownloadGridItemProps {
  download: Download;
  onCancel: (jobId: string) => void;
}

export function DownloadGridItem({ download, onCancel }: DownloadGridItemProps) {
  const { jobId, status, progress, error, phase, preset, embedThumbnail } = download;

  const isAudio = preset?.startsWith('audio');
  
  // State Flags
  const isQueued = status === 'pending';
  const isActive = status === 'downloading'; 
  const isError = status === 'error';
  const isCompleted = status === 'completed';

  const isProcessingPhase = phase?.includes('Merging') 
    || phase?.includes('Extracting') 
    || phase?.includes('Fixing')
    || phase?.includes('Starting')
    || phase?.includes('Initializing');

  const isMetaPhase = phase?.includes('Metadata') || phase?.includes('Thumbnail');

  // Determine base color based on type/status
  const getThemeColorClass = () => {
      if (isError) return "text-theme-red border-theme-red shadow-glow-red";
      if (isCompleted) return "text-emerald-500 border-emerald-500";
      if (isProcessingPhase || isMetaPhase) return "text-yellow-500 border-yellow-500";
      if (isAudio) return "text-theme-red border-theme-red shadow-glow-red";
      return "text-theme-cyan border-theme-cyan shadow-glow-cyan"; // Video/Default
  };
  
  const getBgFillColor = () => {
      if (isError) return "bg-theme-red";
      if (isCompleted) return "bg-emerald-500";
      if (isProcessingPhase || isMetaPhase) return "bg-yellow-500";
      if (isAudio) return "bg-theme-red";
      return "bg-theme-cyan";
  };

  const IconComponent = () => {
    if (isError) return <AlertCircle className="h-6 w-6" />;
    if (isCompleted) return <CheckCircle2 className="h-6 w-6" />;
    if (isQueued) return <Hourglass className="h-6 w-6 animate-pulse" />;
    
    if (isMetaPhase) return <Tags className="h-6 w-6 animate-pulse" />;
    if (isProcessingPhase) return <FileOutput className="h-6 w-6 animate-pulse" />;
    if (embedThumbnail && phase?.includes('Thumbnail')) return <ImageIcon className="h-6 w-6 animate-pulse" />;

    return isAudio ? <Headphones className="h-6 w-6" /> : <MonitorPlay className="h-6 w-6" />;
  };

  return (
    <div 
        className={twMerge(
            "group relative h-24 w-full rounded-xl border bg-zinc-900/40 overflow-hidden transition-all duration-300 select-none flex items-center justify-center",
            isActive ? getThemeColorClass() : "border-zinc-800 text-zinc-600",
            isQueued && "opacity-60 bg-zinc-900/20 border-zinc-800/60"
        )}
    >
        {/* Progress Fill Layer (Bottom to Top) */}
        {isActive && (
            <div 
                className={twMerge("absolute bottom-0 left-0 right-0 transition-all duration-300 opacity-20", getBgFillColor())}
                style={{ height: `${progress}%` }}
            />
        )}
        
        {/* Indeterminate Stripe overlay for Queued/Processing */}
        {(isQueued || isProcessingPhase) && (
            <div className="absolute inset-0 w-full h-full bg-[linear-gradient(45deg,transparent_25%,rgba(255,255,255,0.03)_25%,rgba(255,255,255,0.03)_50%,transparent_50%,transparent_75%,rgba(255,255,255,0.03)_75%,rgba(255,255,255,0.03)_100%)] bg-[length:20px_20px] animate-[progress-stripes_2s_linear_infinite] pointer-events-none" />
        )}

        {/* Content Layer */}
        <div className="z-10 relative flex flex-col items-center justify-center">
            {isActive && !isProcessingPhase && !isMetaPhase ? (
                // Show Percentage when actively downloading
                <div className="flex flex-col items-center animate-fade-in">
                    <span className="text-xl font-black tracking-tighter tabular-nums">
                        {progress.toFixed(0)}<span className="text-xs font-normal opacity-70">%</span>
                    </span>
                    <Activity className="h-3 w-3 mt-1 animate-pulse opacity-50" />
                </div>
            ) : (
                // Show Icon otherwise
                <div className={twMerge("transition-transform duration-300 group-hover:scale-110", isActive && "animate-pulse")}>
                    <IconComponent />
                </div>
            )}
        </div>

        {/* Hover Overlay with Cancel/Info */}
        {(isActive || isQueued || isError) && (
            <div className="absolute inset-0 bg-black/80 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center z-20 backdrop-blur-[2px]">
                {isError ? (
                    <div className="px-2 text-[10px] text-center text-red-400 font-mono break-words w-full">
                        {error?.substring(0, 40)}...
                    </div>
                ) : (
                    <button 
                        onClick={() => onCancel(jobId)}
                        className="p-2 rounded-full bg-theme-red/10 text-theme-red hover:bg-theme-red hover:text-white transition-colors"
                        title="Cancel Download"
                    >
                        <X className="h-5 w-5" />
                    </button>
                )}
            </div>
        )}
    </div>
  );
}