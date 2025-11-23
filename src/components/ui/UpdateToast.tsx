import { useEffect, useState } from 'react';
import { useAppContext } from '@/contexts/AppContext';
import { X, Download, PartyPopper } from 'lucide-react';
import { openExternalLink } from '@/api/invoke';
import { Button } from './Button';

export function UpdateToast() {
    const { isUpdateAvailable, latestVersion, currentVersion } = useAppContext();
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        if (isUpdateAvailable) {
            // Small delay to not overwhelm on launch
            const timer = setTimeout(() => setVisible(true), 2000);
            return () => clearTimeout(timer);
        }
    }, [isUpdateAvailable]);

    if (!visible) return null;

    const handleUpdate = () => {
        openExternalLink("https://github.com/zqily/multiyt-dlp/releases/latest");
        setVisible(false);
    };

    return (
        <div className="fixed bottom-6 right-6 z-50 animate-fade-in">
            <div className="bg-zinc-900 border border-theme-cyan/50 shadow-[0_0_20px_-5px_rgba(0,242,234,0.3)] rounded-lg p-4 w-80 flex flex-col gap-3">
                <div className="flex justify-between items-start">
                    <div className="flex items-center gap-2 text-theme-cyan font-bold">
                        <PartyPopper className="h-5 w-5" />
                        <span>Update Available</span>
                    </div>
                    <button 
                        onClick={() => setVisible(false)} 
                        className="text-zinc-500 hover:text-white transition-colors"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>
                
                <div className="text-sm text-zinc-300">
                    A new version of Multiyt-dlp is available!
                </div>
                
                <div className="flex items-center gap-3 text-xs font-mono bg-black/30 p-2 rounded border border-zinc-800">
                    <div className="text-zinc-500">v{currentVersion}</div>
                    <div className="text-zinc-600">→</div>
                    <div className="text-theme-cyan font-bold">v{latestVersion}</div>
                </div>

                <div className="flex gap-2 mt-1">
                    <Button 
                        size="sm" 
                        variant="neon" 
                        className="w-full h-8 text-xs"
                        onClick={handleUpdate}
                    >
                        <Download className="h-3 w-3 mr-2" />
                        Download
                    </Button>
                    <Button 
                        size="sm" 
                        variant="secondary" 
                        className="w-full h-8 text-xs"
                        onClick={() => setVisible(false)}
                    >
                        Later
                    </Button>
                </div>
            </div>
        </div>
    );
}