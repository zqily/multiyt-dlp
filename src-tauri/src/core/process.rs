use std::process::Stdio;
use std::sync::{Arc, Mutex};
use once_cell::sync::Lazy;
use regex::Regex;
use tauri::{AppHandle, Manager};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::sync::mpsc;
use uuid::Uuid;
use std::path::PathBuf;

use crate::core::manager::{JobManager, JobStatus};
use crate::models::{DownloadCompletePayload, DownloadErrorPayload, DownloadProgressPayload, DownloadFormatPreset};

// --- Regex Definitions ---

// Captures: [download] 12.3% of ~1.23MiB at 5.55MiB/s ETA 00:18
static PROGRESS_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\[download\]\s+(?P<percentage>[\d\.]+)%\s+of\s+~?\s*(?P<size>[^\s]+)(?:\s+at\s+(?P<speed>[^\s]+))?(?:\s+ETA\s+(?P<eta>[^\s]+))?").unwrap()
});

// Captures: [download] Destination: path/to/Title. [id].f123.mp4
static DESTINATION_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\[download\]\s+Destination:\s+(?P<filename>.+)$").unwrap()
});

// Captures: [download] path/to/file has already been downloaded
static ALREADY_DOWNLOADED_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\[download\]\s+(?:Destination:\s+)?(?P<filename>.+?)\s+has already been downloaded").unwrap()
});

// Captures: [Merger] Merging formats into "path/to/file.mkv"
static MERGER_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r#"\[Merger\]\s+Merging formats into\s+"?(?P<filename>.+?)"?$"#).unwrap()
});

// Helper regex to clean the Title.
// Matches the default yt-dlp suffix: " [VideoID].ext" or " [VideoID].fFormat.ext"
static TITLE_CLEANER_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\s\[[a-zA-Z0-9_-]{11}\]\.(?:f[0-9]+\.)?[a-z0-9]+$").unwrap()
});

pub async fn run_download_process(
    job_id: Uuid,
    url: String,
    custom_path: Option<String>,
    format_preset: DownloadFormatPreset, // New argument
    app_handle: AppHandle,
    manager: Arc<Mutex<JobManager>>,
) {
    let downloads_dir = if let Some(path) = custom_path {
        PathBuf::from(path)
    } else {
        match tauri::api::path::download_dir() {
            Some(path) => path,
            None => {
                let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
                    job_id,
                    error: "Could not determine downloads directory.".into(),
                });
                return;
            }
        }
    };
    
    // We explicitly use the default template so we can rely on the standard naming for parsing
    let output_template = downloads_dir.join("%(title)s. [%(id)s].%(ext)s");
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
        .arg("-o")
        .arg(&output_template_str)
        .arg("--no-playlist")
        .arg("--no-simulate") 
        .arg("--newline")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    // --- Format Preset Logic ---
    match format_preset {
        DownloadFormatPreset::Best => {
            // Default behavior: -f bestvideo*+bestaudio/best
            // No explicit args needed other than default yt-dlp flags
        }
        DownloadFormatPreset::BestMp4 => {
            cmd.args(["-f", "bestvideo+bestaudio", "--merge-output-format", "mp4"]);
        }
        DownloadFormatPreset::BestMkv => {
            cmd.args(["-f", "bestvideo+bestaudio", "--merge-output-format", "mkv"]);
        }
        DownloadFormatPreset::BestWebm => {
            cmd.args(["-f", "bestvideo+bestaudio", "--merge-output-format", "webm"]);
        }
        DownloadFormatPreset::AudioBest => {
            cmd.arg("-x").args(["-f", "bestaudio/best"]);
        }
        DownloadFormatPreset::AudioMp3 => {
            cmd.arg("-x").args(["--audio-format", "mp3", "--audio-quality", "0"]);
        }
        DownloadFormatPreset::AudioFlac => {
            cmd.arg("-x").args(["--audio-format", "flac", "--audio-quality", "0"]);
        }
        DownloadFormatPreset::AudioM4a => {
            cmd.arg("-x").args(["--audio-format", "m4a", "--audio-quality", "0"]);
        }
    }
    // --- End Format Preset Logic ---

    // --- Process Spawning ---

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
    
    // Update Manager with PID
    let should_continue = {
        let mut manager_lock = manager.lock().unwrap();
        if manager_lock.update_job_pid(job_id, pid).is_ok() {
            manager_lock.update_job_status(job_id, JobStatus::Downloading).ok();
            true
        } else {
            false
        }
    };

    if !should_continue {
        let _ = child.kill().await;
        return;
    }

    // --- Output Handling ---

    let stdout = child.stdout.take().expect("Failed to capture stdout");
    let stderr = child.stderr.take().expect("Failed to capture stderr");

    // We use an MPSC channel to aggregate both stdout and stderr lines into a single processing loop.
    // This avoids complexity regarding where yt-dlp decides to print progress.
    let (tx, mut rx) = mpsc::channel::<String>(100);

    // Spawn Stdout Reader
    let tx_out = tx.clone();
    tokio::spawn(async move {
        let mut reader = BufReader::new(stdout).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            if tx_out.send(line).await.is_err() { break; }
        }
    });

    // Spawn Stderr Reader
    let tx_err = tx.clone();
    tokio::spawn(async move {
        let mut reader = BufReader::new(stderr).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            if tx_err.send(line).await.is_err() { break; }
        }
    });

    // We drop the original `tx` so the channel closes when both readers finish.
    drop(tx);

    // --- State Tracking ---
    let mut clean_title: Option<String> = None;
    let mut final_filepath: Option<String> = None;
    let mut download_count = 0; // 0 = none, 1 = first file (video), 2 = second file (audio)
    let mut captured_logs = Vec::new();

    // Loop until both streams are exhausted
    while let Some(line) = rx.recv().await {
        let trimmed = line.trim();
        if trimmed.is_empty() { continue; }

        captured_logs.push(trimmed.to_string());
        // Keep log size sane
        if captured_logs.len() > 50 { captured_logs.remove(0); }

        // 1. Check for Destination (Start of a file download)
        if let Some(caps) = DESTINATION_REGEX.captures(trimmed) {
            if let Some(f) = caps.name("filename") {
                let full_path = f.as_str().to_string();
                
                // If this is the first file, try to extract a clean title
                if clean_title.is_none() {
                    // Naive extraction: get filename from path, remove extension/id
                    let path = std::path::Path::new(&full_path);
                    if let Some(name_os) = path.file_name() {
                        let name_str = name_os.to_string_lossy().to_string();
                        // Remove the " [id].ext" suffix
                        let cleaned = TITLE_CLEANER_REGEX.replace(&name_str, "");
                        clean_title = Some(cleaned.to_string());
                    }
                }
                
                // Fallback for final path if no merger happens
                final_filepath = Some(full_path);
                download_count += 1;
            }
        }
        // 2. Check for Merger (Combines video + audio)
        else if let Some(caps) = MERGER_REGEX.captures(trimmed) {
            if let Some(f) = caps.name("filename") {
                final_filepath = Some(f.as_str().to_string());
                // Send a specific status update
                let _ = app_handle.emit_all("download-progress", DownloadProgressPayload {
                    job_id,
                    percentage: 100.0,
                    speed: "N/A".to_string(),
                    eta: "Done".to_string(),
                    filename: clean_title.clone(),
                    phase: Some("Merging".to_string()),
                });
            }
        }
        // 3. Check for "Already downloaded"
        else if let Some(caps) = ALREADY_DOWNLOADED_REGEX.captures(trimmed) {
            if let Some(f) = caps.name("filename") {
                final_filepath = Some(f.as_str().to_string());
                // Set clean title if we didn't get it yet
                if clean_title.is_none() {
                    let path = std::path::Path::new(final_filepath.as_ref().unwrap());
                    if let Some(name_os) = path.file_name() {
                        let name_str = name_os.to_string_lossy().to_string();
                        let cleaned = TITLE_CLEANER_REGEX.replace(&name_str, "");
                        clean_title = Some(cleaned.to_string());
                    }
                }
                
                let _ = app_handle.emit_all("download-progress", DownloadProgressPayload {
                    job_id,
                    percentage: 100.0,
                    speed: "N/A".to_string(),
                    eta: "Done".to_string(),
                    filename: clean_title.clone(),
                    phase: Some("Finished".to_string()),
                });
            }
        }
        // 4. Check for Progress
        else if let Some(caps) = PROGRESS_REGEX.captures(trimmed) {
             if let Some(percentage_str) = caps.name("percentage") {
                if let Ok(percentage) = percentage_str.as_str().parse::<f32>() {
                    let speed = caps.name("speed").map_or("Unknown", |m| m.as_str()).to_string();
                    let eta = caps.name("eta").map_or("Unknown", |m| m.as_str()).to_string();

                    // Determine Phase Text
                    let phase = if download_count <= 1 {
                        "Downloading Video".to_string()
                    } else {
                        "Downloading Audio".to_string()
                    };

                    let _ = app_handle.emit_all("download-progress", DownloadProgressPayload {
                        job_id,
                        percentage,
                        speed,
                        eta,
                        filename: clean_title.clone(),
                        phase: Some(phase),
                    });
                }
            }
        }
    }

    // --- Process Result ---

    let status = child.wait().await.expect("Child process encountered an error");
    let mut manager_lock = manager.lock().unwrap();

    // Check if job still exists (wasn't cancelled manually)
    if let Some(job_status) = manager_lock.get_job_status(job_id) {
        if job_status == JobStatus::Cancelled {
            manager_lock.remove_job(job_id);
            return; 
        }
    } else {
        return; 
    }

    if status.success() {
        if let Some(filename) = final_filepath {
            manager_lock.update_job_status(job_id, JobStatus::Completed).ok();
            let _ = app_handle.emit_all("download-complete", DownloadCompletePayload {
                job_id,
                output_path: filename,
            });
        } else {
            manager_lock.update_job_status(job_id, JobStatus::Error).ok();
            // Send the last few logs as context
            let context = captured_logs.join("\n");
            let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
                job_id,
                error: format!("Download process succeeded but output filename was missing.\nContext:\n{}", context),
            });
        }
    } else {
        manager_lock.update_job_status(job_id, JobStatus::Error).ok();
        let context = captured_logs.join("\n");
        let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
            job_id,
            error: format!(
                "yt-dlp exited with code {}.\nLogs:\n{}",
                status.code().unwrap_or(-1),
                context
            ),
        });
    }

    manager_lock.remove_job(job_id);
}
