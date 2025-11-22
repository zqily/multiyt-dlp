use std::sync::{Arc, Mutex};
use tauri::{AppHandle, State};
use uuid::Uuid;
use std::process::Command;

use crate::core::{
    error::AppError,
    manager::JobManager,
};
use crate::models::{DownloadFormatPreset, QueuedJob, PlaylistResult, PlaylistEntry, JobStatus};

#[tauri::command]
pub async fn expand_playlist(url: String) -> Result<PlaylistResult, AppError> {
    let mut cmd = Command::new("yt-dlp");
    cmd.arg("--flat-playlist")
       .arg("--dump-single-json")
       .arg("--no-warnings")
       .arg(&url);

    // SILENCE WINDOW ON WINDOWS
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000);
    }

    let output = cmd.output().map_err(|e| AppError::IoError(e.to_string()))?;

    if !output.status.success() {
        return Err(AppError::ProcessFailed { 
            exit_code: output.status.code().unwrap_or(-1), 
            stderr: String::from_utf8_lossy(&output.stderr).to_string() 
        });
    }

    let json_str = String::from_utf8_lossy(&output.stdout);
    let parsed: serde_json::Value = serde_json::from_str(&json_str)
        .map_err(|e| AppError::ValidationFailed(format!("Failed to parse JSON: {}", e)))?;

    let mut entries = Vec::new();

    if let Some(entries_arr) = parsed.get("entries").and_then(|e| e.as_array()) {
        for entry in entries_arr {
            if let Some(url) = entry.get("url").and_then(|s| s.as_str()) {
                entries.push(PlaylistEntry {
                    id: entry.get("id").and_then(|s| s.as_str()).map(|s| s.to_string()),
                    url: url.to_string(),
                    title: entry.get("title").and_then(|s| s.as_str()).unwrap_or("Unknown").to_string(),
                });
            }
        }
    } else {
        entries.push(PlaylistEntry {
            id: parsed.get("id").and_then(|s| s.as_str()).map(|s| s.to_string()),
            url: parsed.get("webpage_url").and_then(|s| s.as_str()).unwrap_or(&url).to_string(),
            title: parsed.get("title").and_then(|s| s.as_str()).unwrap_or("Unknown").to_string(),
        });
    }

    Ok(PlaylistResult { entries })
}

#[tauri::command]
pub async fn start_download(
    url: String,
    download_path: Option<String>,
    format_preset: DownloadFormatPreset,
    video_resolution: String, 
    embed_metadata: bool,
    embed_thumbnail: bool,
    filename_template: String,
    app_handle: AppHandle,
    manager: State<'_, Arc<Mutex<JobManager>>>,
) -> Result<Uuid, AppError> {
    
    if !url.starts_with("http://") && !url.starts_with("https://") {
        return Err(AppError::ValidationFailed("Invalid URL provided.".into()));
    }

    let safe_template = if filename_template.trim().is_empty() {
        "%(title)s.%(ext)s".to_string()
    } else {
        if filename_template.contains("..") || filename_template.starts_with("/") || filename_template.starts_with("\\") {
             return Err(AppError::ValidationFailed("Invalid characters in filename template.".into()));
        }
        filename_template
    };

    let job_id = Uuid::new_v4();
    
    let job_data = QueuedJob {
        id: job_id,
        url: url.clone(),
        download_path,
        format_preset,
        video_resolution,
        embed_metadata,
        embed_thumbnail,
        filename_template: safe_template,
    };

    manager.lock().unwrap().add_job(job_data, app_handle)?;

    Ok(job_id)
}

#[tauri::command]
pub fn cancel_download(
    job_id: Uuid,
    manager: State<'_, Arc<Mutex<JobManager>>>,
) -> Result<(), AppError> {
    let mut manager = manager.lock().unwrap();
    
    if let Some(pid) = manager.get_job_pid(job_id) {
        #[cfg(not(windows))]
        {
            use nix::sys::signal::{self, Signal};
            use nix::unistd::Pid;
            let pid_to_kill = Pid::from_raw(pid as i32);
            if let Err(e) = signal::kill(pid_to_kill, Signal::SIGINT) {
                return Err(AppError::ProcessKillFailed(format!("Failed to send SIGINT: {}", e)));
            }
        }

        #[cfg(windows)]
        {
            let mut cmd = std::process::Command::new("taskkill");
            cmd.args(&["/F", "/T", "/PID", &pid.to_string()]);
            cmd.stdout(std::process::Stdio::null());
            cmd.stderr(std::process::Stdio::null());
            
            // SILENCE TASKKILL WINDOW
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x08000000); 

            let status = cmd.status();
            
            if let Err(e) = status {
                 return Err(AppError::ProcessKillFailed(format!("Failed to execute taskkill: {}", e)));
            }
        }
        
        manager.update_job_status(job_id, JobStatus::Cancelled)?;
        Ok(())
    } else {
        if manager.get_job_status(job_id).is_some() {
             manager.update_job_status(job_id, JobStatus::Cancelled)?;
             manager.remove_job(job_id); 
             Ok(())
        } else {
            Err(AppError::JobNotFound)
        }
    }
}