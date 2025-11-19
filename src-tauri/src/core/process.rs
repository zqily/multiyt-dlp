use std::process::Stdio;
use std::sync::{Arc, Mutex};
use once_cell::sync::Lazy;
use regex::Regex;
use tauri::{AppHandle, Manager};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use uuid::Uuid;

use crate::core::manager::{JobManager, JobStatus};
use crate::models::{DownloadCompletePayload, DownloadErrorPayload, DownloadProgressPayload};

// Regex to capture download progress from yt-dlp stdout
// Example: [download]   6.5% of  707.82KiB at  262.24KiB/s ETA 00:02
static PROGRESS_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\[download\]\s+(?P<percentage>[\d\.]+)%\s+of\s+~?\s*(?P<size>[\d\.]+\w+)\s+at\s+(?P<speed>[\d\.]+\w+/s)\s+ETA\s+(?P<eta>\d{2}:\d{2})").unwrap()
});

pub async fn run_download_process(
    job_id: Uuid,
    url: String,
    app_handle: AppHandle,
    manager: Arc<Mutex<JobManager>>,
) {
    let downloads_dir = match app_handle.path_resolver().download_dir() {
        Some(path) => path,
        None => {
            let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
                job_id,
                error: "Could not determine downloads directory.".into(),
            });
            return;
        }
    };
    
    let output_template = downloads_dir.join("%(title)s.%(ext)s");
    let output_template_str = match output_template.to_str() {
        Some(s) => s.to_string(),
        None => {
             let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
                job_id,
                error: "Download path contains invalid characters.".into(),
            });
            return;
        }
    };

    let mut cmd = Command::new("yt-dlp");
    cmd.arg(&url)
        .arg("-o") // --output template
        .arg(&output_template_str)
        .arg("--progress")
        .arg("--no-playlist")
        .arg("--print") // Print final filename to stdout
        .arg("filename")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = match cmd.spawn() {
        Ok(child) => child,
        Err(e) => {
            let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
                job_id,
                error: format!("Failed to spawn yt-dlp: {}", e),
            });
            return;
        }
    };

    let pid = child.id().expect("Failed to get child process ID");
    if manager.lock().unwrap().update_job_pid(job_id, pid).is_err() {
        let _ = child.kill().await;
        return;
    }

    let stdout = child.stdout.take().expect("Failed to capture stdout");
    let stderr = child.stderr.take().expect("Failed to capture stderr");

    let mut stdout_reader = BufReader::new(stdout).lines();
    let mut stderr_reader = BufReader::new(stderr).lines();

    let stderr_output = Arc::new(Mutex::new(Vec::<String>::new()));
    let stderr_clone = stderr_output.clone();
    
    // Spawn a task to read stderr concurrently to prevent blocking
    tokio::spawn(async move {
        while let Ok(Some(line)) = stderr_reader.next_line().await {
            stderr_clone.lock().unwrap().push(line);
        }
    });

    let mut final_filename = None;

    // Read stdout line by line
    while let Ok(Some(line)) = stdout_reader.next_line().await {
        if let Some(caps) = PROGRESS_REGEX.captures(&line) {
            if let (Some(percentage_str), Some(speed), Some(eta)) =
                (caps.name("percentage"), caps.name("speed"), caps.name("eta"))
            {
                if let Ok(percentage) = percentage_str.as_str().parse::<f32>() {
                    let _ = app_handle.emit_all("download-progress", DownloadProgressPayload {
                        job_id,
                        percentage,
                        speed: speed.as_str().to_string(),
                        eta: eta.as_str().to_string(),
                    });
                }
            }
        } else {
            // yt-dlp prints the final filename to stdout on a new line when using `--print filename`.
            let trimmed_line = line.trim();
            if !trimmed_line.is_empty() {
                final_filename = Some(trimmed_line.to_string());
            }
        }
    }
    
    let status = child.wait().await.expect("Child process encountered an error");
    let mut manager_lock = manager.lock().unwrap();

    // Check if the job was cancelled while the process was running.
    if let Some(job_status) = manager_lock.get_job_status(job_id) {
        if job_status == JobStatus::Cancelled {
            manager_lock.remove_job(job_id);
            return; // Job was cancelled, so we stop here and clean up.
        }
    } else {
        return; // Job was already removed, nothing more to do.
    }

    if status.success() {
        if let Some(filename) = final_filename {
            manager_lock.update_job_status(job_id, JobStatus::Completed).ok();
            let _ = app_handle.emit_all("download-complete", DownloadCompletePayload {
                job_id,
                output_path: filename,
            });
        } else {
            manager_lock.update_job_status(job_id, JobStatus::Error).ok();
            let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
                job_id,
                error: "Download completed, but could not determine final filename.".to_string(),
            });
        }
    } else {
        let stderr_lines = stderr_output.lock().unwrap().join("\n");
        manager_lock.update_job_status(job_id, JobStatus::Error).ok();
        let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
            job_id,
            error: format!(
                "Download failed with exit code {}. Stderr: {}",
                status.code().unwrap_or(-1),
                stderr_lines
            ),
        });
    }

    manager_lock.remove_job(job_id);
}
