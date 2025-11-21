import { ReactNode, useEffect, useState } from 'react';
import { checkDependencies, openExternalLink } from '@/api/invoke';
import { Button } from './ui/Button';
import { ExternalLink, RefreshCw, Check } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { useAppContext } from '@/contexts/AppContext';

const YT_DLP_RELEASE_URL = 'https://github.com/yt-dlp/yt-dlp/releases/latest';
const FFMPEG_URL = 'https://ffmpeg.org/download.html';

export function EnvironmentGate({ children }: { children: ReactNode }) {
  const [isReady, setIsReady] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [missingDeps, setMissingDeps] = useState<{ yt_dlp: boolean; ffmpeg: boolean }>({ yt_dlp: false, ffmpeg: false });
  
  const { setIsJsRuntimeMissing } = useAppContext();

  const performCheck = async () => {
    setIsLoading(true);
    try {
        const deps = await checkDependencies();
        
        const criticalMissing = !deps.yt_dlp || !deps.ffmpeg;
        
        setMissingDeps({
            yt_dlp: !deps.yt_dlp,
            ffmpeg: !deps.ffmpeg
        });

        // JS Runtime is not critical for app startup, but we warn about it globally
        setIsJsRuntimeMissing(!deps.js_runtime);
        
        setIsReady(!criticalMissing);
    } catch (e) {
        console.error("Failed to check dependencies", e);
        // Fail safe
        setIsReady(false);
    }
    setIsLoading(false);
  };

  useEffect(() => {
    performCheck();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-zinc-950 text-zinc-400 text-sm">
        <p className="animate-pulse">Scanning system environment...</p>
      </div>
    );
  }

  if (!isReady) {
    return (
      <div className="flex items-center justify-center h-screen p-4 bg-zinc-950">
        <Card className="max-w-md w-full bg-zinc-900 border-zinc-800">
            <CardHeader>
                <CardTitle className="text-lg text-red-400">Missing Critical Dependencies</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
                <p className="text-sm text-zinc-300 leading-relaxed">
                    Multiyt-dlp relies on external tools to function. Please ensure the following are installed and available in your system PATH.
                </p>
                
                <div className="space-y-3">
                    {/* yt-dlp status */}
                    <div className="flex items-center justify-between p-3 rounded bg-zinc-950 border border-zinc-800">
                        <div className="flex items-center gap-3">
                            <div className={`h-2 w-2 rounded-full ${missingDeps.yt_dlp ? 'bg-red-500' : 'bg-emerald-500'}`} />
                            <span className="text-sm font-medium text-zinc-200">yt-dlp</span>
                        </div>
                        {missingDeps.yt_dlp ? (
                            <Button variant="ghost" size="sm" onClick={() => openExternalLink(YT_DLP_RELEASE_URL)}>
                                <ExternalLink className="h-3 w-3 mr-1" /> Install
                            </Button>
                        ) : <Check className="h-4 w-4 text-emerald-500" />}
                    </div>

                    {/* ffmpeg status */}
                    <div className="flex items-center justify-between p-3 rounded bg-zinc-950 border border-zinc-800">
                        <div className="flex items-center gap-3">
                            <div className={`h-2 w-2 rounded-full ${missingDeps.ffmpeg ? 'bg-red-500' : 'bg-emerald-500'}`} />
                            <span className="text-sm font-medium text-zinc-200">FFmpeg</span>
                        </div>
                         {missingDeps.ffmpeg ? (
                            <Button variant="ghost" size="sm" onClick={() => openExternalLink(FFMPEG_URL)}>
                                <ExternalLink className="h-3 w-3 mr-1" /> Install
                            </Button>
                        ) : <Check className="h-4 w-4 text-emerald-500" />}
                    </div>
                </div>

                <Button variant="default" className="w-full" onClick={performCheck}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Re-scan System
                </Button>
            </CardContent>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}