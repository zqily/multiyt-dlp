import React, { useState } from 'react';
import { TemplateBlock } from '@/types';

interface AppContextType {
  defaultDownloadPath: string | null;
  setDefaultDownloadPath: (path: string) => void;
  
  // Filename Template Settings
  filenameTemplateBlocks: TemplateBlock[];
  setFilenameTemplateBlocks: (blocks: TemplateBlock[]) => void;
  getTemplateString: () => string;
}

const DEFAULT_TEMPLATE_BLOCKS: TemplateBlock[] = [
  { id: 'def-1', type: 'variable', value: 'title', label: 'Title' },
  { id: 'def-2', type: 'separator', value: '.', label: '.' },
  { id: 'def-3', type: 'variable', value: 'ext', label: 'Extension' },
];

export const AppContext = React.createContext<AppContextType | undefined>(undefined);

export const AppProvider = ({ children }: { children: React.ReactNode }) => {
  const [defaultDownloadPath, setDefaultDownloadPath] = useState<string | null>(null);
  const [filenameTemplateBlocks, setFilenameTemplateBlocks] = useState<TemplateBlock[]>(DEFAULT_TEMPLATE_BLOCKS);

  // Helper to convert blocks to yt-dlp string
  // e.g. [Title] [.] [Ext] -> "%(title)s.%(ext)s"
  const getTemplateString = () => {
    return filenameTemplateBlocks.map(block => {
        if (block.type === 'variable') {
            return `%(${block.value})s`;
        }
        return block.value;
    }).join('');
  };

  const value = {
    defaultDownloadPath,
    setDefaultDownloadPath,
    filenameTemplateBlocks,
    setFilenameTemplateBlocks,
    getTemplateString
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