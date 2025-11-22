// --- Config Types ---

export interface GeneralConfig {
  download_path: string | null;
  filename_template: string;
  template_blocks_json: string | null;
  // NEW
  max_concurrent_downloads: number;
  max_total_instances: number;
}

export interface PreferenceConfig {
  mode: string;
  format_preset: string;
  video_resolution: string; 
  embed_metadata: boolean;
  embed_thumbnail: boolean;
}

export interface WindowConfig {
  width: number;
  height: number;
  x: number;
  y: number;
}

export interface AppConfig {
  general: GeneralConfig;
  preferences: PreferenceConfig;
  window: WindowConfig;
}

// ... (Keep existing AppDependencies, AppError, etc.) ...

export interface AppDependencies {
  yt_dlp: boolean;
  ffmpeg: boolean;
  js_runtime: boolean;
}

export type AppError = {
  IoError?: string;
  ProcessFailed?: { exit_code: number; stderr: string };
  ValidationFailed?: string;
  JobAlreadyExists?: string;
};

export type DownloadFormatPreset = 
  | 'best' 
  | 'best_mp4' 
  | 'best_mkv'
  | 'best_webm'
  | 'audio_best' 
  | 'audio_mp3'
  | 'audio_flac'
  | 'audio_m4a';

export interface DownloadProgressPayload {
  jobId: string;
  percentage: number;
  speed: string;
  eta: string;
  filename?: string; 
  phase?: string;    
}

export interface DownloadCompletePayload {
  jobId: string;
  outputPath: string;
}

export interface DownloadErrorPayload {
  jobId: string;
  error: string;
}

export type DownloadStatus = 'pending' | 'downloading' | 'completed' | 'error' | 'cancelled';

export interface Download {
  jobId: string;
  url: string;
  status: DownloadStatus;
  progress: number;
  speed?: string;
  eta?: string;
  outputPath?: string;
  error?: string;
  filename?: string;
  phase?: string;
  preset?: DownloadFormatPreset; 
  embedMetadata?: boolean; 
  embedThumbnail?: boolean;
}

export type TemplateBlockType = 'variable' | 'separator' | 'text';

export interface TemplateBlock {
  id: string;
  type: TemplateBlockType;
  value: string; // The yt-dlp string (e.g., "title" or ".")
  label: string; // Display name (e.g., "Title" or ".")
}

// NEW
export interface PlaylistEntry {
    id?: string;
    url: string;
    title: string;
}

export interface PlaylistResult {
    entries: PlaylistEntry[];
}