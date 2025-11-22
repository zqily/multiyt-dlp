import { useEffect, useState, useRef } from 'react';
import { appWindow } from '@tauri-apps/api/window';
import { DownloadForm } from './components/DownloadForm';
import { DownloadQueue } from './components/DownloadQueue';
import { useDownloadManager } from './hooks/useDownloadManager';
import { Layout } from './components/Layout';
import { SplashWindow } from './components/SplashWindow';
import { Activity, CheckCircle2, AlertCircle, List, Database, Hourglass, LayoutGrid } from 'lucide-react';

function App() {
  const [windowLabel, setWindowLabel] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const { downloads, startDownload, cancelDownload } = useDownloadManager();
  
  // Track previous count to handle auto-switching logic cleanly
  const prevCountRef = useRef(0);

  useEffect(() => {
    // appWindow.label is a string, not a Promise
    setWindowLabel(appWindow.label);
  }, []);

  // Auto-switch to Grid view if downloads exceed 20
  useEffect(() => {
    const count = downloads.size;
    const prevCount = prevCountRef.current;

    if (prevCount <= 20 && count > 20 && viewMode === 'list') {
        setViewMode('grid');
    }
    
    prevCountRef.current = count;
  }, [downloads.size, viewMode]);

  if (!windowLabel) return null;

  // --- SPLASH SCREEN ROUTE ---
  if (windowLabel === 'splashscreen') {
      return <SplashWindow />;
  }

  // --- MAIN APP ROUTE ---

  // Calculate Stats
  const total = downloads.size;
  const active = Array.from(downloads.values()).filter(d => d.status === 'downloading').length;
  const queued = Array.from(downloads.values()).filter(d => d.status === 'pending').length;
  const completed = Array.from(downloads.values()).filter(d => d.status === 'completed').length;
  const failed = Array.from(downloads.values()).filter(d => d.status === 'error').length;

  const toggleViewMode = () => {
      setViewMode(prev => prev === 'list' ? 'grid' : 'list');
  };

  return (
      <Layout
        SidebarContent={
          <DownloadForm onDownload={startDownload} />
        }
        MainContent={
          <>
            {/* Executive Summary Header */}
            <div className="flex items-center justify-between mb-6 bg-zinc-900/40 border border-zinc-800 rounded-lg p-4">
                <div className="flex items-center gap-4">
                    {/* View Toggle Icon Button */}
                    <button 
                        onClick={toggleViewMode}
                        className="p-2 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-theme-cyan hover:border-theme-cyan/50 hover:bg-zinc-800 transition-all cursor-pointer group"
                        title={viewMode === 'list' ? "Switch to Grid View" : "Switch to List View"}
                    >
                         {viewMode === 'list' ? (
                             <List className="h-6 w-6 group-hover:scale-110 transition-transform" /> 
                         ) : (
                             <LayoutGrid className="h-6 w-6 group-hover:scale-110 transition-transform" />
                         )}
                    </button>

                    <div>
                        <h2 className="text-lg font-semibold text-zinc-100 leading-tight">
                            Download Queue
                        </h2>
                        <div className="text-xs text-zinc-500 font-mono mt-1">
                            SESSION ID: {Math.floor(Date.now() / 1000).toString(16).toUpperCase()}
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-6">
                    {/* Stats */}
                    <div className="flex items-center gap-6 text-sm">
                        <div className="flex flex-col items-end">
                            <span className="text-[10px] text-zinc-600 uppercase tracking-wider font-bold">Total</span>
                            <div className="flex items-center gap-1.5 text-zinc-200 font-mono">
                                <Database className="h-3 w-3 text-zinc-500" />
                                {total}
                            </div>
                        </div>
                        
                        <div className="w-px h-8 bg-zinc-800" />

                        <div className="flex flex-col items-end">
                            <span className="text-[10px] text-zinc-600 uppercase tracking-wider font-bold">Queued</span>
                            <div className="flex items-center gap-1.5 text-zinc-200 font-mono">
                                <Hourglass className="h-3 w-3 text-amber-500/80" />
                                {queued}
                            </div>
                        </div>

                        <div className="w-px h-8 bg-zinc-800" />
                        
                        <div className="flex flex-col items-end">
                            <span className="text-[10px] text-zinc-600 uppercase tracking-wider font-bold">Active</span>
                            <div className="flex items-center gap-1.5 text-zinc-200 font-mono">
                                <Activity className="h-3 w-3 text-theme-cyan" />
                                {active}
                            </div>
                        </div>
                        
                        <div className="w-px h-8 bg-zinc-800" />
                        
                        <div className="flex flex-col items-end">
                            <span className="text-[10px] text-zinc-600 uppercase tracking-wider font-bold">Done</span>
                            <div className="flex items-center gap-1.5 text-zinc-200 font-mono">
                                <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                                {completed}
                            </div>
                        </div>
                        
                        <div className="w-px h-8 bg-zinc-800" />
                        
                        <div className="flex flex-col items-end">
                            <span className="text-[10px] text-zinc-600 uppercase tracking-wider font-bold">Failed</span>
                            <div className="flex items-center gap-1.5 text-zinc-200 font-mono">
                                <AlertCircle className="h-3 w-3 text-theme-red" />
                                {failed}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <DownloadQueue 
                downloads={downloads} 
                onCancel={cancelDownload} 
                viewMode={viewMode}
            />
          </>
        }
      />
  );
}

export default App;