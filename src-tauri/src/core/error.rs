use serde::Serialize;
use thiserror::Error;

#[derive(Debug, Error, Serialize)]
pub enum AppError {
    #[error("yt-dlp executable not found in system PATH.")]
    YtDlpNotFound,

    #[error("I/O Error: {0}")]
    IoError(String),

    #[error("yt-dlp process failed with exit code {exit_code}: {stderr}")]
    ProcessFailed { exit_code: i32, stderr: String },

    #[error("Validation failed: {0}")]
    ValidationFailed(String),

    #[error("A download for this URL is already in progress.")]
    JobAlreadyExists,

    #[error("Job with the specified ID was not found.")]
    JobNotFound,

    #[error("Failed to kill process: {0}")]
    ProcessKillFailed(String),
}

// Required to convert from std::io::Error
impl From<std::io::Error> for AppError {
    fn from(err: std::io::Error) -> Self {
        AppError::IoError(err.to_string())
    }
}
