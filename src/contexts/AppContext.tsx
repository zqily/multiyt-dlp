import React, { useState, useEffect, useCallback } from 'react';
import { TemplateBlock, PreferenceConfig } from '@/types';
import { getAppConfig, saveGeneralConfig, savePreferenceConfig, checkDependencies, getLatestAppVersion } from '@/api/invoke';
import { getVersion } from '@tauri-apps/api/app';

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

  // Logs
  logLevel: string;
  setLogLevel: (level: string) => void;

  // Update
  checkForUpdates: boolean;
  setCheckForUpdates: (enabled: boolean) => void;
  isUpdateAvailable: boolean;
  latestVersion: string | null;
  currentVersion: string | null;
  checkAppUpdate: () => Promise<void>;

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
    video_preset: 'best',        
    audio_preset: 'audio_best',  
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
  
  // Log State
  const [logLevel, _setLogLevel] = useState('info');

  // Update State
  const [checkForUpdates, _setCheckForUpdates] = useState(true);
  const [isUpdateAvailable, setIsUpdateAvailable] = useState(false);
  const [latestVersion, setLatestVersion] = useState<string | null>(null);
  const [currentVersion, setCurrentVersion] = useState<string | null>(null);

  // Version Comparison Logic
  const checkAppUpdate = async () => {
    try {
        const current = await getVersion();
        setCurrentVersion(current);
        const latestTag = await getLatestAppVersion();
        
        // Strip 'v' if present
        const cleanLatest = latestTag.replace(/^v/, '');
        const cleanCurrent = current.replace(/^v/, '');

        setLatestVersion(cleanLatest);

        // Simple comparison: if strings differ and remote seems larger logic? 
        // Let's do a simple segment compare
        const v1parts = cleanCurrent.split('.').map(Number);
        const v2parts = cleanLatest.split('.').map(Number);
        
        let isNewer = false;
        for (let i = 0; i < Math.max(v1parts.length, v2parts.length); i++) {
            const v1 = v1parts[i] || 0;
            const v2 = v2parts[i] || 0;
            if (v2 > v1) { isNewer = true; break; }
            if (v1 > v2) { break; }
        }

        setIsUpdateAvailable(isNewer);
    } catch (e) {
        console.warn("Update check failed:", e);
    }
  };

  useEffect(() => {
    const load = async () => {
      try {
        const config = await getAppConfig();
        
        if (config.general.download_path) _setDownloadPath(config.general.download_path);
        
        _setMaxConcurrentDownloads(config.general.max_concurrent_downloads);
        _setMaxTotalInstances(config.general.max_total_instances);
        _setLogLevel(config.general.log_level || 'info');
        _setCheckForUpdates(config.general.check_for_updates);

        if (config.general.template_blocks_json) {
            try {
                const parsed = JSON.parse(config.general.template_blocks_json);
                _setTemplateBlocks(parsed);
            } catch(e) { console.warn("Failed to parse blocks", e); }
        }

        _setPreferences({ ...DEFAULT_PREFS, ...config.preferences });
        
        const deps = await checkDependencies();
        if (!deps.js_runtime.available) {
            setIsJsRuntimeMissing(true);
        }

        // Trigger update check if enabled
        if (config.general.check_for_updates) {
            // Run without awaiting to not block init
            checkAppUpdate();
        } else {
            // Still get current version for UI
            getVersion().then(v => setCurrentVersion(v));
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

  const saveGeneral = (
      path: string | null, 
      blocks: TemplateBlock[], 
      concurrent: number, 
      total: number, 
      log: string,
      updates: boolean
    ) => {
      saveGeneralConfig({
        download_path: path,
        filename_template: getTemplateString(blocks),
        template_blocks_json: JSON.stringify(blocks),
        max_concurrent_downloads: concurrent,
        max_total_instances: total,
        log_level: log,
        check_for_updates: updates
      }).catch(e => console.error("Failed to save general config:", e));
  };

  const setDefaultDownloadPath = (path: string) => {
    _setDownloadPath(path);
    saveGeneral(path, filenameTemplateBlocks, maxConcurrentDownloads, maxTotalInstances, logLevel, checkForUpdates);
  };

  const setFilenameTemplateBlocks = (blocks: TemplateBlock[]) => {
    _setTemplateBlocks(blocks);
    saveGeneral(defaultDownloadPath, blocks, maxConcurrentDownloads, maxTotalInstances, logLevel, checkForUpdates);
  };

  const setConcurrency = (concurrent: number, total: number) => {
    _setMaxConcurrentDownloads(concurrent);
    _setMaxTotalInstances(total);
    saveGeneral(defaultDownloadPath, filenameTemplateBlocks, concurrent, total, logLevel, checkForUpdates);
  };

  const setLogLevel = (level: string) => {
      _setLogLevel(level);
      saveGeneral(defaultDownloadPath, filenameTemplateBlocks, maxConcurrentDownloads, maxTotalInstances, level, checkForUpdates);
  };

  const setCheckForUpdates = (enabled: boolean) => {
      _setCheckForUpdates(enabled);
      saveGeneral(defaultDownloadPath, filenameTemplateBlocks, maxConcurrentDownloads, maxTotalInstances, logLevel, enabled);
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
    logLevel,
    setLogLevel,
    checkForUpdates,
    setCheckForUpdates,
    isUpdateAvailable,
    latestVersion,
    currentVersion,
    checkAppUpdate,
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