import { DownloadForm } from './components/DownloadForm';
import { DownloadQueue } from './components/DownloadQueue';
import { EnvironmentGate } from './components/EnvironmentGate';
import { useDownloadManager } from './hooks/useDownloadManager';
import { Layout } from './components/Layout';
import { Activity } from 'lucide-react';

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
            <div className="flex items-center gap-3 mb-6 border-b border-synth-cyan/20 pb-4">
                <Activity className="text-synth-cyan h-6 w-6 animate-pulse" />
                <h1 className="text-2xl font-mono font-bold text-synth-light tracking-widest uppercase">
                    Active Queue
                </h1>
                <div className="flex-grow" />
                <span className="text-xs font-mono text-synth-cyan/50 bg-synth-navy px-2 py-1 rounded border border-synth-cyan/20">
                    PID: {downloads.size}
                </span>
            </div>
            <DownloadQueue downloads={downloads} onCancel={cancelDownload} />
          </>
        }
      />
    </EnvironmentGate>
  );
}

export default App;