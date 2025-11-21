// src-tauri/src/core/process.rs

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

// [download] 12.3% of ~1.23MiB at 5.55MiB/s ETA 00:18
static PROGRESS_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\[download\]\s+(?P<percentage>[\d\.]+)%\s+of\s+~?\s*(?P<size>[^\s]+)(?:\s+at\s+(?P<speed>[^\s]+(?:\s+B/s)?))?(?:\s+ETA\s+(?P<eta>[^\s]+))?").unwrap()
});

// [download] Destination: path/to/Title. [id].f123.mp4
static DESTINATION_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\[download\]\s+Destination:\s+(?P<filename>.+)$").unwrap()
});

// [download] path/to/file has already been downloaded
static ALREADY_DOWNLOADED_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\[download\]\s+(?:Destination:\s+)?(?P<filename>.+?)\s+has already been downloaded").unwrap()
});

// [Merger] Merging formats into "path/to/file.mkv"
static MERGER_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r#"\[Merger\]\s+Merging formats into\s+"?(?P<filename>.+?)"?$"#).unwrap()
});

// [ExtractAudio] Destination: path/to/file.opus
static EXTRACT_AUDIO_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\[ExtractAudio\]\s+Destination:\s+(?P<filename>.+)$").unwrap()
});

// [Metadata] Adding metadata to: path/to/file
static METADATA_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\[Metadata\]\s+Adding metadata to:\s+(?P<filename>.+)$").unwrap()
});

// [Thumbnails] Downloading thumbnail ... or [EmbedThumbnail] ...
static THUMBNAIL_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\[(?:Thumbnails|EmbedThumbnail)\]").unwrap()
});

// [FixupM3u8] Fixing output file
static FIXUP_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\[(?:Fixup\w+)\]").unwrap()
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
    format_preset: DownloadFormatPreset,
    embed_metadata: bool,
    embed_thumbnail: bool,
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

    // --- Metadata & Thumbnail Options ---
    if embed_metadata {
        cmd.arg("--embed-metadata");
    }
    
    if embed_thumbnail {
        cmd.arg("--embed-thumbnail");
    }

    // --- Format Preset Logic ---
    match format_preset {
        DownloadFormatPreset::Best => {
            // Default behavior
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

    drop(tx);

    // --- State Tracking ---
    let mut state_clean_title: Option<String> = None;
    let mut state_final_filepath: Option<String> = None;
    let mut state_percentage: f32 = 0.0;
    let mut state_speed: String = "Starting...".to_string();
    let mut state_eta: String = "Calculating...".to_string();
    let mut state_phase: String = "Initializing".to_string();

    let mut captured_logs = Vec::new();

    // Helper closure to extract clean title from path
    let extract_title = |path_str: &str| -> Option<String> {
        let path = std::path::Path::new(path_str);
        if let Some(name_os) = path.file_name() {
            let name_str = name_os.to_string_lossy().to_string();
            let cleaned = TITLE_CLEANER_REGEX.replace(&name_str, "");
            return Some(cleaned.to_string());
        }
        None
    };

    // Loop until both streams are exhausted
    while let Some(line) = rx.recv().await {
        let trimmed = line.trim();
        if trimmed.is_empty() { continue; }

        captured_logs.push(trimmed.to_string());
        if captured_logs.len() > 50 { captured_logs.remove(0); }

        let mut emit_update = false;

        // 1. Check Phase: Metadata
        if let Some(caps) = METADATA_REGEX.captures(trimmed) {
            if let Some(f) = caps.name("filename") {
                state_final_filepath = Some(f.as_str().to_string());
            }
            state_phase = "Writing Metadata".to_string();
            // Often metadata writing is near instant, keep percentage at 100 if we reached it
            if state_percentage < 100.0 { state_percentage = 99.0; } 
            emit_update = true;
        }
        // 2. Check Phase: Thumbnails
        else if THUMBNAIL_REGEX.is_match(trimmed) {
            state_phase = "Embedding Thumbnail".to_string();
            if state_percentage < 100.0 { state_percentage = 99.0; }
            emit_update = true;
        }
        // 3. Check Phase: Merger
        else if let Some(caps) = MERGER_REGEX.captures(trimmed) {
            if let Some(f) = caps.name("filename") {
                state_final_filepath = Some(f.as_str().to_string());
                state_clean_title = extract_title(f.as_str()).or(state_clean_title);
            }
            state_phase = "Merging Formats".to_string();
            state_percentage = 100.0;
            state_eta = "Done".to_string();
            emit_update = true;
        }
        // 4. Check Phase: Extract Audio
        else if let Some(caps) = EXTRACT_AUDIO_REGEX.captures(trimmed) {
            if let Some(f) = caps.name("filename") {
                state_final_filepath = Some(f.as_str().to_string());
                state_clean_title = extract_title(f.as_str()).or(state_clean_title);
            }
            state_phase = "Extracting Audio".to_string();
            state_percentage = 100.0;
            state_eta = "Done".to_string();
            emit_update = true;
        }
        // 5. Check Phase: Fixup
        else if FIXUP_REGEX.is_match(trimmed) {
            state_phase = "Fixing Container".to_string();
            emit_update = true;
        }
        // 6. Check Phase: Already Downloaded
        else if let Some(caps) = ALREADY_DOWNLOADED_REGEX.captures(trimmed) {
            if let Some(f) = caps.name("filename") {
                state_final_filepath = Some(f.as_str().to_string());
                state_clean_title = extract_title(f.as_str()).or(state_clean_title);
            }
            state_phase = "Finished".to_string();
            state_percentage = 100.0;
            state_eta = "Done".to_string();
            state_speed = "N/A".to_string();
            emit_update = true;
        }
        // 7. Check Destination (Filename discovery)
        else if let Some(caps) = DESTINATION_REGEX.captures(trimmed) {
            if let Some(f) = caps.name("filename") {
                let full_path = f.as_str().to_string();
                if state_clean_title.is_none() {
                    state_clean_title = extract_title(&full_path);
                }
                state_final_filepath = Some(full_path);
                state_phase = "Downloading".to_string();
                emit_update = true;
            }
        }
        // 8. Check Progress
        else if let Some(caps) = PROGRESS_REGEX.captures(trimmed) {
             if let Some(percentage_str) = caps.name("percentage") {
                if let Ok(p) = percentage_str.as_str().parse::<f32>() {
                    state_percentage = p;
                    
                    // Only update speed/eta if present and not "Unknown" (keep last known)
                    if let Some(s) = caps.name("speed") {
                        let s_str = s.as_str();
                        if s_str != "Unknown" && !s_str.contains("N/A") {
                            state_speed = s_str.to_string();
                        }
                    }
                    if let Some(e) = caps.name("eta") {
                        let e_str = e.as_str();
                        if e_str != "Unknown" {
                            state_eta = e_str.to_string();
                        }
                    }
                    
                    // If we are downloading, ensure phase says so (unless we were in a post-process)
                    if !state_phase.contains("Merging") && !state_phase.contains("Extracting") && !state_phase.contains("Writing") && !state_phase.contains("Embedding") {
                        state_phase = "Downloading".to_string();
                    }
                    
                    emit_update = true;
                }
            }
        }

        if emit_update {
            let _ = app_handle.emit_all("download-progress", DownloadProgressPayload {
                job_id,
                percentage: state_percentage,
                speed: state_speed.clone(),
                eta: state_eta.clone(),
                filename: state_clean_title.clone(),
                phase: Some(state_phase.clone()),
            });
        }
    }

    // --- Process Result ---

    let status = child.wait().await.expect("Child process encountered an error");
    let mut manager_lock = manager.lock().unwrap();

    if let Some(job_status) = manager_lock.get_job_status(job_id) {
        if job_status == JobStatus::Cancelled {
            manager_lock.remove_job(job_id);
            return; 
        }
    } else {
        return; 
    }

    if status.success() {
        if let Some(filename) = state_final_filepath {
            manager_lock.update_job_status(job_id, JobStatus::Completed).ok();
            let _ = app_handle.emit_all("download-complete", DownloadCompletePayload {
                job_id,
                output_path: filename,
            });
        } else {
            // Fallback: if success but no filename captured, it might be a short file or logic error
            // But since exit code is 0, we treat as success if we can't find path.
            manager_lock.update_job_status(job_id, JobStatus::Completed).ok();
            let _ = app_handle.emit_all("download-complete", DownloadCompletePayload {
                job_id,
                output_path: "Unknown".to_string(),
            });
        }
    } else {
        manager_lock.update_job_status(job_id, JobStatus::Error).ok();
        let context = captured_logs.join("\n");
        let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
            job_id,
            error: format!(
                "yt-dlp exited with code {}.\nLast Logs:\n{}",
                status.code().unwrap_or(-1),
                context
            ),
        });
    }

    manager_lock.remove_job(job_id);
}