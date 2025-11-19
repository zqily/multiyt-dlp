import { Download } from '@/types';
import { Progress } from './ui/Progress';
import { Button } from './ui/Button';
import { X, FileVideo, Clock, CheckCircle2, AlertTriangle, Headphones } from 'lucide-react';
import { twMerge } from 'tailwind-merge';

interface DownloadItemProps {
  download: Download;
  onCancel: (jobId: string) => void;
}

// Define the interface to ensure all themes are compatible
interface Theme {
    icon: React.ElementType;
    text: string;
    border: string;
    bg: string;
    shadow: string;
    progress: 'cyan' | 'pink' | 'green' | 'red';
    label: string;
}

export function DownloadItem({ download, onCancel }: DownloadItemProps) {
  const { jobId, url, status, progress, speed, eta, error, filename, phase, preset } = download;

  const displayTitle = filename || url;
  const isAudio = preset?.startsWith('audio');

  // --- Theme Logic ---
  
  // Base Themes
  const themes: Record<string, Theme> = {
    video: {
        icon: FileVideo,
        text: 'text-synth-cyan',
        border: 'border-synth-cyan',
        bg: 'bg-synth-cyan/10',
        shadow: 'shadow-neon-cyan',
        progress: 'cyan',
        label: 'VIDEO'
    },
    audio: {
        icon: Headphones,
        text: 'text-synth-pink',
        border: 'border-synth-pink',
        bg: 'bg-synth-pink/10',
        shadow: 'shadow-neon-pink',
        progress: 'pink',
        label: 'AUDIO'
    },
    completed: {
        icon: CheckCircle2,
        text: 'text-green-400',
        border: 'border-green-500',
        bg: 'bg-green-500/10',
        shadow: 'shadow-none',
        progress: 'green',
        label: 'DONE'
    },
    error: {
        icon: AlertTriangle,
        text: 'text-red-500',
        border: 'border-red-500',
        bg: 'bg-red-500/10',
        shadow: 'shadow-none',
        progress: 'red',
        label: 'ERROR'
    },
    cancelled: {
        icon: X,
        text: 'text-gray-500',
        border: 'border-gray-600',
        bg: 'bg-gray-800',
        shadow: 'shadow-none',
        progress: 'cyan',
        label: 'CANCELLED'
    }
  };

  // Select Theme based on Status > Type
  // We explicitly type this as Theme so it can accept any variant
  let currentTheme: Theme = isAudio ? themes.audio : themes.video;

  if (status === 'completed') currentTheme = themes.completed;
  if (status === 'error') currentTheme = themes.error;
  if (status === 'cancelled') currentTheme = themes.cancelled;

  const Icon = currentTheme.icon;
  
  // Determine badge text (e.g. "MP3" or "VIDEO")
  let badgeText = currentTheme.label;
  if (status === 'downloading' || status === 'pending') {
      if (preset) {
          // Parse preset like "audio_mp3" -> "MP3"
          const parts = preset.split('_');
          if (parts.length > 1 && parts[1] !== 'best') {
             badgeText = parts[1].toUpperCase();
          }
      }
  }

  return (
    <div className={twMerge(
        "group animate-slide-in relative bg-synth-dark border rounded-lg p-4 overflow-hidden transition-all duration-300 hover:shadow-lg hover:bg-synth-navy",
        currentTheme.border,
        // Subtle glow on hover based on type
        status === 'downloading' && isAudio ? "hover:shadow-neon-pink" : "",
        status === 'downloading' && !isAudio ? "hover:shadow-neon-cyan" : ""
    )}>
      
      <div className="flex items-start gap-4 relative z-10">
        {/* Icon Box */}
        <div className={twMerge(
            "h-12 w-12 flex-shrink-0 rounded-lg flex items-center justify-center border transition-all duration-500",
            currentTheme.bg,
            currentTheme.border,
            currentTheme.text,
            status === 'downloading' ? currentTheme.shadow : "",
            status === 'downloading' ? "animate-pulse" : ""
        )}>
          <Icon className="h-6 w-6" />
        </div>
        
        <div className="flex-grow min-w-0 space-y-2">
            {/* Title Row */}
            <div className="flex justify-between items-start gap-2">
                 <p className="text-sm font-medium truncate text-white font-mono tracking-tight flex-grow" title={displayTitle}>
                    {displayTitle}
                 </p>
                 
                 {/* Percentage Badge */}
                 {(status === 'downloading' || status === 'pending') && (
                    <span className={twMerge("text-xs font-mono px-2 py-0.5 rounded bg-synth-navy border min-w-[3rem] text-center", currentTheme.text, currentTheme.border)}>
                        {progress.toFixed(0)}%
                    </span>
                 )}
                 
                 {/* Status Badge for non-active states */}
                 {(status === 'completed' || status === 'error' || status === 'cancelled') && (
                     <span className={twMerge("text-xs font-bold font-mono px-2 py-0.5 rounded bg-synth-navy border", currentTheme.text, currentTheme.border)}>
                        {currentTheme.label}
                     </span>
                 )}
            </div>
            
            {/* Progress Bar */}
            <Progress value={progress} variant={currentTheme.progress} />
            
            {/* Meta Data Grid */}
            <div className="grid grid-cols-2 gap-2 text-xs font-mono text-synth-light/60 mt-2">
                
                {/* Left: Type/Phase */}
                <div className="flex items-center gap-1.5 truncate">
                   {!['completed', 'error', 'cancelled'].includes(status) && (
                       <span className={twMerge("font-bold px-1.5 rounded text-[10px] border", currentTheme.text, currentTheme.border)}>
                           {badgeText}
                       </span>
                   )}
                   <span className={currentTheme.text}>
                     {status === 'downloading' ? (phase || 'Processing...') : ''}
                     {status === 'completed' && <span className="text-green-400">Saved to disk</span>}
                   </span>
                </div>

                {/* Right: Stats */}
                {(status === 'downloading') && (
                    <div className="flex items-center justify-end gap-3">
                        <span title="Speed" className="flex items-center gap-1 text-white/80">
                            ⚡ {speed}
                        </span>
                        <span title="ETA" className="flex items-center gap-1 text-white/80">
                            <Clock className="h-3 w-3" /> {eta}
                        </span>
                    </div>
                )}
                 {status === 'error' && (
                    <span className="col-span-2 text-red-400 truncate font-bold" title={error}>{error}</span>
                )}
                 {status === 'completed' && (
                     <div className="flex items-center justify-end">
                        <span className="text-green-400/70">Ready</span>
                     </div>
                 )}
            </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col justify-center">
          {(status === 'downloading' || status === 'pending') && (
             <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => onCancel(jobId)} 
                className="text-gray-500 hover:text-red-500 hover:bg-red-500/10 h-8 w-8"
                title="Cancel Download"
             >
                <X className="h-4 w-4" />
              </Button>
          )}
        </div>
      </div>
    </div>
  );
}