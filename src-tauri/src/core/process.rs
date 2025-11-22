use std::process::Stdio;
use std::sync::{Arc, Mutex};
use once_cell::sync::Lazy;
use regex::Regex;
use tauri::{AppHandle, Manager};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::sync::mpsc;
use std::path::PathBuf;

use crate::core::manager::JobManager;
// Fix: Import JobStatus directly from models
use crate::models::{DownloadCompletePayload, DownloadErrorPayload, DownloadProgressPayload, DownloadFormatPreset, QueuedJob, JobStatus};

// --- Regex Definitions ---
static PROGRESS_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\[download\]\s+(?P<percentage>[\d\.]+)%\s+of\s+~?\s*(?P<size>[^\s]+)(?:\s+at\s+(?P<speed>[^\s]+(?:\s+B/s)?))?(?:\s+ETA\s+(?P<eta>[^\s]+))?").unwrap()
});
static DESTINATION_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\[download\]\s+Destination:\s+(?P<filename>.+)$").unwrap()
});
static ALREADY_DOWNLOADED_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\[download\]\s+(?:Destination:\s+)?(?P<filename>.+?)\s+has already been downloaded").unwrap()
});
static MERGER_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r#"\[Merger\]\s+Merging formats into\s+"?(?P<filename>.+?)"?$"#).unwrap()
});
static EXTRACT_AUDIO_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\[ExtractAudio\]\s+Destination:\s+(?P<filename>.+)$").unwrap()
});
static METADATA_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\[Metadata\]\s+Adding metadata to:\s+(?P<filename>.+)$").unwrap()
});
static THUMBNAIL_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\[(?:Thumbnails|EmbedThumbnail)\]").unwrap()
});
static FIXUP_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^\[(?:Fixup\w+)\]").unwrap()
});
static TITLE_CLEANER_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\s\[[a-zA-Z0-9_-]{11}\]\.(?:f[0-9]+\.)?[a-z0-9]+$").unwrap()
});

pub async fn run_download_process(
    job_data: QueuedJob,
    app_handle: AppHandle,
    manager: Arc<Mutex<JobManager>>,
) {
    let job_id = job_data.id;
    let url = job_data.url;
    
    // --- Determine Paths ---
    let downloads_dir = if let Some(path) = job_data.download_path {
        PathBuf::from(path)
    } else {
        match tauri::api::path::download_dir() {
            Some(path) => path,
            None => {
                emit_error(job_id, "Could not determine downloads directory.".into(), &app_handle, &manager);
                return;
            }
        }
    };
    
    // FIX 1: Ensure the directory exists before spawning, as we will set it as CWD
    if !downloads_dir.exists() {
        if let Err(e) = std::fs::create_dir_all(&downloads_dir) {
            emit_error(job_id, format!("Failed to create download directory: {}", e), &app_handle, &manager);
            return;
        }
    }

    // --- Build Command ---
    let mut cmd = Command::new("yt-dlp");
    
    // FIX 2: Enforce UTF-8 everywhere to prevent cp1252 crashes
    cmd.env("PYTHONUTF8", "1");
    cmd.env("PYTHONIOENCODING", "utf-8");
    
    // FIX 3: Set Working Directory to the download folder
    // This prevents us from having to pass absolute paths (which break on special chars in Windows) to the -o flag
    cmd.current_dir(&downloads_dir);

    cmd.arg(&url)
        .arg("-o")
        .arg(&job_data.filename_template) // Pass ONLY the template, relative to CWD
        .arg("--no-playlist")
        .arg("--no-simulate") 
        .arg("--newline")
        // FIX 4: Explicitly tell yt-dlp to handle Windows filenames, just in case
        .arg("--windows-filenames")
        // FIX 5: Force internal encoding to UTF-8 to match our Python env vars
        .arg("--encoding")
        .arg("utf-8")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    if job_data.embed_metadata { cmd.arg("--embed-metadata"); }
    if job_data.embed_thumbnail { cmd.arg("--embed-thumbnail"); }

    let height_filter = if job_data.video_resolution != "best" {
        let number_part: String = job_data.video_resolution.chars().filter(|c| c.is_numeric()).collect();
        if !number_part.is_empty() { format!("[height<={}]", number_part) } else { String::new() }
    } else { String::new() };

    match job_data.format_preset {
        DownloadFormatPreset::Best => {
            if !height_filter.is_empty() {
                 cmd.arg("-f").arg(format!("bestvideo{}+bestaudio/best{}", height_filter, height_filter));
            }
        }
        DownloadFormatPreset::BestMp4 => {
            cmd.arg("-f").arg(format!("bestvideo{}+bestaudio", height_filter));
            cmd.args(["--merge-output-format", "mp4"]);
        }
        DownloadFormatPreset::BestMkv => {
            cmd.arg("-f").arg(format!("bestvideo{}+bestaudio", height_filter));
            cmd.args(["--merge-output-format", "mkv"]);
        }
        DownloadFormatPreset::BestWebm => {
            cmd.arg("-f").arg(format!("bestvideo{}+bestaudio", height_filter));
            cmd.args(["--merge-output-format", "webm"]);
        }
        DownloadFormatPreset::AudioBest => { cmd.arg("-x").args(["-f", "bestaudio/best"]); }
        DownloadFormatPreset::AudioMp3 => { cmd.arg("-x").args(["--audio-format", "mp3", "--audio-quality", "0"]); }
        DownloadFormatPreset::AudioFlac => { cmd.arg("-x").args(["--audio-format", "flac", "--audio-quality", "0"]); }
        DownloadFormatPreset::AudioM4a => { cmd.arg("-x").args(["--audio-format", "m4a", "--audio-quality", "0"]); }
    }

    // --- Process Spawning ---
    let mut child = match cmd.spawn() {
        Ok(child) => child,
        Err(e) => {
            emit_error(job_id, format!("Failed to spawn yt-dlp: {}", e), &app_handle, &manager);
            return;
        }
    };

    let pid = child.id().expect("Failed to get child process ID");
    
    let should_continue = {
        let mut manager_lock = manager.lock().unwrap();
        // Check if cancelled before PID update
        if let Some(status) = manager_lock.get_job_status(job_id) {
            if status == JobStatus::Cancelled {
                false
            } else {
                 let _ = manager_lock.update_job_pid(job_id, pid);
                 let _ = manager_lock.update_job_status(job_id, JobStatus::Downloading);
                 true
            }
        } else {
            false
        }
    };

    if !should_continue {
        let _ = child.kill().await;
        // Even if we don't continue, we must release the slot
        let mut manager_lock = manager.lock().unwrap();
        manager_lock.notify_process_finished(app_handle.clone());
        return;
    }

    // --- FIX: IMMEDIATE NOTIFICATION ---
    // Notify frontend immediately that process exists, forcing UI state from Queued -> Active
    let _ = app_handle.emit_all("download-progress", DownloadProgressPayload {
        job_id,
        percentage: 0.0,
        speed: "Starting...".to_string(),
        eta: "Calculating...".to_string(),
        filename: None,
        phase: Some("Initializing Process...".to_string()),
    });
    // -----------------------------------

    // --- Output Handling & Phase Detection ---
    let stdout = child.stdout.take().expect("Failed to capture stdout");
    let stderr = child.stderr.take().expect("Failed to capture stderr");
    let (tx, mut rx) = mpsc::channel::<String>(100);

    let tx_out = tx.clone();
    tokio::spawn(async move {
        let mut reader = BufReader::new(stdout).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            if tx_out.send(line).await.is_err() { break; }
        }
    });

    let tx_err = tx.clone();
    tokio::spawn(async move {
        let mut reader = BufReader::new(stderr).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            if tx_err.send(line).await.is_err() { break; }
        }
    });

    drop(tx);

    let mut state_clean_title: Option<String> = None;
    let mut state_final_filepath: Option<String> = None;
    let mut state_percentage: f32 = 0.0;
    let mut state_phase: String = "Initializing".to_string();
    let mut captured_logs = Vec::new();
    
    // Flag to ensure we only release the network slot once per job
    let mut network_slot_released = false;

    // Helper to release network slot safely
    let release_network_slot = |mgr: &Arc<Mutex<JobManager>>, app: &AppHandle, released: &mut bool| {
        if !*released {
            *released = true;
            let mut lock = mgr.lock().unwrap();
            lock.notify_network_finished(app.clone());
        }
    };

    let extract_title = |path_str: &str| -> Option<String> {
        let path = std::path::Path::new(path_str);
        if let Some(name_os) = path.file_name() {
            let name_str = name_os.to_string_lossy().to_string();
            let cleaned = TITLE_CLEANER_REGEX.replace(&name_str, "");
            return Some(cleaned.to_string());
        }
        None
    };

    while let Some(line) = rx.recv().await {
        let trimmed = line.trim();
        if trimmed.is_empty() { continue; }
        
        captured_logs.push(trimmed.to_string());
        if captured_logs.len() > 50 { captured_logs.remove(0); }

        let mut emit_update = false;
        let mut speed = "N/A".to_string();
        let mut eta = "N/A".to_string();

        if let Some(caps) = METADATA_REGEX.captures(trimmed) {
            release_network_slot(&manager, &app_handle, &mut network_slot_released);
            if let Some(f) = caps.name("filename") { state_final_filepath = Some(f.as_str().to_string()); }
            state_phase = "Writing Metadata".to_string();
            state_percentage = 99.0;
            emit_update = true;
        }
        else if THUMBNAIL_REGEX.is_match(trimmed) {
            release_network_slot(&manager, &app_handle, &mut network_slot_released);
            state_phase = "Embedding Thumbnail".to_string();
            state_percentage = 99.0;
            emit_update = true;
        }
        else if let Some(caps) = MERGER_REGEX.captures(trimmed) {
            release_network_slot(&manager, &app_handle, &mut network_slot_released);
            if let Some(f) = caps.name("filename") {
                state_final_filepath = Some(f.as_str().to_string());
                state_clean_title = extract_title(f.as_str()).or(state_clean_title);
            }
            state_phase = "Merging Formats".to_string();
            state_percentage = 100.0;
            eta = "Done".to_string();
            emit_update = true;
        }
        else if let Some(caps) = EXTRACT_AUDIO_REGEX.captures(trimmed) {
            release_network_slot(&manager, &app_handle, &mut network_slot_released);
            if let Some(f) = caps.name("filename") {
                state_final_filepath = Some(f.as_str().to_string());
                state_clean_title = extract_title(f.as_str()).or(state_clean_title);
            }
            state_phase = "Extracting Audio".to_string();
            state_percentage = 100.0;
            eta = "Done".to_string();
            emit_update = true;
        }
        else if FIXUP_REGEX.is_match(trimmed) {
            release_network_slot(&manager, &app_handle, &mut network_slot_released);
            state_phase = "Fixing Container".to_string();
            emit_update = true;
        }
        else if let Some(caps) = ALREADY_DOWNLOADED_REGEX.captures(trimmed) {
            release_network_slot(&manager, &app_handle, &mut network_slot_released);
            if let Some(f) = caps.name("filename") {
                state_final_filepath = Some(f.as_str().to_string());
                state_clean_title = extract_title(f.as_str()).or(state_clean_title);
            }
            state_phase = "Finished".to_string();
            state_percentage = 100.0;
            eta = "Done".to_string();
            emit_update = true;
        }
        else if let Some(caps) = DESTINATION_REGEX.captures(trimmed) {
            if let Some(f) = caps.name("filename") {
                let full_path = f.as_str().to_string();
                if state_clean_title.is_none() { state_clean_title = extract_title(&full_path); }
                state_final_filepath = Some(full_path);
                state_phase = "Downloading".to_string();
                emit_update = true;
            }
        }
        else if let Some(caps) = PROGRESS_REGEX.captures(trimmed) {
             if let Some(percentage_str) = caps.name("percentage") {
                if let Ok(p) = percentage_str.as_str().parse::<f32>() {
                    state_percentage = p;
                    // If 100% reached, we can technically release network slot
                    if p >= 100.0 {
                        release_network_slot(&manager, &app_handle, &mut network_slot_released);
                    }
                    
                    if let Some(s) = caps.name("speed") {
                         let s_str = s.as_str();
                         if !s_str.contains("N/A") { speed = s_str.to_string(); }
                    }
                    if let Some(e) = caps.name("eta") {
                        let e_str = e.as_str();
                        eta = e_str.to_string();
                    }
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
                speed,
                eta,
                filename: state_clean_title.clone(),
                phase: Some(state_phase.clone()),
            });
        }
    }

    // --- Process Result ---
    let status = child.wait().await.expect("Child process encountered an error");
    
    // Ensure network slot is released if process crashes before finishing download
    release_network_slot(&manager, &app_handle, &mut network_slot_released);

    let mut manager_lock = manager.lock().unwrap();

    // Cleanup job from map
    let final_status_ok = if let Some(job_status) = manager_lock.get_job_status(job_id) {
        if job_status == JobStatus::Cancelled {
            manager_lock.remove_job(job_id);
            // Notify instance finished
            drop(manager_lock); // Unlock before calling notify
            let mut mgr = manager.lock().unwrap();
            mgr.notify_process_finished(app_handle.clone());
            return; 
        }
        true
    } else {
        false
    };

    if final_status_ok {
        if status.success() {
            let output = state_final_filepath.unwrap_or_else(|| "Unknown".to_string());
            manager_lock.update_job_status(job_id, JobStatus::Completed).ok();
            let _ = app_handle.emit_all("download-complete", DownloadCompletePayload {
                job_id,
                output_path: output,
            });
        } else {
            manager_lock.update_job_status(job_id, JobStatus::Error).ok();
            let context = captured_logs.join("\n");
            let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
                job_id,
                error: format!("yt-dlp exited with code {}.\nLast Logs:\n{}", status.code().unwrap_or(-1), context),
            });
        }
        manager_lock.remove_job(job_id);
    }
    
    drop(manager_lock);
    
    // Final slot release
    let mut mgr = manager.lock().unwrap();
    mgr.notify_process_finished(app_handle.clone());
}

fn emit_error(job_id: uuid::Uuid, error: String, app_handle: &AppHandle, manager: &Arc<Mutex<JobManager>>) {
    let mut lock = manager.lock().unwrap();
    lock.update_job_status(job_id, JobStatus::Error).ok();
    // Since we are erroring out early, we must release the instance slot reserved by process_queue
    lock.notify_process_finished(app_handle.clone());
    
    let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
        job_id,
        error,
    });
}