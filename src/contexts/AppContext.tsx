import React, { useState, useEffect, useCallback } from 'react';
import { TemplateBlock, PreferenceConfig } from '@/types';
import { getAppConfig, saveGeneralConfig, savePreferenceConfig } from '@/api/invoke';

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
  getTemplateString: () => string;

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

  // 1. Load Config on Mount
  useEffect(() => {
    const load = async () => {
      try {
        const config = await getAppConfig();
        
        // Load General
        if (config.general.download_path) _setDownloadPath(config.general.download_path);
        if (config.general.template_blocks_json) {
            try {
                const parsed = JSON.parse(config.general.template_blocks_json);
                _setTemplateBlocks(parsed);
            } catch(e) { console.warn("Failed to parse blocks", e); }
        }

        // Load Preferences
        _setPreferences(config.preferences);
        
      } catch (error) {
        console.error("Failed to load config:", error);
      } finally {
        setIsConfigLoaded(true);
      }
    };
    load();
  }, []);

  // Helper to compile template
  const getTemplateString = useCallback((blocks?: TemplateBlock[]) => {
    const target = blocks || filenameTemplateBlocks;
    return target.map(block => {
        if (block.type === 'variable') {
            return `%(${block.value})s`;
        }
        return block.value;
    }).join('');
  }, [filenameTemplateBlocks]);


  // --- Saving Logic Wrappers ---

  const setDefaultDownloadPath = (path: string) => {
    _setDownloadPath(path);
    saveGeneralConfig({
        download_path: path,
        filename_template: getTemplateString(),
        template_blocks_json: JSON.stringify(filenameTemplateBlocks)
    });
  };

  const setFilenameTemplateBlocks = (blocks: TemplateBlock[]) => {
    _setTemplateBlocks(blocks);
    saveGeneralConfig({
        download_path: defaultDownloadPath,
        filename_template: getTemplateString(blocks),
        template_blocks_json: JSON.stringify(blocks)
    });
  };

  const updatePreferences = (updates: Partial<PreferenceConfig>) => {
      const newPrefs = { ...preferences, ...updates };
      _setPreferences(newPrefs);
      savePreferenceConfig(newPrefs);
  };

  const value = {
    isConfigLoaded,
    isJsRuntimeMissing,
    setIsJsRuntimeMissing,
    defaultDownloadPath,
    setDefaultDownloadPath,
    filenameTemplateBlocks,
    setFilenameTemplateBlocks,
    getTemplateString: () => getTemplateString(),
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