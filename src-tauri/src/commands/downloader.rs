use tauri::{State};
use uuid::Uuid;
use std::process::Command;

use crate::core::{
    error::AppError,
    manager::{JobManagerHandle},
};
use crate::models::{DownloadFormatPreset, QueuedJob, PlaylistResult, PlaylistEntry};

// Helper: Probes the URL to see if it's a playlist or single video
fn probe_url(url: &str) -> Result<Vec<PlaylistEntry>, AppError> {
    let mut cmd = Command::new("yt-dlp");
    cmd.arg("--flat-playlist")
       .arg("--dump-single-json")
       .arg("--no-warnings")
       .arg(url);

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
            if let Some(u) = entry.get("url").and_then(|s| s.as_str()) {
                entries.push(PlaylistEntry {
                    id: entry.get("id").and_then(|s| s.as_str()).map(|s| s.to_string()),
                    url: u.to_string(),
                    title: entry.get("title").and_then(|s| s.as_str()).unwrap_or("Unknown").to_string(),
                });
            }
        }
    } else {
        entries.push(PlaylistEntry {
            id: parsed.get("id").and_then(|s| s.as_str()).map(|s| s.to_string()),
            url: parsed.get("webpage_url").and_then(|s| s.as_str()).unwrap_or(url).to_string(),
            title: parsed.get("title").and_then(|s| s.as_str()).unwrap_or("Unknown").to_string(),
        });
    }

    Ok(entries)
}

#[tauri::command]
pub async fn expand_playlist(url: String) -> Result<PlaylistResult, AppError> {
    let entries = probe_url(&url)?;
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
    restrict_filenames: Option<bool>,
    manager: State<'_, JobManagerHandle>, 
) -> Result<Vec<Uuid>, AppError> { 
    
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

    let entries = probe_url(&url)?;
    let mut created_job_ids = Vec::new();

    for entry in entries {
        let job_id = Uuid::new_v4();
        
        let job_data = QueuedJob {
            id: job_id,
            url: entry.url,
            download_path: download_path.clone(),
            format_preset: format_preset.clone(),
            video_resolution: video_resolution.clone(),
            embed_metadata,
            embed_thumbnail,
            filename_template: safe_template.clone(),
            restrict_filenames: restrict_filenames.unwrap_or(false),
        };

        manager.add_job(job_data).await
            .map_err(|e| AppError::ValidationFailed(e))?;
            
        created_job_ids.push(job_id);
    }

    Ok(created_job_ids)
}

#[tauri::command]
pub async fn cancel_download(
    job_id: Uuid,
    manager: State<'_, JobManagerHandle>,
) -> Result<(), AppError> {
    manager.cancel_job(job_id).await;
    Ok(())
}

#[tauri::command]
pub async fn get_pending_jobs(manager: State<'_, JobManagerHandle>) -> Result<u32, String> {
    Ok(manager.get_pending_count().await)
}

#[tauri::command]
pub async fn resume_pending_jobs(
    manager: State<'_, JobManagerHandle>
) -> Result<Vec<QueuedJob>, String> {
    Ok(manager.resume_pending().await)
}

#[tauri::command]
pub async fn clear_pending_jobs(manager: State<'_, JobManagerHandle>) -> Result<(), String> {
    manager.clear_pending().await;
    Ok(())
}