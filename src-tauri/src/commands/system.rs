use std::process::Command;
use tauri::{AppHandle, Manager, Window};
use serde::Serialize;

#[derive(Serialize)]
pub struct AppDependencies {
    pub yt_dlp: bool,
    pub ffmpeg: bool,
    pub js_runtime: bool,
}

// Checks if yt-dlp, ffmpeg, and a valid JS runtime are available in the system's PATH
#[tauri::command]
pub fn check_dependencies() -> AppDependencies {
    let yt_dlp = Command::new("yt-dlp")
        .arg("--version")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false);

    let ffmpeg = Command::new("ffmpeg")
        .arg("-version") // ffmpeg uses -version, not --version
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false);

    // Check for any supported JS runtime (Deno is preferred by yt-dlp, then Node, then Bun)
    let runtimes = ["deno", "node", "bun"];
    let js_runtime = runtimes.iter().any(|r| {
        Command::new(r)
            .arg("--version")
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    });

    AppDependencies {
        yt_dlp,
        ffmpeg,
        js_runtime,
    }
}

// Opens a URL in the user's default browser
#[tauri::command]
pub fn open_external_link(app_handle: AppHandle, url: String) -> Result<(), String> {
    tauri::api::shell::open(&app_handle.shell_scope(), url, None)
        .map_err(|e| format!("Failed to open URL: {}", e))
}

// Transition from Splash to Main
#[tauri::command]
pub fn close_splash(window: Window) {
    // Close splashscreen
    if let Some(splash) = window.get_window("splashscreen") {
        splash.close().unwrap();
    }
    // Show main window
    if let Some(main) = window.get_window("main") {
        main.show().unwrap();
        main.set_focus().unwrap();
    }
}