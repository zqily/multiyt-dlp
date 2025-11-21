// --- Data Contracts ---

export interface AppDependencies {
  yt_dlp: boolean;
  ffmpeg: boolean;
  js_runtime: boolean;
}

// This mirrors the `AppError` enum in the Rust backend.
export type AppError = {
  IoError?: string;
  ProcessFailed?: { exit_code: number; stderr: string };
  ValidationFailed?: string;
  JobAlreadyExists?: string;
};

// This mirrors the `DownloadFormatPreset` enum in the Rust backend.
export type DownloadFormatPreset = 
  | 'best' 
  | 'best_mp4' 
  | 'best_mkv'
  | 'best_webm'
  | 'audio_best' 
  | 'audio_mp3'
  | 'audio_flac'
  | 'audio_m4a';


// --- Event Payloads ---

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

// --- Frontend State ---

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

// --- Settings Types ---

export type TemplateBlockType = 'variable' | 'separator' | 'text';

export interface TemplateBlock {
  id: string;
  type: TemplateBlockType;
  value: string; // The yt-dlp string (e.g., "title" or ".")
  label: string; // Display name (e.g., "Title" or ".")
}