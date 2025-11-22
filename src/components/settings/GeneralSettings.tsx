import React from 'react';
import { useAppContext } from '@/contexts/AppContext';

export function GeneralSettings() {
    const { defaultDownloadPath, getTemplateString, filenameTemplateBlocks } = useAppContext();
    const [config, setConfig] = React.useState({ max_concurrent_downloads: 4, max_total_instances: 10 });

    React.useEffect(() => {
        // Load config via context hook wrapper if we had exposed full config object
        // For now, we need to fetch it or rely on Context to provide these values.
        // Given current AppContext structure, we need to manually invoke getAppConfig here or expand context.
        // Assuming we invoke directly for this component to keep Context light:
        import('@/api/invoke').then(api => {
            api.getAppConfig().then(c => {
                setConfig({
                    max_concurrent_downloads: c.general.max_concurrent_downloads,
                    max_total_instances: c.general.max_total_instances
                });
            });
        });
    }, []);

    const handleChange = (key: keyof typeof config, value: number) => {
        const newConfig = { ...config, [key]: value };
        // Enforce logic: Total >= Concurrent
        if (key === 'max_concurrent_downloads' && value > newConfig.max_total_instances) {
            newConfig.max_total_instances = value;
        }
        if (key === 'max_total_instances' && value < newConfig.max_concurrent_downloads) {
            newConfig.max_concurrent_downloads = value;
        }

        setConfig(newConfig);

        // Save
        import('@/api/invoke').then(api => {
            api.saveGeneralConfig({
                download_path: defaultDownloadPath,
                filename_template: getTemplateString(),
                template_blocks_json: JSON.stringify(filenameTemplateBlocks),
                max_concurrent_downloads: newConfig.max_concurrent_downloads,
                max_total_instances: newConfig.max_total_instances
            });
        });
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
                        <span className="text-theme-cyan font-mono font-bold">{config.max_concurrent_downloads}</span>
                    </div>
                    <input
                        type="range"
                        min="1"
                        max="15"
                        value={config.max_concurrent_downloads}
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
                        <span className="text-theme-cyan font-mono font-bold">{config.max_total_instances}</span>
                    </div>
                    <input
                        type="range"
                        min="1"
                        max="20"
                        value={config.max_total_instances}
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