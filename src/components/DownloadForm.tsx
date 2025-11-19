import React, { useState } from 'react';
import { Button } from './ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { Download, FolderOpen, FileVideo, Music } from 'lucide-react';
import { selectDirectory } from '@/api/invoke';
import { DownloadFormatPreset } from '@/types';
import { twMerge } from 'tailwind-merge';

interface DownloadFormProps {
  onDownload: (url: string, downloadPath?: string, formatPreset?: DownloadFormatPreset) => void;
}

type DownloadMode = 'video' | 'audio';

const formatPresets: {
  label: string;
  value: DownloadFormatPreset;
  mode: DownloadMode;
}[] = [
  // Video Group (Video + Audio)
  { label: 'Best Quality (Merged/Default)', value: 'best', mode: 'video' },
  { label: 'Best MP4 (Merged)', value: 'best_mp4', mode: 'video' },
  { label: 'Best MKV (Merged)', value: 'best_mkv', mode: 'video' },
  { label: 'Best WebM (Merged)', value: 'best_webm', mode: 'video' },
  
  // Audio Only Group
  { label: 'Best Audio Only (Default)', value: 'audio_best', mode: 'audio' },
  { label: 'MP3 Audio Only', value: 'audio_mp3', mode: 'audio' },
  { label: 'FLAC Audio Only (Lossless)', value: 'audio_flac', mode: 'audio' },
  { label: 'M4A Audio Only', value: 'audio_m4a', mode: 'audio' },
];

interface ModeButtonProps {
    mode: DownloadMode;
    currentMode: DownloadMode;
    icon: React.ElementType;
    label: string;
    onClick: (mode: DownloadMode) => void;
}

const ModeButton: React.FC<ModeButtonProps> = ({ mode, currentMode, icon: Icon, label, onClick }) => {
    const isActive = mode === currentMode;
    return (
        <button
            type="button"
            onClick={() => onClick(mode)}
            title={label}
            className={twMerge(
                'flex items-center justify-center p-2 rounded-md transition-colors border text-sm',
                isActive
                    ? 'bg-blue-600 border-blue-600 text-white'
                    : 'bg-zinc-700 border-zinc-600 text-zinc-300 hover:bg-zinc-600'
            )}
        >
            <Icon className="h-5 w-5" />
        </button>
    );
};


export function DownloadForm({ onDownload }: DownloadFormProps) {
  const [url, setUrl] = useState('');
  const [downloadPath, setDownloadPath] = useState<string>('');
  
  // New state for mode and selected format
  const [mode, setMode] = useState<DownloadMode>('video');
  const [selectedFormat, setSelectedFormat] = useState<DownloadFormatPreset>('best');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim()) {
      onDownload(url, downloadPath || undefined, selectedFormat);
      setUrl('');
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
  
  const handleModeChange = (newMode: DownloadMode) => {
    setMode(newMode);
    
    // Automatically select the default preset for the new mode
    if (newMode === 'video') {
        setSelectedFormat('best');
    } else {
        setSelectedFormat('audio_best');
    }
  };

  const isValidUrl = url.startsWith('http://') || url.startsWith('https://');
  const filteredPresets = formatPresets.filter(p => p.mode === mode);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Input / Output</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* URL Input */}
          <div className="flex gap-2">
            <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Enter video URL..."
                className="flex-grow bg-zinc-700 border border-zinc-600 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          {/* Download Path Input and Selector */}
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

          {/* Format Selection (Mode + Dropdown) */}
          <div className="flex gap-2 items-center">
            {/* Mode Toggles */}
            <ModeButton 
                mode="video" 
                currentMode={mode} 
                onClick={handleModeChange} 
                icon={FileVideo}
                label="Download Video + Audio"
            />
            <ModeButton 
                mode="audio" 
                currentMode={mode} 
                onClick={handleModeChange} 
                icon={Music}
                label="Download Audio Only"
            />

            {/* Dynamic Dropdown */}
            <div className="relative flex-grow transition-all duration-300">
                <select
                    value={selectedFormat}
                    onChange={(e) => setSelectedFormat(e.target.value as DownloadFormatPreset)}
                    className="w-full bg-zinc-700 border border-zinc-600 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-white appearance-none pr-8"
                >
                    {filteredPresets.map(p => (
                        // We must ensure the selected format is one of the displayed options
                        // If the user clicks on 'Audio', the selectedFormat will automatically become 'audio_best'
                        <option key={p.value} value={p.value}>
                            {p.label}
                        </option>
                    ))}
                </select>
                {/* Custom chevron to fix appearance-none */}
                <span className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-zinc-400">
                    &#9662;
                </span>
            </div>
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