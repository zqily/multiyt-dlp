// src-tauri/src/commands/downloader.rs

use std::sync::{Arc, Mutex};
use tauri::{AppHandle, State};
use uuid::Uuid;

use crate::core::{
    error::AppError,
    manager::{JobManager, JobStatus},
    process::run_download_process,
};
use crate::models::{Job, DownloadFormatPreset};

// Command to start a download
#[tauri::command]
pub async fn start_download(
    url: String,
    download_path: Option<String>,
    format_preset: DownloadFormatPreset,
    embed_metadata: bool,
    embed_thumbnail: bool, // New argument
    app_handle: AppHandle,
    manager: State<'_, Arc<Mutex<JobManager>>>,
) -> Result<Uuid, AppError> {
    // Basic URL validation
    if !url.starts_with("http://") && !url.starts_with("https://") {
        return Err(AppError::ValidationFailed("Invalid URL provided.".into()));
    }

    let job_id = Uuid::new_v4();
    let job = Job::new(url.clone());

    // Add job to the manager
    manager.lock().unwrap().add_job(job_id, job)?;

    // Spawn the download process in a separate async task
    let manager_clone = manager.inner().clone();
    tokio::spawn(async move {
        run_download_process(
            job_id, 
            url, 
            download_path, 
            format_preset, 
            embed_metadata,
            embed_thumbnail, // Pass to process
            app_handle, 
            manager_clone
        ).await;
    });

    Ok(job_id)
}

// Command to cancel a download
#[tauri::command]
pub fn cancel_download(
    job_id: Uuid,
    manager: State<'_, Arc<Mutex<JobManager>>>,
) -> Result<(), AppError> {
    let mut manager = manager.lock().unwrap();
    
    if let Some(pid) = manager.get_job_pid(job_id) {
        // Platform-specific process killing
        #[cfg(not(windows))]
        {
            use nix::sys::signal::{self, Signal};
            use nix::unistd::Pid;
            let pid_to_kill = Pid::from_raw(pid as i32);
            if let Err(e) = signal::kill(pid_to_kill, Signal::SIGINT) {
                return Err(AppError::ProcessKillFailed(format!(
                    "Failed to send SIGINT to PID {}: {}",
                    pid, e
                )));
            }
        }

        #[cfg(windows)]
        {
            // On Windows, we use taskkill to terminate the process tree.
            // /F for force, /T for tree (kills child processes).
            let status = std::process::Command::new("taskkill")
                .args(&["/F", "/T", "/PID", &pid.to_string()])
                .stdout(std::process::Stdio::null()) // Hide output
                .stderr(std::process::Stdio::null())
                .status();

            if let Err(e) = status {
                 return Err(AppError::ProcessKillFailed(format!(
                    "Failed to execute taskkill for PID {}: {}",
                    pid, e
                )));
            }
        }
        
        manager.update_job_status(job_id, JobStatus::Cancelled)?;
        println!("Cancelled job {} with PID {}", job_id, pid);
        Ok(())
    } else {
        Err(AppError::JobNotFound)
    }
}