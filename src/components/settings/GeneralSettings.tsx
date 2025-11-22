import { useAppContext } from '@/contexts/AppContext';

export function GeneralSettings() {
    const { 
        maxConcurrentDownloads, 
        maxTotalInstances, 
        setConcurrency 
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

        // Use Context function to update state and save to disk consistently
        setConcurrency(concurrent, total);
    };

    return (
        <div className="space-y-6 animate-fade-in">
            <div>
                <h3 className="text-base font-medium text-zinc-100">Queue Management</h3>
                <p className="text-sm text-zinc-500">
                    Control how many downloads happen at once to manage bandwidth and CPU usage.
                </p>
            </div>
            <hr className="border-zinc-800" />

            <div className="space-y-8">
                <div className="space-y-4">
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
                    <p className="text-xs text-zinc-500">
                        The number of videos actively downloading data from the internet simultaneously.
                    </p>
                </div>

                <div className="space-y-4">
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
                        Useful to start new downloads while ffmpeg is busy merging previous ones.
                    </p>
                </div>
            </div>
        </div>
    );
}