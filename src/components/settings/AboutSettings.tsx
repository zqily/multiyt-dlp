import { useEffect, useState } from 'react';
import { getVersion, getName } from '@tauri-apps/api/app';
import { checkDependencies, installDependency } from '@/api/invoke';
import { DependencyInfo } from '@/types';
import { Copy, Check, Terminal, AlertCircle, Cpu, Download, Loader2 } from 'lucide-react';
import icon from '@/assets/icon.png';
import { Button } from '../ui/Button';

const DependencyRow = ({ info, onInstall }: { info: DependencyInfo, onInstall?: () => void }) => {
    const [copied, setCopied] = useState(false);
    
    const handleCopy = () => {
        if (info.path) {
            navigator.clipboard.writeText(info.path);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    return (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-md bg-zinc-800 text-zinc-400">
                        <Terminal className="h-4 w-4" />
                    </div>
                    <div>
                        <div className="font-semibold text-zinc-200 text-sm capitalize">{info.name}</div>
                        {info.available ? (
                             <div className="text-[10px] text-emerald-500 font-mono flex items-center gap-1">
                                <Check className="h-3 w-3" /> {info.version || 'Detected'}
                             </div>
                        ) : (
                             <div className="text-[10px] text-theme-red font-mono flex items-center gap-1">
                                <AlertCircle className="h-3 w-3" /> Not Found
                             </div>
                        )}
                    </div>
                </div>
                {onInstall && !info.available && (
                    <Button size="sm" variant="outline" onClick={onInstall} className="h-7 text-xs">
                        <Download className="h-3 w-3 mr-1" /> Install
                    </Button>
                )}
            </div>

            {info.path && (
                <div className="relative group">
                    <input 
                        readOnly
                        value={info.path} 
                        className="w-full bg-zinc-950 text-zinc-500 text-xs font-mono py-2 px-3 rounded border border-zinc-800 focus:outline-none"
                    />
                    <button 
                        onClick={handleCopy}
                        className="absolute right-1 top-1 bottom-1 px-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded text-xs flex items-center gap-2 transition-colors"
                        title="Copy Path"
                    >
                        {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    </button>
                </div>
            )}
        </div>
    );
};

export function AboutSettings() {
    const [appName, setAppName] = useState("Loading...");
    const [appVersion, setAppVersion] = useState("0.0.0");
    const [deps, setDeps] = useState<{ yt_dlp?: DependencyInfo, ffmpeg?: DependencyInfo, js_runtime?: DependencyInfo }>({});
    const [loading, setLoading] = useState(true);
    const [installing, setInstalling] = useState<string | null>(null);

    const fetchData = async () => {
        try {
            const name = await getName();
            const ver = await getVersion();
            const dependencies = await checkDependencies();
            setAppName(name);
            setAppVersion(ver);
            setDeps(dependencies);
        } catch (e) {
            console.error("Failed to fetch system info", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleInstall = async (name: string) => {
        setInstalling(name);
        try {
            await installDependency(name);
            await fetchData();
        } catch (e) {
            alert(`Failed to install ${name}: ${e}`);
        } finally {
            setInstalling(null);
        }
    };

    if (loading) {
        return <div className="p-10 text-center text-zinc-500 text-sm animate-pulse">Scanning System...</div>;
    }

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header Area */}
            <div className="flex items-center gap-5 pb-4 border-b border-zinc-800">
                <img src={icon} className="w-16 h-16 rounded-xl shadow-glow-cyan" alt="App Icon" />
                <div>
                    <h2 className="text-xl font-bold text-zinc-100 tracking-tight">{appName}</h2>
                    <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs font-mono text-zinc-500">v{appVersion}</span>
                        <span className="px-1.5 py-0.5 text-[9px] bg-theme-cyan/10 text-theme-cyan border border-theme-cyan/20 rounded uppercase font-bold tracking-wider">
                            Stable
                        </span>
                    </div>
                </div>
                {installing && (
                    <div className="ml-auto flex items-center gap-2 text-theme-cyan text-xs animate-pulse">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Installing {installing}...
                    </div>
                )}
            </div>

            {/* Dependencies Grid */}
            <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm text-zinc-400 font-medium">
                    <Cpu className="h-4 w-4" />
                    <span>System Dependencies</span>
                </div>
                
                <div className="grid grid-cols-1 gap-3">
                    {deps.yt_dlp && <DependencyRow info={deps.yt_dlp} />}
                    {deps.ffmpeg && <DependencyRow info={deps.ffmpeg} />}
                    {deps.js_runtime && <DependencyRow 
                        info={deps.js_runtime} 
                        onInstall={() => handleInstall('js_runtime')} 
                    />}
                </div>
            </div>

            <div className="pt-4 text-center">
                <p className="text-[10px] text-zinc-600">
                    Binaries are installed to <code>%AppData%/multiyt-dlp/bin</code> and prioritized over system paths.
                </p>
            </div>
        </div>
    );
}