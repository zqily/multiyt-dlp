import { useAppContext } from '@/contexts/AppContext';
import { AlertCircle } from 'lucide-react';

export function GeneralSettings() {
    const { 
        maxConcurrentDownloads, 
        maxTotalInstances, 
        setConcurrency,
        logLevel,
        setLogLevel
    } = useAppContext();

    const handleChange = (key: 'max_concurrent_downloads' | 'max_total_instances', value: number) => {
        let concurrent = maxConcurrentDownloads;
        let total = maxTotalInstances;

        // Enforce logic: Total >= Concurrent
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

    return (
        <div className="space-y-8 animate-fade-in pb-6">
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