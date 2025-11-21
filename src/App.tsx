import { DownloadForm } from './components/DownloadForm';
import { DownloadQueue } from './components/DownloadQueue';
import { EnvironmentGate } from './components/EnvironmentGate';
import { useDownloadManager } from './hooks/useDownloadManager';
import { Layout } from './components/Layout';
import { List } from 'lucide-react';

function App() {
  const { downloads, startDownload, cancelDownload } = useDownloadManager();

  return (
    <EnvironmentGate>
      <Layout
        SidebarContent={
          <DownloadForm onDownload={startDownload} />
        }
        MainContent={
          <>
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                    <div className="p-2 rounded bg-zinc-900 border border-zinc-800">
                         <List className="text-zinc-400 h-5 w-5" />
                    </div>
                    <h2 className="text-xl font-semibold text-zinc-100">
                        Queue
                    </h2>
                </div>
                {downloads.size > 0 && (
                    <span className="text-xs font-medium text-zinc-500 bg-zinc-900 px-2.5 py-1 rounded-full border border-zinc-800">
                        {downloads.size} Active
                    </span>
                )}
            </div>
            <DownloadQueue downloads={downloads} onCancel={cancelDownload} />
          </>
        }
      />
    </EnvironmentGate>
  );
}

export default App;