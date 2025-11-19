use serde::Serialize;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, PartialEq)]
pub enum JobStatus {
    Pending,
    Downloading,
    Completed,
    Cancelled,
    Error,
}

#[derive(Debug, Clone, Serialize)]
pub struct Job {
    pub url: String,
    pub pid: Option<u32>,
    pub status: JobStatus,
    pub output_path: Option<String>,
}

impl Job {
    pub fn new(url: String) -> Self {
        Self {
            url,
            pid: None,
            status: JobStatus::Pending,
            output_path: None,
        }
    }
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