import React, { useState } from 'react';
import { Button } from './ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { Download } from 'lucide-react';

interface DownloadFormProps {
  onDownload: (url: string) => void;
}

export function DownloadForm({ onDownload }: DownloadFormProps) {
  const [url, setUrl] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim()) {
      onDownload(url);
      setUrl('');
    }
  };

  const isValidUrl = url.startsWith('http://') || url.startsWith('https://');

  return (
    <Card>
      <CardHeader>
        <CardTitle>Download Video</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Enter video URL..."
            className="flex-grow bg-zinc-700 border border-zinc-600 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <Button type="submit" disabled={!isValidUrl}>
            <Download className="mr-2 h-4 w-4" />
            Download
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
