import React, { useState } from 'react';
import { Button } from './ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { Download, FolderOpen, FileVideo, Music, Radio } from 'lucide-react';
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
}

const ModeButton: React.FC<ModeButtonProps> = ({ mode, currentMode, icon: Icon, label, onClick }) => {
    const isActive = mode === currentMode;
    return (
        <button
            type="button"
            onClick={() => onClick(mode)}
            title={label}
            className={twMerge(
                'flex items-center justify-center p-3 rounded-lg transition-all duration-300 border',
                isActive
                    ? 'bg-synth-cyan text-synth-navy border-synth-cyan shadow-neon-cyan'
                    : 'bg-synth-navy border-synth-cyan/20 text-synth-cyan/50 hover:text-synth-cyan hover:border-synth-cyan/50 hover:bg-synth-cyan/5'
            )}
        >
            <Icon className="h-5 w-5" />
        </button>
    );
};

export function DownloadForm({ onDownload }: DownloadFormProps) {
  const [url, setUrl] = useState('');
  const [downloadPath, setDownloadPath] = useState<string>('');
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
    if (newMode === 'video') {
        setSelectedFormat('best');
    } else {
        setSelectedFormat('audio_best');
    }
  };

  const isValidUrl = url.startsWith('http://') || url.startsWith('https://');
  const filteredPresets = formatPresets.filter(p => p.mode === mode);

  return (
    <Card className="border-synth-cyan/30 bg-synth-dark/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
            <Radio className="h-5 w-5 animate-pulse text-synth-pink" />
            Input Sequence
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          
          {/* URL Input */}
          <div className="relative group">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-synth-cyan to-synth-pink rounded-lg blur opacity-20 group-hover:opacity-50 transition duration-200"></div>
            <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Paste URL here..."
                className="relative w-full bg-synth-navy border border-synth-cyan/30 rounded-lg px-4 py-3 text-sm font-mono text-synth-cyan placeholder-synth-cyan/30 focus:outline-none focus:border-synth-cyan focus:shadow-neon-cyan transition-all"
            />
          </div>
          
          {/* Download Path */}
          <div className="flex gap-2 items-center">
             <div className="relative flex-grow">
                 <input
                    type="text"
                    value={downloadPath}
                    readOnly
                    placeholder="Default Downloads"
                    className="w-full bg-synth-dark border border-synth-cyan/20 rounded-lg px-3 py-2 text-xs font-mono text-synth-light/50 cursor-not-allowed focus:outline-none"
                 />
             </div>
             <Button 
                type="button" 
                variant="secondary" 
                onClick={handleSelectDirectory} 
                className="h-full aspect-square p-0 flex items-center justify-center"
             >
                <FolderOpen className="h-4 w-4" />
             </Button>
          </div>

          {/* Controls */}
          <div className="flex gap-3 items-stretch h-12">
            <div className="flex gap-2">
                <ModeButton mode="video" currentMode={mode} onClick={handleModeChange} icon={FileVideo} label="Video" />
                <ModeButton mode="audio" currentMode={mode} onClick={handleModeChange} icon={Music} label="Audio" />
            </div>

            <div className="relative flex-grow group">
                 <div className="absolute inset-y-0 right-0 flex items-center px-2 pointer-events-none text-synth-cyan z-10 bg-synth-navy/80 rounded-r-lg border-l border-synth-cyan/20">
                    <span className="text-[10px] font-bold">&#9660;</span>
                </div>
                <select
                    value={selectedFormat}
                    onChange={(e) => setSelectedFormat(e.target.value as DownloadFormatPreset)}
                    className="w-full h-full bg-synth-navy border border-synth-cyan/30 rounded-lg pl-3 pr-8 text-sm font-mono text-synth-cyan focus:outline-none focus:ring-1 focus:ring-synth-cyan appearance-none hover:bg-synth-cyan/5 cursor-pointer transition-colors"
                >
                    {filteredPresets.map(p => (
                        <option key={p.value} value={p.value} className="bg-synth-navy text-white">
                            {p.label}
                        </option>
                    ))}
                </select>
            </div>
          </div>

          <Button 
            type="submit" 
            disabled={!isValidUrl} 
            className={twMerge(
                "w-full h-12 text-base tracking-wider uppercase relative overflow-hidden group",
                !isValidUrl ? "opacity-50" : "hover:shadow-[0_0_20px_rgba(8,217,214,0.4)]"
            )}
            variant={isValidUrl ? 'default' : 'secondary'}
          >
            <span className="relative z-10 flex items-center">
                <Download className={twMerge("mr-2 h-5 w-5", isValidUrl && "animate-bounce")} />
                Initialize Download
            </span>
            {isValidUrl && <div className="absolute inset-0 bg-white/20 skew-x-12 -translate-x-full group-hover:animate-[shimmer_1s_infinite]"></div>}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}