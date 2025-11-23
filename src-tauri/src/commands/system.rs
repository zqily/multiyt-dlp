use std::process::Command;
use tauri::{AppHandle, Manager};
use serde::Serialize;
use regex::Regex;
use crate::core::deps;
use std::path::PathBuf;

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

// Helper to create a command that doesn't spawn a visible window on Windows
fn new_silent_command(program: &str) -> Command {
    let mut cmd = Command::new(program);
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }
    cmd
}

fn resolve_binary_info(bin_name: &str, version_flag: &str, local_bin_path: &PathBuf) -> DependencyInfo {
    // 1. Check Local Bin Folder First
    let local_path = local_bin_path.join(bin_name);
    let local_available = local_path.exists();

    let final_path = if local_available {
        Some(local_path.to_string_lossy().to_string())
    } else {
        // 2. Check System Path
        let path_cmd = if cfg!(target_os = "windows") { "where" } else { "which" };
        new_silent_command(path_cmd)
            .arg(bin_name)
            .output()
            .ok()
            .filter(|o| o.status.success())
            .and_then(|o| String::from_utf8(o.stdout).ok())
            .map(|s| s.lines().next().unwrap_or("").trim().to_string())
    };

    let available = final_path.is_some();

    // 3. Check Version if available
    let mut version = None;
    if let Some(ref p) = final_path {
        if let Ok(output) = new_silent_command(p).arg(version_flag).output() {
             if output.status.success() {
                 let out_str = String::from_utf8_lossy(&output.stdout).to_string();
                 let first_line = out_str.lines().next().unwrap_or("").trim().to_string();
                 version = Some(first_line);
             }
        }
    }

    DependencyInfo {
        name: bin_name.to_string(),
        available,
        version,
        path: final_path
    }
}

#[tauri::command]
pub async fn check_dependencies(app_handle: AppHandle) -> AppDependencies {
    let app_dir = app_handle.path_resolver().app_data_dir().unwrap();
    let bin_dir = app_dir.join("bin");

    tauri::async_runtime::spawn_blocking(move || {
        let bin_path = bin_dir;

        // 1. yt-dlp
        let exec_name = if cfg!(windows) { "yt-dlp.exe" } else { "yt-dlp" };
        let yt_dlp = resolve_binary_info(exec_name, "--version", &bin_path);

        // 2. ffmpeg
        let exec_name = if cfg!(windows) { "ffmpeg.exe" } else { "ffmpeg" };
        let mut ffmpeg = resolve_binary_info(exec_name, "-version", &bin_path);
        if let Some(ref v) = ffmpeg.version {
            let re = Regex::new(r"ffmpeg version ([^\s]+)").unwrap();
            if let Some(caps) = re.captures(v) {
                ffmpeg.version = Some(caps[1].to_string());
            }
        }

        // 3. JS Runtime
        let mut js_runtime = DependencyInfo { 
            name: "None".to_string(), available: false, version: None, path: None 
        };

        // Check local deno first
        let deno_exec = if cfg!(windows) { "deno.exe" } else { "deno" };
        let local_deno = resolve_binary_info(deno_exec, "--version", &bin_path);

        if local_deno.available {
            js_runtime = local_deno;
            js_runtime.name = "deno".to_string();
        } else {
            // Fallback to system
            let runtimes = [("deno", "--version"), ("node", "--version"), ("bun", "--version")];
            for (bin, flag) in runtimes {
                let info = resolve_binary_info(bin, flag, &bin_path); // path check is redundant but safe
                if info.available {
                    js_runtime = info;
                    break;
                }
            }
        }
        
        if js_runtime.name.contains("deno") {
             if let Some(ref v) = js_runtime.version {
                 js_runtime.version = Some(v.replace("deno ", ""));
             }
        }

        AppDependencies {
            yt_dlp,
            ffmpeg,
            js_runtime,
        }
    })
    .await
    .unwrap()
}

#[tauri::command]
pub async fn install_dependency(app_handle: AppHandle, name: String) -> Result<(), String> {
    deps::install_dep(name, app_handle).await
}

#[tauri::command]
pub async fn sync_dependencies(app_handle: AppHandle) -> Result<AppDependencies, String> {
    let app_dir = app_handle.path_resolver().app_data_dir().ok_or("Failed to get app dir")?;
    let bin_dir = app_dir.join("bin");

    if !bin_dir.exists() {
        std::fs::create_dir_all(&bin_dir).map_err(|e| e.to_string())?;
    }

    deps::auto_update_yt_dlp(app_handle.clone(), bin_dir.clone()).await?;
    deps::install_missing_ffmpeg(app_handle.clone(), bin_dir.clone()).await?;
    deps::manage_js_runtime(app_handle.clone(), bin_dir.clone()).await?;

    Ok(check_dependencies(app_handle).await)
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

// NEW: App Update Check
#[tauri::command]
pub async fn get_latest_app_version() -> Result<String, String> {
    deps::get_latest_github_tag("zqily/multiyt-dlp").await
}