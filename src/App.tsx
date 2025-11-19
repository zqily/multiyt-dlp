import { DownloadForm } from './components/DownloadForm';
import { DownloadQueue } from './components/DownloadQueue';
import { EnvironmentGate } from './components/EnvironmentGate';
import { useDownloadManager } from './hooks/useDownloadManager';

function App() {
  const { downloads, startDownload, cancelDownload } = useDownloadManager();

  return (
    <EnvironmentGate>
      <div className="container mx-auto p-4 max-w-4xl space-y-4">
        <DownloadForm onDownload={startDownload} />
        <DownloadQueue downloads={downloads} onCancel={cancelDownload} />
      </div>
    </EnvironmentGate>
  );
}

export default App;