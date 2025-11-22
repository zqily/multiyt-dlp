use std::process::Command;
use tauri::{AppHandle, Manager};
use serde::Serialize;
use regex::Regex;

#[derive(Serialize, Clone)]
pub struct DependencyInfo {
    pub name: String,
    pub available: bool,
    pub version: Option<String>,
    pub path: Option<String>,
}

#[derive(Serialize)]
pub struct AppDependencies {
    pub yt_dlp: DependencyInfo,
    pub ffmpeg: DependencyInfo,
    pub js_runtime: DependencyInfo,
}

fn resolve_binary_info(bin_name: &str, version_flag: &str) -> DependencyInfo {
    // 1. Check Path
    let path_cmd = if cfg!(target_os = "windows") { "where" } else { "which" };
    let path_output = Command::new(path_cmd).arg(bin_name).output().ok();
    
    let path = path_output
        .filter(|o| o.status.success())
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| s.lines().next().unwrap_or("").trim().to_string());

    let available = path.is_some();

    // 2. Check Version if available
    let mut version = None;
    if available {
        if let Ok(output) = Command::new(bin_name).arg(version_flag).output() {
             if output.status.success() {
                 let out_str = String::from_utf8_lossy(&output.stdout).to_string();
                 // Naive cleaning: take first line, split by space if needed
                 // Specific logic for ffmpeg vs others
                 let first_line = out_str.lines().next().unwrap_or("").trim().to_string();
                 version = Some(first_line);
             }
        }
    }

    DependencyInfo {
        name: bin_name.to_string(),
        available,
        version,
        path
    }
}

#[tauri::command]
pub fn check_dependencies() -> AppDependencies {
    // 1. yt-dlp
    let yt_dlp = resolve_binary_info("yt-dlp", "--version");

    // 2. ffmpeg (Requires specific parsing as output is verbose)
    let mut ffmpeg = resolve_binary_info("ffmpeg", "-version");
    if let Some(ref v) = ffmpeg.version {
        // Extract just the version number from "ffmpeg version 6.0 ..."
        let re = Regex::new(r"ffmpeg version ([^\s]+)").unwrap();
        if let Some(caps) = re.captures(v) {
            ffmpeg.version = Some(caps[1].to_string());
        }
    }

    // 3. JS Runtime (Try Deno -> Node -> Bun)
    let mut js_runtime = DependencyInfo { 
        name: "None".to_string(), available: false, version: None, path: None 
    };

    let runtimes = [("deno", "--version"), ("node", "--version"), ("bun", "--version")];
    
    for (bin, flag) in runtimes {
        let info = resolve_binary_info(bin, flag);
        if info.available {
            js_runtime = info;
            // Clean up version string if needed
            if bin == "deno" {
                 // Deno outputs "deno x.x.x"
                 if let Some(ref v) = js_runtime.version {
                     js_runtime.version = Some(v.replace("deno ", ""));
                 }
            }
            break;
        }
    }

    AppDependencies {
        yt_dlp,
        ffmpeg,
        js_runtime,
    }
}

#[tauri::command]
pub fn open_external_link(app_handle: AppHandle, url: String) -> Result<(), String> {
    tauri::api::shell::open(&app_handle.shell_scope(), url, None)
        .map_err(|e| format!("Failed to open URL: {}", e))
}

#[tauri::command]
pub fn close_splash(app_handle: AppHandle) {
    if let Some(splash) = app_handle.get_window("splashscreen") {
        let _ = splash.close();
    }

    if let Some(main) = app_handle.get_window("main") {
        let _ = main.show();
        let _ = main.set_focus();
    }
}