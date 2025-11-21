// src/components/DownloadForm.tsx

import React, { useState } from 'react';
import { Button } from './ui/Button';
import { Card, CardContent } from './ui/Card';
import { Download, FolderOpen, Link2, MonitorPlay, Headphones, FileText, Image as ImageIcon } from 'lucide-react';
import { selectDirectory } from '@/api/invoke';
import { DownloadFormatPreset } from '@/types';
import { useAppContext } from '@/contexts/AppContext';
import { twMerge } from 'tailwind-merge';

interface DownloadFormProps {
  onDownload: (
      url: string, 
      downloadPath: string | undefined, 
      formatPreset: DownloadFormatPreset, 
      embedMeta: boolean,
      embedThumbnail: boolean,
      filenameTemplate: string
    ) => void;
}

type DownloadMode = 'video' | 'audio';

const formatPresets: {
  label: string;
  value: DownloadFormatPreset;
  mode: DownloadMode;
}[] = [
  { label: 'Best Quality', value: 'best', mode: 'video' },
  { label: 'Best MP4', value: 'best_mp4', mode: 'video' },
  { label: 'Best MKV', value: 'best_mkv', mode: 'video' },
  { label: 'Best WebM', value: 'best_webm', mode: 'video' },
  { label: 'Best Audio', value: 'audio_best', mode: 'audio' },
  { label: 'MP3 Audio', value: 'audio_mp3', mode: 'audio' },
  { label: 'FLAC (Lossless)', value: 'audio_flac', mode: 'audio' },
  { label: 'M4A Audio', value: 'audio_m4a', mode: 'audio' },
];

interface ModeButtonProps {
    mode: DownloadMode;
    currentMode: DownloadMode;
    icon: React.ElementType;
    label: string;
    onClick: (mode: DownloadMode) => void;
    accentColor: string;
}

const ModeButton: React.FC<ModeButtonProps> = ({ mode, currentMode, icon: Icon, label, onClick }) => {
    const isActive = mode === currentMode;
    const activeClass = mode === 'video' 
        ? 'bg-theme-cyan/10 text-theme-cyan border-theme-cyan/50 shadow-glow-cyan' 
        : 'bg-theme-red/10 text-theme-red border-theme-red/50 shadow-glow-red';

    return (
        <button
            type="button"
            onClick={() => onClick(mode)}
            className={twMerge(
                'flex flex-1 items-center justify-center gap-2 py-2.5 text-xs uppercase tracking-wider font-bold rounded-md transition-all border',
                isActive
                    ? activeClass
                    : 'bg-zinc-900/50 border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700'
            )}
        >
            <Icon className="h-4 w-4" />
            {label}
        </button>
    );
};

export function DownloadForm({ onDownload }: DownloadFormProps) {
  const { getTemplateString } = useAppContext();
  
  const [url, setUrl] = useState('');
  const [downloadPath, setDownloadPath] = useState<string>('');
  const [mode, setMode] = useState<DownloadMode>('video');
  const [selectedFormat, setSelectedFormat] = useState<DownloadFormatPreset>('best');
  
  const [embedMetadata, setEmbedMetadata] = useState<boolean>(false);
  const [embedThumbnail, setEmbedThumbnail] = useState<boolean>(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim()) {
      const template = getTemplateString();
      onDownload(url, downloadPath || undefined, selectedFormat, embedMetadata, embedThumbnail, template);
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
    if (newMode === 'video') {
        setSelectedFormat('best');
    } else {
        setSelectedFormat('audio_best');
    }
  };

  const isValidUrl = url.startsWith('http://') || url.startsWith('https://');
  const filteredPresets = formatPresets.filter(p => p.mode === mode);

  return (
    <Card className="bg-transparent border-0 shadow-none p-0">
      <CardContent className="p-0">
        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          
          {/* URL Input */}
          <div className="space-y-2">
            <label className="text-[11px] uppercase tracking-wider font-bold text-zinc-500 ml-1">Target URL</label>
            <div className="relative group">
                <div className="absolute inset-0 bg-theme-cyan/20 blur-md rounded-lg opacity-0 group-focus-within:opacity-100 transition-opacity duration-500"></div>
                <Link2 className="absolute left-3 top-3 h-4 w-4 text-zinc-500 group-focus-within:text-theme-cyan transition-colors" />
                <input
                    type="text"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://youtube.com/watch?v=..."
                    className="relative w-full bg-surfaceHighlight border border-border rounded-md pl-10 pr-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-700 focus:outline-none focus:ring-1 focus:ring-theme-cyan focus:border-theme-cyan transition-all"
                />
            </div>
          </div>
          
          <div className="grid grid-cols-1 gap-5">
              
              {/* Mode & Format */}
              <div className="space-y-2">
                 <label className="text-[11px] uppercase tracking-wider font-bold text-zinc-500 ml-1">Configuration</label>
                 <div className="flex gap-2 mb-3">
                    <ModeButton 
                        mode="video" 
                        currentMode={mode} 
                        onClick={handleModeChange} 
                        icon={MonitorPlay} 
                        label="Video" 
                        accentColor="cyan"
                    />
                    <ModeButton 
                        mode="audio" 
                        currentMode={mode} 
                        onClick={handleModeChange} 
                        icon={Headphones} 
                        label="Audio" 
                        accentColor="red"
                    />
                 </div>
                 
                 <div className="space-y-3">
                     <select
                        value={selectedFormat}
                        onChange={(e) => setSelectedFormat(e.target.value as DownloadFormatPreset)}
                        className="w-full bg-surfaceHighlight border border-border rounded-md px-3 py-2.5 text-sm text-zinc-300 focus:outline-none focus:ring-1 focus:ring-theme-cyan/50 focus:border-theme-cyan/50"
                     >
                        {filteredPresets.map(p => (
                            <option key={p.value} value={p.value}>
                                {p.label}
                            </option>
                        ))}
                     </select>

                     {/* Post Processing Options */}
                     <div className="flex gap-2">
                         <button
                            type="button"
                            onClick={() => setEmbedMetadata(!embedMetadata)}
                            className={twMerge(
                                "flex-1 flex items-center justify-center gap-2 px-2 py-2.5 rounded-md border transition-all text-xs font-medium",
                                embedMetadata 
                                    ? "bg-zinc-800 border-theme-cyan/50 text-theme-cyan"
                                    : "bg-surfaceHighlight border-border text-zinc-500 hover:text-zinc-300"
                            )}
                            title="Embed Metadata (Tags)"
                         >
                            <FileText className="h-3.5 w-3.5" />
                            Metadata
                         </button>

                         <button
                            type="button"
                            onClick={() => setEmbedThumbnail(!embedThumbnail)}
                            className={twMerge(
                                "flex-1 flex items-center justify-center gap-2 px-2 py-2.5 rounded-md border transition-all text-xs font-medium",
                                embedThumbnail 
                                    ? "bg-zinc-800 border-theme-cyan/50 text-theme-cyan"
                                    : "bg-surfaceHighlight border-border text-zinc-500 hover:text-zinc-300"
                            )}
                            title="Embed Thumbnail (Cover Art)"
                         >
                            <ImageIcon className="h-3.5 w-3.5" />
                            Thumbnail
                         </button>
                     </div>
                 </div>
              </div>

              {/* Directory */}
              <div className="space-y-2">
                  <label className="text-[11px] uppercase tracking-wider font-bold text-zinc-500 ml-1">Save Location</label>
                  <div className="flex gap-2">
                     <input
                        type="text"
                        value={downloadPath}
                        readOnly
                        placeholder="Downloads Folder"
                        className="flex-grow bg-surfaceHighlight border border-border rounded-md px-3 py-2.5 text-sm text-zinc-500 cursor-not-allowed"
                     />
                     <Button 
                        type="button" 
                        variant="secondary" 
                        onClick={handleSelectDirectory} 
                        className="px-4 border-zinc-700 hover:border-zinc-500"
                        title="Choose Folder"
                     >
                        <FolderOpen className="h-4 w-4" />
                     </Button>
                  </div>
              </div>
          </div>

          <div className="pt-2">
            <Button 
                type="submit" 
                variant="default"
                disabled={!isValidUrl} 
                className="w-full h-12 text-base uppercase tracking-wide font-black shadow-lg shadow-theme-cyan/20"
            >
                <Download className="mr-2 h-5 w-5" />
                Initialize Download
            </Button>
          </div>

        </form>
      </CardContent>
    </Card>
  );
}