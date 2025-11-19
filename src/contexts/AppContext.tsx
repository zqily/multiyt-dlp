import React from 'react';

// This is a placeholder for global application settings,
// as outlined in the master plan. It can be expanded to manage
// user configurations like the default download path.

interface AppContextType {
  // Example setting
  defaultDownloadPath: string | null;
}

export const AppContext = React.createContext<AppContextType | undefined>(undefined);

export const AppProvider = ({ children }: { children: React.ReactNode }) => {
  const value = {
    defaultDownloadPath: null, // To be loaded from config
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
