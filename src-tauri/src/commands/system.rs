use std::process::Command;
use tauri::AppHandle;

use crate::core::error::AppError;

// Checks if yt-dlp is available in the system's PATH
#[tauri::command]
pub fn check_yt_dlp_path() -> Result<bool, AppError> {
    Command::new("yt-dlp")
        .arg("--version")
        .output()
        .map(|output| output.status.success())
        .map_err(|_| AppError::YtDlpNotFound)
}

// Opens a URL in the user's default browser
#[tauri::command]
pub fn open_external_link(app_handle: AppHandle, url: String) -> Result<(), String> {
    tauri::api::shell::open(&app_handle.shell_scope(), url, None)
        .map_err(|e| format!("Failed to open URL: {}", e))
}
