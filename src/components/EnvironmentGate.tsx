import { ReactNode, useEffect, useState } from 'react';
import { checkYtDlpPath, openExternalLink } from '@/api/invoke';
import { Button } from './ui/Button';
import { ExternalLink, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';

const YT_DLP_RELEASE_URL = 'https://github.com/yt-dlp/yt-dlp/releases/latest';

export function EnvironmentGate({ children }: { children: ReactNode }) {
  const [isReady, setIsReady] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const checkEnvironment = async () => {
    setIsLoading(true);
    const hasYtDlp = await checkYtDlpPath();
    setIsReady(hasYtDlp);
    setIsLoading(false);
  };

  useEffect(() => {
    checkEnvironment();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-zinc-950 text-zinc-400 text-sm">
        <p>Initializing environment...</p>
      </div>
    );
  }

  if (!isReady) {
    return (
      <div className="flex items-center justify-center h-screen p-4 bg-zinc-950">
        <Card className="max-w-md w-full bg-zinc-900 border-zinc-800">
            <CardHeader>
                <CardTitle className="text-lg text-red-400">Dependency Missing</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <p className="text-sm text-zinc-300 leading-relaxed">
                    Multiyt-dlp requires the <code>yt-dlp</code> executable to be installed and available in your system's PATH.
                </p>
                <div className="flex gap-3 pt-2">
                    <Button variant="outline" className="flex-1" onClick={() => openExternalLink(YT_DLP_RELEASE_URL)}>
                        <ExternalLink className="mr-2 h-4 w-4" />
                        Get yt-dlp
                    </Button>
                    <Button variant="default" className="flex-1" onClick={checkEnvironment}>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Retry
                    </Button>
                </div>
            </CardContent>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}