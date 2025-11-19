import React, { useState } from 'react';
import { Button } from './ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { Download, FolderOpen } from 'lucide-react';
import { selectDirectory } from '@/api/invoke';

interface DownloadFormProps {
  onDownload: (url: string, downloadPath?: string) => void;
}

export function DownloadForm({ onDownload }: DownloadFormProps) {
  const [url, setUrl] = useState('');
  const [downloadPath, setDownloadPath] = useState<string>('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim()) {
      onDownload(url, downloadPath || undefined);
      setUrl('');
      // We intentionally keep the download path persistent
    }
  };

  const handleSelectDirectory = async () => {
    try {
        const selected = await selectDirectory();
        if (selected) {
            setDownloadPath(selected);
        }
    } catch (err) {
        console.error("Failed to select directory", err);
    }
  };

  const isValidUrl = url.startsWith('http://') || url.startsWith('https://');

  return (
    <Card>
      <CardHeader>
        <CardTitle>Input / Output</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex gap-2">
            <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Enter video URL..."
                className="flex-grow bg-zinc-700 border border-zinc-600 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div className="flex gap-2 items-center">
             <input
                type="text"
                value={downloadPath}
                readOnly
                placeholder="Default System Downloads Folder"
                className="flex-grow bg-zinc-700/50 border border-zinc-600 rounded-md px-3 py-2 text-sm text-zinc-300 cursor-not-allowed focus:outline-none"
             />
             <Button type="button" variant="secondary" onClick={handleSelectDirectory} title="Select Output Folder">
                <FolderOpen className="h-4 w-4" />
             </Button>
          </div>

          <Button type="submit" disabled={!isValidUrl} className="w-full">
            <Download className="mr-2 h-4 w-4" />
            Start Download
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}