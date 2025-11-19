// --- Data Contracts ---

// This mirrors the `AppError` enum in the Rust backend.
// The keys match the enum variants. The value is the error message.
export type AppError = {
  YtDlpNotFound?: string;
  IoError?: string;
  ProcessFailed?: { exit_code: number; stderr: string };
  ValidationFailed?: string;
  JobAlreadyExists?: string;
};

// --- Event Payloads ---

export interface DownloadProgressPayload {
  jobId: string;
  percentage: number;
  speed: string;
  eta: string;
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
}
