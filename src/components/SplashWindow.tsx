import { useState, useEffect, useRef } from 'react';
import { syncDependencies, closeSplash } from '@/api/invoke';
import { listen } from '@tauri-apps/api/event';
import { getVersion } from '@tauri-apps/api/app';
import icon from '@/assets/icon.png';
import { RefreshCw, AlertTriangle, ShieldCheck } from 'lucide-react';
import { Progress } from './ui/Progress';
import { Button } from './ui/Button';

interface InstallProgress {
    name: string;
    percentage: number;
    status: string;
}

export function SplashWindow() {
  const [status, setStatus] = useState<'init' | 'syncing' | 'ready' | 'error'>('init');
  const [message, setMessage] = useState('Initializing Core...');
  const [installState, setInstallState] = useState<InstallProgress>({ name: '', percentage: 0, status: '' });
  const [appVersion, setAppVersion] = useState('');
  const [errorDetails, setErrorDetails] = useState('');
  
  const hasRun = useRef(false);

  const startStartupSync = async () => {
    if (hasRun.current) return;
    hasRun.current = true;

    setStatus('syncing');
    setMessage('Checking System Integrity...');
    
    try {
      // Allow the UI to render the 'Syncing' state briefly before heavy lifting
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Call the all-in-one sync command
      const finalDeps = await syncDependencies();

      // Check critical failures
      if (!finalDeps.yt_dlp.available || !finalDeps.ffmpeg.available) {
          throw new Error("Critical dependencies failed to install.");
      }

      setStatus('ready');
      setMessage('System Optimal. Launching...');
      
      setTimeout(async () => {
          await closeSplash();
      }, 800);

    } catch (e) {
      console.error(e);
      setStatus('error');
      setMessage('Startup Failed');
      setErrorDetails(String(e));
    }
  };

  useEffect(() => {
    getVersion().then(v => setAppVersion(`v${v}`));

    const unlisten = listen<InstallProgress>('install-progress', (event) => {
        setInstallState(event.payload);
        setStatus('syncing'); // Ensure we show syncing UI during events
    });

    const img = new Image();
    img.src = icon;
    const startApp = () => { requestAnimationFrame(() => { startStartupSync(); }); };

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
                {status === 'init' && 'Initializing'}
                {status === 'syncing' && 'Syncing Resources'}
                {status === 'ready' && 'Ready'}
                {status === 'error' && 'Critical Error'}
            </h1>
            <p className="text-zinc-500 text-xs font-medium min-h-[16px]">{message}</p>
        </div>

        {/* Syncing Progress UI */}
        {status === 'syncing' && (
            <div className="w-full space-y-3 animate-fade-in bg-black/50 p-4 rounded-lg border border-zinc-800 backdrop-blur-sm">
                <div className="flex items-center gap-2 text-xs text-zinc-300">
                    <RefreshCw className="h-3 w-3 animate-spin text-theme-cyan" />
                    <span className="font-bold uppercase">{installState.name || 'Core System'}</span>
                </div>
                
                {installState.status && (
                    <div className="text-[10px] text-zinc-500 font-mono truncate">
                        {installState.status}
                    </div>
                )}
                
                <Progress value={installState.percentage || 0} className="h-1" />
            </div>
        )}

        {/* Ready UI */}
        {status === 'ready' && (
             <div className="flex items-center gap-2 text-emerald-500 animate-fade-in bg-emerald-500/10 px-4 py-2 rounded-full border border-emerald-500/20">
                <ShieldCheck className="h-4 w-4" />
                <span className="text-xs font-bold uppercase tracking-wider">Integrity Verified</span>
             </div>
        )}

        {/* Error UI */}
        {status === 'error' && (
            <div className="w-full space-y-3 animate-fade-in bg-black/50 p-4 rounded-lg border border-theme-red/30 backdrop-blur-sm">
                <div className="flex items-center gap-2 text-theme-red text-xs font-bold uppercase">
                    <AlertTriangle className="h-4 w-4" />
                    <span>Sync Failed</span>
                </div>
                <div className="text-[10px] text-zinc-400 font-mono bg-zinc-900 p-2 rounded border border-zinc-800 break-all">
                    {errorDetails || "Unknown error occurred during startup sync."}
                </div>
                
                <Button 
                    size="sm" 
                    className="w-full mt-2"
                    onClick={() => { hasRun.current = false; startStartupSync(); }}
                >
                    Retry Sync
                </Button>
            </div>
        )}

        {/* Initial Loading Spinner */}
        {status === 'init' && (
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