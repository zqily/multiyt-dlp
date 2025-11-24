use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, PartialEq)]
pub enum JobStatus {
    Pending,
    Downloading,
    Completed,
    Cancelled,
    Error,
}

#[derive(Debug, Clone, Serialize, Deserialize)] // Added Deserialize
#[serde(rename_all = "snake_case")]
pub enum DownloadFormatPreset {
    // Video + Audio (Merged)
    Best,
    BestMp4,
    BestMkv,
    BestWebm,
    
    // Audio Only
    AudioBest,
    AudioMp3,
    AudioFlac,
    AudioM4a,
}

#[derive(Debug, Clone, Serialize)]
pub struct Job {
    pub url: String,
    pub pid: Option<u32>,
    pub status: JobStatus,
    pub progress: f32, // Changed: Added progress field
    pub output_path: Option<String>,
}

impl Job {
    pub fn new(url: String) -> Self {
        Self {
            url,
            pid: None,
            status: JobStatus::Pending,
            progress: 0.0,
            output_path: None,
        }
    }
}

// --- Queue Struct ---
// Holds all data needed to spawn the process later
#[derive(Debug, Clone, Serialize, Deserialize)] // Added Serialize, Deserialize
pub struct QueuedJob {
    pub id: Uuid,
    pub url: String,
    pub download_path: Option<String>,
    pub format_preset: DownloadFormatPreset,
    pub video_resolution: String,
    pub embed_metadata: bool,
    pub embed_thumbnail: bool,
    pub filename_template: String,
    pub restrict_filenames: bool,
}

// --- Playlist Expansion ---

#[derive(Debug, Serialize, Deserialize)]
pub struct PlaylistResult {
    pub entries: Vec<PlaylistEntry>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PlaylistEntry {
    pub id: Option<String>,
    pub url: String,
    pub title: String,
}

// --- Event Payloads ---

#[derive(Clone, serde::Serialize)]
pub struct DownloadProgressPayload {
    #[serde(rename = "jobId")]
    pub job_id: Uuid,
    pub percentage: f32,
    pub speed: String,
    pub eta: String,
    pub filename: Option<String>,
    pub phase: Option<String>,
}

#[derive(Clone, serde::Serialize)]
pub struct DownloadCompletePayload {
    #[serde(rename = "jobId")]
    pub job_id: Uuid,
    #[serde(rename = "outputPath")]
    pub output_path: String,
}

#[derive(Clone, serde::Serialize)]
pub struct DownloadErrorPayload {
    #[serde(rename = "jobId")]
    pub job_id: Uuid,
    pub error: String,
}