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
      <div className="flex items-center justify-center h-screen">
        <p>Checking environment...</p>
      </div>
    );
  }

  if (!isReady) {
    return (
      <div className="flex items-center justify-center h-screen p-4">
        <Card className="max-w-md">
            <CardHeader>
                <CardTitle className="text-xl">yt-dlp Not Found</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <p>
                    This application requires <code>yt-dlp</code> to be installed and available in your system's PATH.
                </p>
                <p>
                    Please download the latest version for your operating system and place it in a directory included in your PATH.
                </p>
                <div className="flex gap-2">
                    <Button onClick={() => openExternalLink(YT_DLP_RELEASE_URL)}>
                        <ExternalLink className="mr-2 h-4 w-4" />
                        Get yt-dlp
                    </Button>
                    <Button variant="secondary" onClick={checkEnvironment}>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Check Again
                    </Button>
                </div>
            </CardContent>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}
