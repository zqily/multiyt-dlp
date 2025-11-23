use std::process::Stdio;
use std::sync::{Arc, Mutex};
use once_cell::sync::Lazy;
use regex::Regex;
use tauri::{AppHandle, Manager};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::sync::mpsc;
use std::path::{Path, PathBuf};
use std::fs;

use crate::core::manager::JobManager;
use crate::config::ConfigManager;
use crate::models::{DownloadCompletePayload, DownloadErrorPayload, DownloadProgressPayload, DownloadFormatPreset, QueuedJob, JobStatus};
use crate::commands::system::get_js_runtime_info;

// --- Regex Definitions ---
static PROGRESS_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"\[download\]\s+(?P<percentage>[\d\.]+)%\s+of\s+~?\s*(?P<size>[^\s]+)(?:\s+at\s+(?P<speed>[^\s]+(?:\s+B/s)?))?(?:\s+ETA\s+(?P<eta>[^\s]+))?").unwrap());
static DESTINATION_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"^\[download\]\s+Destination:\s+(?P<filename>.+)$").unwrap());
static ALREADY_DOWNLOADED_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"\[download\]\s+(?:Destination:\s+)?(?P<filename>.+?)\s+has already been downloaded").unwrap());
static MERGER_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r#"\[Merger\]\s+Merging formats into\s+"?(?P<filename>.+?)"?$"#).unwrap());
static EXTRACT_AUDIO_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"^\[ExtractAudio\]\s+Destination:\s+(?P<filename>.+)$").unwrap());
static METADATA_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"^\[Metadata\]\s+Adding metadata to:\s+(?P<filename>.+)$").unwrap());
static THUMBNAIL_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"^\[(?:Thumbnails|EmbedThumbnail)\]").unwrap());
static FIXUP_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"^\[(?:Fixup\w+)\]").unwrap());
static TITLE_CLEANER_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"\s\[[a-zA-Z0-9_-]{11}\]\.(?:f[0-9]+\.)?[a-z0-9]+$").unwrap());
static FILESYSTEM_ERROR_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"(?i)(No such file|Invalid argument|cannot be written|WinError 123|Postprocessing: Error opening input files)").unwrap());

/// Robust move: Tries rename (fast), falls back to copy+delete (slow, for cross-drive)
fn robust_move_file(src: &Path, dest: &Path) -> Result<(), std::io::Error> {
    if let Err(_) = fs::rename(src, dest) {
        fs::copy(src, dest)?;
        fs::remove_file(src)?;
    }
    Ok(())
}

pub async fn run_download_process(
    mut job_data: QueuedJob,
    app_handle: AppHandle,
    manager: Arc<Mutex<JobManager>>,
) {
    let job_id = job_data.id;
    let url = job_data.url.clone();

    // Retrieve Global Config (ConfigManager is thread-safe)
    let config_manager = app_handle.state::<Arc<ConfigManager>>();

    loop {
        // Refresh config on every retry loop to catch immediate changes
        let general_config = config_manager.get_config().general;

        let app_dir = app_handle.path_resolver().app_data_dir().unwrap();
        let bin_dir = app_dir.join("bin");
        
        // 1. Determine Target Destination (Where the user WANTS the file)
        let target_dir = if let Some(ref path) = job_data.download_path {
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
        
        if !target_dir.exists() {
            if let Err(e) = std::fs::create_dir_all(&target_dir) {
                emit_error(job_id, format!("Failed to create target directory: {}", e), &app_handle, &manager);
                return;
            }
        }

        // 2. Determine Temp Directory (Where execution HAPPENS)
        let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
        let temp_dir = home.join(".multiyt-dlp").join("temp_downloads");
        if !temp_dir.exists() {
            if let Err(e) = std::fs::create_dir_all(&temp_dir) {
                emit_error(job_id, format!("Failed to create temp directory: {}", e), &app_handle, &manager);
                return;
            }
        }

        let mut yt_dlp_cmd = "yt-dlp".to_string();
        let local_exe = bin_dir.join(if cfg!(windows) { "yt-dlp.exe" } else { "yt-dlp" });
        if local_exe.exists() {
            yt_dlp_cmd = local_exe.to_string_lossy().to_string();
        }

        let mut cmd = Command::new(yt_dlp_cmd);
        
        if let Ok(current_path) = std::env::var("PATH") {
            let new_path = format!("{}{}{}", bin_dir.to_string_lossy(), if cfg!(windows) { ";" } else { ":" }, current_path);
            cmd.env("PATH", new_path);
        } else {
            cmd.env("PATH", bin_dir.to_string_lossy().to_string());
        }
        
        cmd.env("PYTHONUTF8", "1");
        cmd.env("PYTHONIOENCODING", "utf-8");
        
        // IMPORTANT: Run inside the temp directory
        cmd.current_dir(&temp_dir);

        // --- AUTO-INJECT JS RUNTIME ---
        if let Some((name, path)) = get_js_runtime_info(&bin_dir) {
            cmd.arg("--js-runtimes");
            cmd.arg(format!("{}:{}", name, path));
        }

        // --- COOKIES INJECTION ---
        if let Some(cookie_path) = &general_config.cookies_path {
            if !cookie_path.trim().is_empty() {
                cmd.arg("--cookies").arg(cookie_path);
            }
        } else if let Some(browser) = &general_config.cookies_from_browser {
            if !browser.trim().is_empty() && browser != "none" {
                cmd.arg("--cookies-from-browser").arg(browser);
            }
        }

        cmd.arg(&url)
            .arg("-o")
            .arg(&job_data.filename_template) 
            .arg("--no-playlist")
            .arg("--no-simulate") 
            .arg("--newline")
            .arg("--windows-filenames")
            .arg("--encoding")
            .arg("utf-8")
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        #[cfg(target_os = "windows")]
        {
            cmd.creation_flags(0x08000000);
        }

        if job_data.restrict_filenames {
            cmd.arg("--restrict-filenames");
            cmd.arg("--trim-filenames").arg("200");
        }

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
            let mut manager_lock = manager.lock().unwrap();
            manager_lock.notify_process_finished(app_handle.clone());
            return;
        }

        if job_data.restrict_filenames {
            let _ = app_handle.emit_all("download-progress", DownloadProgressPayload {
                job_id,
                percentage: 0.0,
                speed: "Retrying...".to_string(),
                eta: "--".to_string(),
                filename: None,
                phase: Some("Sanitizing Filenames (Retry)".to_string()),
            });
        } else {
            let _ = app_handle.emit_all("download-progress", DownloadProgressPayload {
                job_id,
                percentage: 0.0,
                speed: "Starting...".to_string(),
                eta: "Calculating...".to_string(),
                filename: None,
                phase: Some("Initializing Process...".to_string()),
            });
        }

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
        let mut state_final_filename: Option<String> = None; // Just the filename, no path
        let mut state_percentage: f32 = 0.0;
        let mut state_phase: String = "Initializing".to_string();
        let mut captured_logs = Vec::new();
        
        let mut network_slot_released = false;

        let release_network_slot = |mgr: &Arc<Mutex<JobManager>>, app: &AppHandle, released: &mut bool| {
            if !*released {
                *released = true;
                let mut lock = mgr.lock().unwrap();
                lock.notify_network_finished(app.clone());
            }
        };

        let extract_filename_from_path = |path_str: &str| -> Option<String> {
            Path::new(path_str).file_name()
                .map(|os| os.to_string_lossy().to_string())
        };

        let extract_clean_title = |path_str: &str| -> Option<String> {
             if let Some(fname) = extract_filename_from_path(path_str) {
                let cleaned = TITLE_CLEANER_REGEX.replace(&fname, "");
                return Some(cleaned.to_string());
             }
             None
        };

        while let Some(line) = rx.recv().await {
            let trimmed = line.trim();
            if trimmed.is_empty() { continue; }
            
            captured_logs.push(trimmed.to_string());
            if captured_logs.len() > 100 { captured_logs.remove(0); }

            let mut emit_update = false;
            let mut speed = "N/A".to_string();
            let mut eta = "N/A".to_string();

            if let Some(caps) = METADATA_REGEX.captures(trimmed) {
                release_network_slot(&manager, &app_handle, &mut network_slot_released);
                if let Some(f) = caps.name("filename") { 
                    state_final_filename = extract_filename_from_path(f.as_str());
                }
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
                    state_final_filename = extract_filename_from_path(f.as_str());
                    state_clean_title = extract_clean_title(f.as_str()).or(state_clean_title);
                }
                state_phase = "Merging Formats".to_string();
                state_percentage = 100.0;
                eta = "Done".to_string();
                emit_update = true;
            }
            else if let Some(caps) = EXTRACT_AUDIO_REGEX.captures(trimmed) {
                release_network_slot(&manager, &app_handle, &mut network_slot_released);
                if let Some(f) = caps.name("filename") {
                    state_final_filename = extract_filename_from_path(f.as_str());
                    state_clean_title = extract_clean_title(f.as_str()).or(state_clean_title);
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
                    state_final_filename = extract_filename_from_path(f.as_str());
                    state_clean_title = extract_clean_title(f.as_str()).or(state_clean_title);
                }
                state_phase = "Finished".to_string();
                state_percentage = 100.0;
                eta = "Done".to_string();
                emit_update = true;
            }
            else if let Some(caps) = DESTINATION_REGEX.captures(trimmed) {
                if let Some(f) = caps.name("filename") {
                    let full_path_str = f.as_str();
                    if state_clean_title.is_none() { state_clean_title = extract_clean_title(full_path_str); }
                    state_final_filename = extract_filename_from_path(full_path_str);
                    state_phase = "Downloading".to_string();
                    emit_update = true;
                }
            }
            else if let Some(caps) = PROGRESS_REGEX.captures(trimmed) {
                if let Some(percentage_str) = caps.name("percentage") {
                    if let Ok(p) = percentage_str.as_str().parse::<f32>() {
                        state_percentage = p;
                        if p >= 100.0 {
                            release_network_slot(&manager, &app_handle, &mut network_slot_released);
                        }
                        if let Some(s) = caps.name("speed") {
                            let s_str = s.as_str();
                            if !s_str.contains("N/A") { speed = s_str.to_string(); }
                        }
                        if let Some(e) = caps.name("eta") {
                            eta = e.as_str().to_string();
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

        let status = child.wait().await.expect("Child process encountered an error");
        release_network_slot(&manager, &app_handle, &mut network_slot_released);

        let mut manager_lock = manager.lock().unwrap();
        if let Some(job_status) = manager_lock.get_job_status(job_id) {
            if job_status == JobStatus::Cancelled {
                manager_lock.remove_job(job_id);
                drop(manager_lock); 
                let mut mgr = manager.lock().unwrap();
                mgr.notify_process_finished(app_handle.clone());
                return; 
            }
        }
        drop(manager_lock);

        if status.success() {
            // SUCCESS: Move file from TEMP to TARGET
            if let Some(filename) = state_final_filename {
                let src_path = temp_dir.join(&filename);
                let dest_path = target_dir.join(&filename);
                
                if src_path.exists() {
                    match robust_move_file(&src_path, &dest_path) {
                        Ok(_) => {
                            let mut manager_lock = manager.lock().unwrap();
                            manager_lock.update_job_status(job_id, JobStatus::Completed).ok();
                            let _ = app_handle.emit_all("download-complete", DownloadCompletePayload {
                                job_id,
                                output_path: dest_path.to_string_lossy().to_string(),
                            });
                            manager_lock.remove_job(job_id);
                            drop(manager_lock);
                            break;
                        },
                        Err(e) => {
                            // Move failed
                            let mut manager_lock = manager.lock().unwrap();
                            manager_lock.update_job_status(job_id, JobStatus::Error).ok();
                            let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
                                job_id,
                                error: format!("Download successful, but failed to move to destination: {}", e),
                            });
                            manager_lock.remove_job(job_id);
                            drop(manager_lock);
                            break;
                        }
                    }
                } else {
                    // File missing in temp?
                     let mut manager_lock = manager.lock().unwrap();
                     manager_lock.update_job_status(job_id, JobStatus::Error).ok();
                     let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
                         job_id,
                         error: "Output file not found in temporary directory.".to_string(),
                     });
                     manager_lock.remove_job(job_id);
                     drop(manager_lock);
                     break;
                }
            } else {
                // Could not determine filename
                let mut manager_lock = manager.lock().unwrap();
                manager_lock.update_job_status(job_id, JobStatus::Error).ok();
                let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
                    job_id,
                    error: "Download finished, but filename could not be determined.".to_string(),
                });
                manager_lock.remove_job(job_id);
                drop(manager_lock);
                break;
            }
        } else {
            // FAIL
            let log_blob = captured_logs.join("\n");
            let is_filesystem_error = FILESYSTEM_ERROR_REGEX.is_match(&log_blob);
            
            if !job_data.restrict_filenames && is_filesystem_error {
                job_data.restrict_filenames = true;
                continue; 
            }

            let mut manager_lock = manager.lock().unwrap();
            manager_lock.update_job_status(job_id, JobStatus::Error).ok();
            let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
                job_id,
                error: format!("yt-dlp exited with code {}.\nLast Logs:\n{}", status.code().unwrap_or(-1), log_blob),
            });
            manager_lock.remove_job(job_id);
            drop(manager_lock);
            break;
        }
    }
    
    let mut mgr = manager.lock().unwrap();
    mgr.notify_process_finished(app_handle.clone());
}

fn emit_error(job_id: uuid::Uuid, error: String, app_handle: &AppHandle, manager: &Arc<Mutex<JobManager>>) {
    let mut lock = manager.lock().unwrap();
    lock.update_job_status(job_id, JobStatus::Error).ok();
    lock.notify_process_finished(app_handle.clone());
    
    let _ = app_handle.emit_all("download-error", DownloadErrorPayload {
        job_id,
        error,
    });
}