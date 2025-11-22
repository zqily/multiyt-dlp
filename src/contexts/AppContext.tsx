import React, { useState, useEffect, useCallback } from 'react';
import { TemplateBlock, PreferenceConfig } from '@/types';
import { getAppConfig, saveGeneralConfig, savePreferenceConfig, checkDependencies } from '@/api/invoke';

interface AppContextType {
  // State
  isConfigLoaded: boolean;
  isJsRuntimeMissing: boolean;
  setIsJsRuntimeMissing: (missing: boolean) => void;

  // General Config
  defaultDownloadPath: string | null;
  setDefaultDownloadPath: (path: string) => void;
  filenameTemplateBlocks: TemplateBlock[];
  setFilenameTemplateBlocks: (blocks: TemplateBlock[]) => void;
  getTemplateString: (blocks?: TemplateBlock[]) => string;
  
  // Concurrency
  maxConcurrentDownloads: number;
  maxTotalInstances: number;
  setConcurrency: (concurrent: number, total: number) => void;

  // Preferences
  preferences: PreferenceConfig;
  updatePreferences: (updates: Partial<PreferenceConfig>) => void;
}

const DEFAULT_TEMPLATE_BLOCKS: TemplateBlock[] = [
  { id: 'def-1', type: 'variable', value: 'title', label: 'Title' },
  { id: 'def-2', type: 'separator', value: '.', label: '.' },
  { id: 'def-3', type: 'variable', value: 'ext', label: 'Extension' },
];

const DEFAULT_PREFS: PreferenceConfig = {
    mode: 'video',
    format_preset: 'best',
    video_resolution: 'best',
    embed_metadata: false,
    embed_thumbnail: false
};

export const AppContext = React.createContext<AppContextType | undefined>(undefined);

export const AppProvider = ({ children }: { children: React.ReactNode }) => {
  const [isConfigLoaded, setIsConfigLoaded] = useState(false);
  const [isJsRuntimeMissing, setIsJsRuntimeMissing] = useState(false);

  // Config State
  const [defaultDownloadPath, _setDownloadPath] = useState<string | null>(null);
  const [filenameTemplateBlocks, _setTemplateBlocks] = useState<TemplateBlock[]>(DEFAULT_TEMPLATE_BLOCKS);
  const [preferences, _setPreferences] = useState<PreferenceConfig>(DEFAULT_PREFS);
  
  // Concurrency State
  const [maxConcurrentDownloads, _setMaxConcurrentDownloads] = useState(4);
  const [maxTotalInstances, _setMaxTotalInstances] = useState(10);

  useEffect(() => {
    const load = async () => {
      try {
        const config = await getAppConfig();
        
        // Load General
        if (config.general.download_path) _setDownloadPath(config.general.download_path);
        
        _setMaxConcurrentDownloads(config.general.max_concurrent_downloads);
        _setMaxTotalInstances(config.general.max_total_instances);

        if (config.general.template_blocks_json) {
            try {
                const parsed = JSON.parse(config.general.template_blocks_json);
                _setTemplateBlocks(parsed);
            } catch(e) { console.warn("Failed to parse blocks", e); }
        }

        // Load Preferences
        _setPreferences({ ...DEFAULT_PREFS, ...config.preferences });
        
        // Check Dependencies for Runtime Warning (Silently)
        const deps = await checkDependencies();
        if (!deps.js_runtime.available) {
            setIsJsRuntimeMissing(true);
        }

      } catch (error) {
        console.error("Failed to load config:", error);
      } finally {
        setIsConfigLoaded(true);
      }
    };
    load();
  }, []);

  const getTemplateString = useCallback((blocks?: TemplateBlock[]) => {
    const target = blocks || filenameTemplateBlocks;
    return target.map(block => {
        if (block.type === 'variable') {
            return `%(${block.value})s`;
        }
        return block.value;
    }).join('');
  }, [filenameTemplateBlocks]);

  const setDefaultDownloadPath = (path: string) => {
    _setDownloadPath(path);
    saveGeneralConfig({
        download_path: path,
        filename_template: getTemplateString(),
        template_blocks_json: JSON.stringify(filenameTemplateBlocks),
        max_concurrent_downloads: maxConcurrentDownloads,
        max_total_instances: maxTotalInstances
    }).catch(e => console.error("Failed to save download path:", e));
  };

  const setFilenameTemplateBlocks = (blocks: TemplateBlock[]) => {
    _setTemplateBlocks(blocks);
    saveGeneralConfig({
        download_path: defaultDownloadPath,
        filename_template: getTemplateString(blocks),
        template_blocks_json: JSON.stringify(blocks),
        max_concurrent_downloads: maxConcurrentDownloads,
        max_total_instances: maxTotalInstances
    }).catch(e => console.error("Failed to save template:", e));
  };

  const setConcurrency = (concurrent: number, total: number) => {
    _setMaxConcurrentDownloads(concurrent);
    _setMaxTotalInstances(total);
    saveGeneralConfig({
        download_path: defaultDownloadPath,
        filename_template: getTemplateString(),
        template_blocks_json: JSON.stringify(filenameTemplateBlocks),
        max_concurrent_downloads: concurrent,
        max_total_instances: total
    }).catch(e => console.error("Failed to save concurrency:", e));
  };

  const updatePreferences = (updates: Partial<PreferenceConfig>) => {
      const newPrefs = { ...preferences, ...updates };
      _setPreferences(newPrefs);
      savePreferenceConfig(newPrefs).catch(e => console.error("Failed to save preferences:", e));
  };

  const value = {
    isConfigLoaded,
    isJsRuntimeMissing,
    setIsJsRuntimeMissing,
    defaultDownloadPath,
    setDefaultDownloadPath,
    filenameTemplateBlocks,
    setFilenameTemplateBlocks,
    getTemplateString,
    maxConcurrentDownloads,
    maxTotalInstances,
    setConcurrency,
    preferences,
    updatePreferences
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export const useAppContext = () => {
  const context = React.useContext(AppContext);
  if (context === undefined) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};