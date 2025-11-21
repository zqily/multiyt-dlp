// src/components/DownloadItem.tsx

import { Download } from '@/types';
import { Progress } from './ui/Progress';
import { Button } from './ui/Button';
import { X, MonitorPlay, Clock, CheckCircle2, AlertCircle, Headphones, Activity, FileOutput, Tags, FileText, Image as ImageIcon } from 'lucide-react';
import { twMerge } from 'tailwind-merge';

interface DownloadItemProps {
  download: Download;
  onCancel: (jobId: string) => void;
}

export function DownloadItem({ download, onCancel }: DownloadItemProps) {

  const { jobId, url, status, progress, speed, eta, error, filename, phase, preset, embedMetadata, embedThumbnail } = download;

  const displayTitle = filename || url;
  const isAudio = preset?.startsWith('audio');

  // Formatting helpers
  const formatStat = (text?: string) => {
      if (!text || text === 'Unknown' || text === 'N/A') return <span className="animate-pulse text-zinc-600">--</span>;
      return text;
  };

  // Determine if we are in a post-processing phase
  const isProcessingPhase = phase?.includes('Merging') || phase?.includes('Extracting') || phase?.includes('Fixing');
  const isMetaPhase = phase?.includes('Metadata') || phase?.includes('Thumbnail');

  const getIcon = () => {
      if (status === 'error') return <AlertCircle className="h-5 w-5 text-theme-red" />;
      if (status === 'completed') return <CheckCircle2 className="h-5 w-5 text-theme-cyan" />;
      if (status === 'cancelled') return <X className="h-5 w-5 text-zinc-500" />;
      
      if (isMetaPhase) return <Tags className="h-5 w-5 text-yellow-400 animate-pulse" />;
      if (isProcessingPhase) return <FileOutput className="h-5 w-5 text-zinc-100 animate-pulse" />;

      return isAudio 
        ? <Headphones className="h-5 w-5 text-theme-red animate-pulse" /> 
        : <MonitorPlay className="h-5 w-5 text-theme-cyan animate-pulse" />;
  };

  let badgeText = isAudio ? 'AUDIO' : 'VIDEO';
  if (status === 'downloading' || status === 'pending') {
      if (preset) {
          const parts = preset.split('_');
          if (parts.length > 1 && parts[1] !== 'best') {
             badgeText = parts[1].toUpperCase();
          }
      }
  }
  
  const isActive = status === 'downloading';
  const isError = status === 'error';

  return (
    <div className={twMerge(
        "group animate-fade-in relative bg-surface border border-border rounded-lg p-5 transition-all duration-300",
        isActive && "border-theme-cyan/30 shadow-[0_0_20px_-10px_rgba(0,242,234,0.1)]",
        (isProcessingPhase || isMetaPhase) && "border-yellow-500/30 shadow-[0_0_20px_-10px_rgba(234,179,8,0.2)]",
        isError && "border-theme-red/30"
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
                        <span className={twMerge(
                            "px-1.5 py-0.5 rounded border",
                            isAudio ? "border-theme-red/30 text-theme-red bg-theme-red/5" : "border-theme-cyan/30 text-theme-cyan bg-theme-cyan/5"
                        )}>{badgeText}</span>
                        
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

                        <span className={twMerge(
                            "flex items-center gap-1 transition-colors duration-300 ml-1",
                             (isProcessingPhase || isMetaPhase) ? "text-yellow-400" : "text-zinc-500"
                        )}>
                            {isActive && <Activity className={twMerge("h-3 w-3", (isProcessingPhase || isMetaPhase) && "animate-spin")} />}
                            {phase || (status === 'pending' ? 'Queued' : status)}
                        </span>
                    </div>
                 </div>

                 {/* Percentage / Status */}
                 <div className="flex flex-col items-end gap-1">
                    {(status === 'downloading' || status === 'pending') && (
                         <span className="text-lg font-bold text-zinc-100 tabular-nums">
                            {progress.toFixed(0)}<span className="text-sm text-zinc-600">%</span>
                         </span>
                    )}
                 </div>
            </div>
            
            {/* Progress Bar & Error/Stats */}
            <div className="space-y-3">
                {(status === 'downloading' || status === 'pending') && (
                     <div className={twMerge("relative", (isProcessingPhase || isMetaPhase) && "opacity-80")}>
                        <Progress 
                            value={progress} 
                            variant={isError ? 'error' : 'default'} 
                            className={twMerge(
                                (isProcessingPhase || isMetaPhase) && "opacity-70"
                            )}
                        />
                        {/* Indeterminate overlay for processing phases if we are essentially 'done' with download */}
                        {(isProcessingPhase || isMetaPhase) && (
                            <div className="absolute inset-0 bg-yellow-400/20 animate-pulse rounded-full" />
                        )}
                     </div>
                )}
                
                {status === 'error' && (
                    <div className="text-xs text-theme-red bg-theme-red/10 border border-theme-red/20 p-3 rounded font-mono whitespace-pre-wrap">
                        {error}
                    </div>
                )}

                {/* Active Stats */}
                {(status === 'downloading' && !isProcessingPhase && !isMetaPhase) && (
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
          {(status === 'downloading' || status === 'pending') && (
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