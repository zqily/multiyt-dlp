// src/components/DownloadItem.tsx

import { Download } from '@/types';
import { Progress } from './ui/Progress';
import { Button } from './ui/Button';
import { X, MonitorPlay, Clock, CheckCircle2, AlertCircle, Headphones, Activity, FileOutput, Tags, FileText, Image as ImageIcon, Hourglass } from 'lucide-react';
import { twMerge } from 'tailwind-merge';

interface DownloadItemProps {
  download: Download;
  onCancel: (jobId: string) => void;
}

export function DownloadItem({ download, onCancel }: DownloadItemProps) {

  const { jobId, url, status, progress, speed, eta, error, filename, phase, preset, embedMetadata, embedThumbnail } = download;

  const displayTitle = filename || url;
  const isAudio = preset?.startsWith('audio');

  // Determine State Flags
  const isQueued = status === 'pending';
  const isActive = status === 'downloading'; // Only true if process is actually running
  const isError = status === 'error';
  const isCompleted = status === 'completed';
  const isCancelled = status === 'cancelled';

  // Formatting helpers
  const formatStat = (text?: string) => {
      if (!text || text === 'Unknown' || text === 'N/A') return <span className="animate-pulse text-zinc-600">--</span>;
      return text;
  };

  // Determine if we are in a post-processing phase
  const isProcessingPhase = phase?.includes('Merging') || phase?.includes('Extracting') || phase?.includes('Fixing');
  const isMetaPhase = phase?.includes('Metadata') || phase?.includes('Thumbnail');

  const getIcon = () => {
      if (isError) return <AlertCircle className="h-5 w-5 text-theme-red" />;
      if (isCompleted) return <CheckCircle2 className="h-5 w-5 text-theme-cyan" />;
      if (isCancelled) return <X className="h-5 w-5 text-zinc-500" />;
      if (isQueued) return <Hourglass className="h-5 w-5 text-zinc-500 animate-pulse" />; // Distinct Icon for Queue
      
      if (isMetaPhase) return <Tags className="h-5 w-5 text-yellow-400 animate-pulse" />;
      if (isProcessingPhase) return <FileOutput className="h-5 w-5 text-zinc-100 animate-pulse" />;

      return isAudio 
        ? <Headphones className="h-5 w-5 text-theme-red animate-pulse" /> 
        : <MonitorPlay className="h-5 w-5 text-theme-cyan animate-pulse" />;
  };

  let badgeText = isAudio ? 'AUDIO' : 'VIDEO';
  if (isActive || isQueued) {
      if (preset) {
          const parts = preset.split('_');
          if (parts.length > 1 && parts[1] !== 'best') {
             badgeText = parts[1].toUpperCase();
          }
      }
  }

  return (
    <div className={twMerge(
        "group animate-fade-in relative bg-surface border rounded-lg p-5 transition-all duration-300",
        // Styling for Active (Running) Jobs
        isActive && "border-theme-cyan/30 shadow-[0_0_20px_-10px_rgba(0,242,234,0.1)]",
        // Styling for Processing Phase
        (isProcessingPhase || isMetaPhase) && "border-yellow-500/30 shadow-[0_0_20px_-10px_rgba(234,179,8,0.2)]",
        // Styling for Error
        isError && "border-theme-red/30",
        // Styling for Queued (Pending) - Dormant look
        isQueued && "border-zinc-800/60 bg-zinc-900/30 opacity-80",
        // Default
        (!isActive && !isError && !isQueued) && "border-border"
    )}>
      
      <div className="flex items-start gap-5">
        {/* Icon Box */}
        <div className={twMerge(
            "h-12 w-12 flex-shrink-0 rounded-lg flex items-center justify-center border transition-colors duration-500",
            isActive && (isProcessingPhase || isMetaPhase) && "bg-yellow-500/10 border-yellow-500/30",
            isActive && !isProcessingPhase && !isMetaPhase && isAudio && "bg-theme-red/5 border-theme-red/20",
            isActive && !isProcessingPhase && !isMetaPhase && !isAudio && "bg-theme-cyan/5 border-theme-cyan/20",
            !isActive && "bg-zinc-900 border-zinc-800"
        )}>
          {getIcon()}
        </div>
        
        <div className="flex-grow min-w-0 space-y-3">
            {/* Title Row */}
            <div className="flex justify-between items-start gap-4">
                 <div className="space-y-1 min-w-0">
                    <p className={twMerge(
                        "text-sm font-semibold truncate transition-colors",
                        isActive ? "text-zinc-100" : "text-zinc-400"
                    )} title={displayTitle}>
                        {displayTitle}
                    </p>
                    <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider font-bold">
                        {/* Format Badge */}
                        <span className={twMerge(
                            "px-1.5 py-0.5 rounded border",
                            isQueued 
                                ? "border-zinc-700 text-zinc-600 bg-zinc-800" // Dim badge for queued
                                : isAudio 
                                    ? "border-theme-red/30 text-theme-red bg-theme-red/5" 
                                    : "border-theme-cyan/30 text-theme-cyan bg-theme-cyan/5"
                        )}>{badgeText}</span>
                        
                        {/* Extra Flags */}
                        {embedMetadata && (
                             <span className="px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-400 bg-zinc-800/50 flex items-center gap-1" title="Metadata Embedded">
                                <FileText className="h-3 w-3" /> TAGS
                             </span>
                        )}
                        
                        {embedThumbnail && (
                             <span className="px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-400 bg-zinc-800/50 flex items-center gap-1" title="Thumbnail Embedded">
                                <ImageIcon className="h-3 w-3" /> ART
                             </span>
                        )}

                        {/* Phase / Status Text */}
                        <span className={twMerge(
                            "flex items-center gap-1 transition-colors duration-300 ml-1",
                             (isProcessingPhase || isMetaPhase) ? "text-yellow-400" : "text-zinc-500"
                        )}>
                            {isActive && <Activity className={twMerge("h-3 w-3", (isProcessingPhase || isMetaPhase) && "animate-spin")} />}
                            
                            {/* Display Logic */}
                            {phase 
                                ? phase 
                                : isQueued 
                                    ? "Waiting for slot..." 
                                    : status}
                        </span>
                    </div>
                 </div>

                 {/* Percentage / Status (Only show % if actually running) */}
                 <div className="flex flex-col items-end gap-1">
                    {isActive && (
                         <span className="text-lg font-bold text-zinc-100 tabular-nums">
                            {progress.toFixed(0)}<span className="text-sm text-zinc-600">%</span>
                         </span>
                    )}
                    {isQueued && (
                        <span className="text-xs font-bold text-zinc-600 uppercase bg-zinc-900 border border-zinc-800 px-2 py-1 rounded">
                            Queued
                        </span>
                    )}
                 </div>
            </div>
            
            {/* Progress Bar Area */}
            <div className="space-y-3">
                {/* Active Download Bar */}
                {isActive && (
                     <div className={twMerge("relative", (isProcessingPhase || isMetaPhase) && "opacity-80")}>
                        <Progress 
                            value={progress} 
                            variant={isError ? 'error' : 'default'} 
                            className={twMerge(
                                (isProcessingPhase || isMetaPhase) && "opacity-70"
                            )}
                        />
                        {/* Indeterminate overlay for processing phases */}
                        {(isProcessingPhase || isMetaPhase) && (
                            <div className="absolute inset-0 bg-yellow-400/20 animate-pulse rounded-full" />
                        )}
                     </div>
                )}
                
                {/* Queued Indeterminate Bar */}
                {isQueued && (
                    <div className="w-full h-1 bg-zinc-900 rounded-full overflow-hidden relative">
                         {/* Striped pattern for queued state */}
                        <div className="absolute inset-0 w-full h-full bg-[linear-gradient(45deg,transparent_25%,rgba(255,255,255,0.05)_25%,rgba(255,255,255,0.05)_50%,transparent_50%,transparent_75%,rgba(255,255,255,0.05)_75%,rgba(255,255,255,0.05)_100%)] bg-[length:20px_20px] animate-[progress-stripes_1s_linear_infinite]" />
                    </div>
                )}
                
                {isError && (
                    <div className="text-xs text-theme-red bg-theme-red/10 border border-theme-red/20 p-3 rounded font-mono whitespace-pre-wrap">
                        {error}
                    </div>
                )}

                {/* Active Stats */}
                {isActive && !isProcessingPhase && !isMetaPhase && (
                    <div className="flex items-center justify-between text-xs text-zinc-500 font-mono">
                        <span title="Speed" className="text-zinc-400 min-w-[60px]">
                           {formatStat(speed)}
                        </span>
                        <span title="ETA" className="flex items-center gap-1 text-zinc-400">
                            <Clock className="h-3 w-3" /> {formatStat(eta)}
                        </span>
                    </div>
                )}
            </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col justify-center pl-2">
          {(isActive || isQueued) && (
             <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => onCancel(jobId)} 
                className="h-8 w-8 text-zinc-600 hover:text-theme-red hover:bg-theme-red/10 transition-colors"
                title="Cancel"
             >
                <X className="h-4 w-4" />
              </Button>
          )}
        </div>
      </div>
    </div>
  );
}