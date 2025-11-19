import { DownloadForm } from './components/DownloadForm';
import { DownloadQueue } from './components/DownloadQueue';
import { EnvironmentGate } from './components/EnvironmentGate';
import { useDownloadManager } from './hooks/useDownloadManager';
import { Layout } from './components/Layout';

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
            <h1 className="text-2xl font-semibold mb-4 text-zinc-200">Download Queue</h1>
            <DownloadQueue downloads={downloads} onCancel={cancelDownload} />
          </>
        }
      />
    </EnvironmentGate>
  );
}

export default App;
