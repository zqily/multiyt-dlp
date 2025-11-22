import { useState, useEffect, useRef } from 'react';
import { checkDependencies, openExternalLink, closeSplash } from '@/api/invoke';
import icon from '@/assets/icon.png';
import { RefreshCw, ExternalLink, Check } from 'lucide-react';
import { Button } from './ui/Button';

const YT_DLP_RELEASE_URL = 'https://github.com/yt-dlp/yt-dlp/releases/latest';
const FFMPEG_URL = 'https://ffmpeg.org/download.html';

export function SplashWindow() {
  const [status, setStatus] = useState<'loading' | 'error' | 'ready'>('loading');
  const [message, setMessage] = useState('Initializing Core...');
  const [missingDeps, setMissingDeps] = useState<{ yt_dlp: boolean; ffmpeg: boolean }>({ yt_dlp: false, ffmpeg: false });
  
  const hasRun = useRef(false);

  const runChecks = async () => {
    if (hasRun.current) return;
    hasRun.current = true;

    setStatus('loading');
    setMessage('Scanning System Environment...');
    
    try {
      await new Promise(resolve => setTimeout(resolve, 1500));

      const deps = await checkDependencies();
      
      // Updated check logic for new object structure
      const ytMissing = !deps.yt_dlp.available;
      const ffmpegMissing = !deps.ffmpeg.available;

      if (ytMissing || ffmpegMissing) {
        setMissingDeps({
          yt_dlp: ytMissing,
          ffmpeg: ffmpegMissing
        });
        setStatus('error');
        setMessage('Critical Components Missing');
      } else {
        setStatus('ready');
        setMessage('System Optimal. Launching...');
        
        setTimeout(async () => {
            try {
                await closeSplash();
            } catch (err) {
                setMessage("Failed to launch Main Window");
                setStatus('error');
            }
        }, 800);
      }
    } catch (e) {
      setStatus('error');
      setMessage('Initialization Failed');
    }
  };

  useEffect(() => {
    runChecks();
  }, []);

  return (
    <div className="h-screen w-screen bg-zinc-950 flex flex-col items-center justify-center relative overflow-hidden border-2 border-zinc-900 cursor-default select-none">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(18,18,18,0)_1px,transparent_1px),linear-gradient(90deg,rgba(18,18,18,0)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_50%,black,transparent)] pointer-events-none" />

      <div className="z-10 flex flex-col items-center w-full max-w-[320px]">
        <div className="glitch-wrapper mb-8">
            <div 
                className="glitch-logo" 
                style={{ backgroundImage: `url(${icon})` }} 
            />
        </div>

        <div className="text-center space-y-2 mb-6">
            <h1 className={`font-mono font-bold text-lg tracking-wider uppercase transition-colors duration-300 ${
                status === 'error' ? 'text-theme-red' : 'text-theme-cyan'
            }`}>
                {status === 'loading' ? 'Loading...' : status === 'error' ? 'Error' : 'Ready'}
            </h1>
            <p className="text-zinc-500 text-xs font-medium">{message}</p>
        </div>

        {status === 'error' && (
            <div className="w-full space-y-3 animate-fade-in bg-black/50 p-4 rounded-lg border border-zinc-800 backdrop-blur-sm">
                <div className="space-y-2">
                     <div className="flex items-center justify-between text-xs">
                        <span className="text-zinc-400">yt-dlp</span>
                        {missingDeps.yt_dlp ? (
                             <button onClick={() => openExternalLink(YT_DLP_RELEASE_URL)} className="text-theme-red hover:underline flex items-center gap-1">
                                <ExternalLink className="h-3 w-3" /> Install
                             </button>
                        ) : <Check className="h-3 w-3 text-emerald-500" />}
                     </div>
                     <div className="flex items-center justify-between text-xs">
                        <span className="text-zinc-400">FFmpeg</span>
                        {missingDeps.ffmpeg ? (
                             <button onClick={() => openExternalLink(FFMPEG_URL)} className="text-theme-red hover:underline flex items-center gap-1">
                                <ExternalLink className="h-3 w-3" /> Install
                             </button>
                        ) : <Check className="h-3 w-3 text-emerald-500" />}
                     </div>
                </div>
                
                <Button 
                    size="sm" 
                    className="w-full mt-2 border-zinc-700 bg-zinc-800 hover:bg-zinc-700"
                    onClick={() => { hasRun.current = false; runChecks(); }}
                >
                    <RefreshCw className="mr-2 h-3 w-3" /> Retry Connection
                </Button>
            </div>
        )}

        {status === 'loading' && (
            <div className="w-32 h-1 bg-zinc-900 rounded-full overflow-hidden">
                <div className="h-full bg-theme-cyan animate-[shimmer_1s_infinite_linear] w-full origin-left scale-x-50" />
            </div>
        )}
      </div>
      
      <div className="absolute bottom-4 text-[10px] text-zinc-700 font-mono">
         v0.1.0-alpha
      </div>
    </div>
  );
}