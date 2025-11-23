import { useState, useEffect, useRef } from 'react';
import { checkDependencies, installDependency, closeSplash } from '@/api/invoke';
import { listen } from '@tauri-apps/api/event';
import { getVersion } from '@tauri-apps/api/app';
import icon from '@/assets/icon.png';
import { DownloadCloud, Check, AlertTriangle } from 'lucide-react';
import { Button } from './ui/Button';
import { Progress } from './ui/Progress';

interface InstallProgress {
    name: string;
    percentage: number;
    status: string;
}

export function SplashWindow() {
  const [status, setStatus] = useState<'loading' | 'error' | 'ready' | 'installing'>('loading');
  const [message, setMessage] = useState('Initializing Core...');
  const [missingDeps, setMissingDeps] = useState<{ yt_dlp: boolean; ffmpeg: boolean }>({ yt_dlp: false, ffmpeg: false });
  const [installState, setInstallState] = useState<InstallProgress>({ name: '', percentage: 0, status: '' });
  const [appVersion, setAppVersion] = useState('');
  
  const hasRun = useRef(false);

  const runChecks = async () => {
    if (hasRun.current) return;
    hasRun.current = true;

    setStatus('loading');
    setMessage('Scanning System Environment...');
    
    try {
      await new Promise(resolve => setTimeout(resolve, 800));
      const deps = await checkDependencies();
      
      const ytMissing = !deps.yt_dlp.available;
      const ffmpegMissing = !deps.ffmpeg.available;

      if (ytMissing || ffmpegMissing) {
        setMissingDeps({
          yt_dlp: ytMissing,
          ffmpeg: ffmpegMissing
        });
        setStatus('error');
        setMessage('Dependencies Missing');
      } else {
        setStatus('ready');
        setMessage('System Optimal. Launching...');
        setTimeout(async () => {
            await closeSplash();
        }, 800);
      }
    } catch (e) {
      setStatus('error');
      setMessage('Initialization Failed');
    }
  };

  const handleAutoInstall = async () => {
      setStatus('installing');
      try {
          if (missingDeps.yt_dlp) {
              setInstallState({ name: 'yt-dlp', percentage: 0, status: 'Starting...' });
              await installDependency('yt-dlp');
          }
          if (missingDeps.ffmpeg) {
              setInstallState({ name: 'ffmpeg', percentage: 0, status: 'Starting...' });
              await installDependency('ffmpeg');
          }
          // Re-run checks
          hasRun.current = false;
          runChecks();
      } catch (e) {
          setStatus('error');
          setMessage('Installation Failed: ' + String(e));
      }
  };

  useEffect(() => {
    getVersion().then(v => setAppVersion(`v${v}`));

    const unlisten = listen<InstallProgress>('install-progress', (event) => {
        setInstallState(event.payload);
    });

    const img = new Image();
    img.src = icon;
    const startApp = () => { requestAnimationFrame(() => { runChecks(); }); };

    if (img.complete) startApp();
    else { img.onload = startApp; img.onerror = startApp; }

    return () => { unlisten.then(f => f()); };
  }, []);

  return (
    <div className="h-screen w-screen bg-zinc-950 flex flex-col items-center justify-center relative overflow-hidden border-2 border-zinc-900 cursor-default select-none">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(18,18,18,0)_1px,transparent_1px),linear-gradient(90deg,rgba(18,18,18,0)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_50%,black,transparent)] pointer-events-none" />

      <div className="z-10 flex flex-col items-center w-full max-w-[340px]">
        <div className="glitch-wrapper mb-8">
            <div className="glitch-logo" style={{ backgroundImage: `url(${icon})` }} />
        </div>

        <div className="text-center space-y-2 mb-6">
            <h1 className={`font-mono font-bold text-lg tracking-wider uppercase transition-colors duration-300 ${
                status === 'error' ? 'text-theme-red' : 'text-theme-cyan'
            }`}>
                {status === 'loading' ? 'Loading...' : status === 'installing' ? 'Installing...' : status === 'error' ? 'Action Required' : 'Ready'}
            </h1>
            <p className="text-zinc-500 text-xs font-medium">{message}</p>
        </div>

        {status === 'installing' && (
            <div className="w-full space-y-2 animate-fade-in bg-black/50 p-4 rounded-lg border border-zinc-800 backdrop-blur-sm">
                <div className="flex justify-between text-xs text-zinc-300 mb-1">
                    <span className="font-bold uppercase">{installState.name}</span>
                    <span>{installState.status}</span>
                </div>
                <Progress value={installState.percentage} className="h-1.5" />
            </div>
        )}

        {status === 'error' && (
            <div className="w-full space-y-3 animate-fade-in bg-black/50 p-4 rounded-lg border border-zinc-800 backdrop-blur-sm">
                <div className="space-y-2">
                     <div className="flex items-center justify-between text-xs">
                        <span className="text-zinc-400">yt-dlp</span>
                        {missingDeps.yt_dlp ? <span className="text-theme-red font-bold flex items-center gap-1"><AlertTriangle className="h-3 w-3"/> Missing</span> : <Check className="h-3 w-3 text-emerald-500" />}
                     </div>
                     <div className="flex items-center justify-between text-xs">
                        <span className="text-zinc-400">FFmpeg</span>
                        {missingDeps.ffmpeg ? <span className="text-theme-red font-bold flex items-center gap-1"><AlertTriangle className="h-3 w-3"/> Missing</span> : <Check className="h-3 w-3 text-emerald-500" />}
                     </div>
                </div>
                
                <Button 
                    size="sm" 
                    className="w-full mt-2 border-theme-cyan/50 bg-theme-cyan/10 text-theme-cyan hover:bg-theme-cyan/20"
                    onClick={handleAutoInstall}
                >
                    <DownloadCloud className="mr-2 h-3 w-3" /> Download & Install
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
         {appVersion || '...'}
      </div>
    </div>
  );
}