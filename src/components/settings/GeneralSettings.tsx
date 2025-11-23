import { useAppContext } from '@/contexts/AppContext';
import { AlertCircle, FileKey, FolderOpen, Lock, X } from 'lucide-react';
import { open } from '@tauri-apps/api/dialog';
import { Button } from '../ui/Button';

const BROWSERS = [
    { label: 'None', value: 'none' },
    { label: 'Chrome', value: 'chrome' },
    { label: 'Firefox', value: 'firefox' },
    { label: 'Edge', value: 'edge' },
    { label: 'Brave', value: 'brave' },
    { label: 'Opera', value: 'opera' },
    { label: 'Vivaldi', value: 'vivaldi' },
    { label: 'Safari', value: 'safari' },
];

export function GeneralSettings() {
    const { 
        maxConcurrentDownloads, 
        maxTotalInstances, 
        setConcurrency,
        logLevel,
        setLogLevel,
        cookiesPath,
        setCookiesPath,
        cookiesBrowser,
        setCookiesBrowser
    } = useAppContext();

    const handleChange = (key: 'max_concurrent_downloads' | 'max_total_instances', value: number) => {
        let concurrent = maxConcurrentDownloads;
        let total = maxTotalInstances;

        if (key === 'max_concurrent_downloads') {
            concurrent = value;
            if (value > total) {
                total = value;
            }
        } else {
            total = value;
            if (value < concurrent) {
                concurrent = value;
            }
        }
        setConcurrency(concurrent, total);
    };

    const handleSelectCookieFile = async () => {
        try {
            const selected = await open({
                multiple: false,
                filters: [{ name: 'Text Files', extensions: ['txt'] }]
            });
            if (selected && typeof selected === 'string') {
                setCookiesPath(selected);
            }
        } catch (err) {
            console.error("Failed to select cookie file", err);
        }
    };

    return (
        <div className="space-y-8 animate-fade-in pb-6">
            {/* Cookies & Auth Section */}
            <div className="space-y-4">
                <div>
                    <h3 className="text-base font-medium text-zinc-100">Cookies & Authentication</h3>
                    <p className="text-sm text-zinc-500">
                        Load cookies to access age-restricted content or premium subscriptions.
                    </p>
                </div>
                <hr className="border-zinc-800" />
                
                <div className="grid gap-6">
                    {/* File Method */}
                    <div className="space-y-2">
                        <div className="flex justify-between items-center">
                            <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                <FileKey className="h-4 w-4 text-theme-cyan" />
                                Load from File (cookies.txt)
                            </label>
                            {cookiesPath && (
                                <button onClick={() => setCookiesPath(null)} className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1">
                                    <X className="h-3 w-3" /> Clear
                                </button>
                            )}
                        </div>
                        <div className="flex gap-2">
                             <input
                                type="text"
                                value={cookiesPath || ''}
                                readOnly
                                placeholder="No cookie file selected"
                                className={`flex-grow bg-zinc-900 border rounded-md px-3 py-2 text-sm text-zinc-400 focus:outline-none ${cookiesPath ? 'border-theme-cyan/50' : 'border-zinc-800'}`}
                             />
                             <Button 
                                type="button" 
                                variant="secondary" 
                                onClick={handleSelectCookieFile} 
                                className="border-zinc-700"
                             >
                                <FolderOpen className="h-4 w-4" />
                             </Button>
                        </div>
                    </div>
                    
                    <div className="relative flex py-1 items-center">
                        <div className="flex-grow border-t border-zinc-800"></div>
                        <span className="flex-shrink-0 mx-4 text-xs text-zinc-600 uppercase font-bold">OR</span>
                        <div className="flex-grow border-t border-zinc-800"></div>
                    </div>

                    {/* Browser Method */}
                    <div className="space-y-2">
                         <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                            <Lock className="h-4 w-4 text-amber-500" />
                            Extract from Browser
                         </label>
                         <select 
                             value={cookiesBrowser || 'none'}
                             onChange={(e) => setCookiesBrowser(e.target.value)}
                             className={`w-full bg-zinc-900 border rounded-md px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:ring-1 ${cookiesBrowser && cookiesBrowser !== 'none' ? 'border-amber-500/50 focus:ring-amber-500/50' : 'border-zinc-800 focus:ring-theme-cyan/50'}`}
                         >
                             {BROWSERS.map(b => (
                                 <option key={b.value} value={b.value}>{b.label}</option>
                             ))}
                         </select>
                         <p className="text-xs text-zinc-500">
                            Uses <code>--cookies-from-browser</code>. Ensure the browser is closed before starting downloads if you experience issues.
                         </p>
                    </div>
                </div>
            </div>

            {/* Queue Management Section */}
            <div className="space-y-4">
                <div>
                    <h3 className="text-base font-medium text-zinc-100">Queue Management</h3>
                    <p className="text-sm text-zinc-500">
                        Control how many downloads happen at once to manage bandwidth and CPU usage.
                    </p>
                </div>
                <hr className="border-zinc-800" />

                <div className="space-y-6">
                    <div className="space-y-3">
                        <div className="flex justify-between items-center">
                            <label className="text-sm font-medium text-zinc-300">Active Downloads</label>
                            <span className="text-theme-cyan font-mono font-bold">{maxConcurrentDownloads}</span>
                        </div>
                        <input
                            type="range"
                            min="1"
                            max="15"
                            value={maxConcurrentDownloads}
                            onChange={(e) => handleChange('max_concurrent_downloads', parseInt(e.target.value))}
                            className="w-full h-2 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-theme-cyan"
                        />
                    </div>

                    <div className="space-y-3">
                        <div className="flex justify-between items-center">
                            <label className="text-sm font-medium text-zinc-300">Total Concurrent Instances</label>
                            <span className="text-theme-cyan font-mono font-bold">{maxTotalInstances}</span>
                        </div>
                        <input
                            type="range"
                            min="1"
                            max="20"
                            value={maxTotalInstances}
                            onChange={(e) => handleChange('max_total_instances', parseInt(e.target.value))}
                            className="w-full h-2 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-theme-cyan"
                        />
                        <p className="text-xs text-zinc-500">
                            Includes active downloads AND videos that are currently merging/processing.
                        </p>
                    </div>
                </div>
            </div>

            {/* Debugging Section */}
            <div className="space-y-4">
                <div>
                    <h3 className="text-base font-medium text-zinc-100">Application Logging</h3>
                    <p className="text-sm text-zinc-500">
                        Configure system verbosity for troubleshooting. Logs are saved to <code>.multiyt-dlp/logs</code>.
                    </p>
                </div>
                <hr className="border-zinc-800" />

                <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1">
                        <label className="text-sm font-medium text-zinc-300">Log Verbosity</label>
                        <div className="text-xs text-zinc-500 max-w-xs">
                            Setting this to DEBUG or TRACE will generate large log files. Use only when reporting issues.
                        </div>
                    </div>
                    
                    <select 
                        value={logLevel}
                        onChange={(e) => setLogLevel(e.target.value)}
                        className="bg-zinc-900 border border-zinc-800 rounded-md px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-theme-cyan/50"
                    >
                        <option value="off">Off</option>
                        <option value="error">Error</option>
                        <option value="warn">Warn</option>
                        <option value="info">Info</option>
                        <option value="debug">Debug</option>
                        <option value="trace">Trace</option>
                    </select>
                </div>

                {logLevel === 'debug' || logLevel === 'trace' ? (
                    <div className="flex items-center gap-2 text-xs text-amber-500 bg-amber-950/20 border border-amber-900/50 p-3 rounded">
                        <AlertCircle className="h-4 w-4" />
                        High verbosity enabled. Performance may be slightly impacted.
                    </div>
                ) : null}
            </div>
        </div>
    );
}