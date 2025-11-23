use std::fs::{self, File};
use std::io::Write;
use std::path::PathBuf;
use tauri::{AppHandle, Manager};
use futures_util::StreamExt;
use serde::Serialize;
use reqwest::Client;
use async_trait::async_trait;

// --- Constants ---

#[cfg(target_os = "windows")]
const YT_DLP_URL: &str = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe";
#[cfg(target_os = "macos")]
const YT_DLP_URL: &str = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos";
#[cfg(target_os = "linux")]
const YT_DLP_URL: &str = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux";

#[cfg(target_os = "windows")]
const FFMPEG_URL: &str = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip";
#[cfg(target_os = "macos")]
const FFMPEG_URL: &str = "https://evermeet.cx/ffmpeg/ffmpeg-113374-g80f9281204.zip"; 
#[cfg(target_os = "linux")]
const FFMPEG_URL: &str = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz";

#[cfg(target_os = "windows")]
const DENO_URL: &str = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip";
#[cfg(target_os = "macos")]
const DENO_URL: &str = "https://github.com/denoland/deno/releases/latest/download/deno-aarch64-apple-darwin.zip"; 
#[cfg(target_os = "linux")]
const DENO_URL: &str = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip";


// --- Types ---

#[derive(Clone, Serialize)]
struct InstallProgressPayload {
    name: String,
    percentage: u64,
    status: String,
}

#[async_trait]
pub trait DependencyProvider: Send + Sync {
    fn get_name(&self) -> String;
    fn get_binaries(&self) -> Vec<&str>;
    async fn install(&self, app_handle: AppHandle, target_dir: PathBuf) -> Result<(), String>;
}

// --- Downloader Helper ---

async fn download_file(url: &str, dest: &PathBuf, name: &str, app_handle: &AppHandle) -> Result<(), String> {
    let client = Client::new();
    let res = client.get(url).send().await.map_err(|e| e.to_string())?;
    
    let total_size = res.content_length().unwrap_or(0);
    let mut file = File::create(dest).map_err(|e| e.to_string())?;
    let mut stream = res.bytes_stream();
    let mut downloaded: u64 = 0;

    // Throttle event emission to avoid flooding the frontend channel
    let mut last_emit = 0;

    while let Some(item) = stream.next().await {
        let chunk = item.map_err(|e| e.to_string())?;
        file.write_all(&chunk).map_err(|e| e.to_string())?;
        downloaded += chunk.len() as u64;

        if total_size > 0 {
            let percentage = (downloaded * 100) / total_size;
            if percentage > last_emit + 1 || percentage == 100 {
                last_emit = percentage;
                let _ = app_handle.emit_all("install-progress", InstallProgressPayload {
                    name: name.to_string(),
                    percentage,
                    status: "Downloading...".to_string()
                });
            }
        }
    }

    Ok(())
}

// --- Extraction Helpers ---

fn extract_zip_finding_binary(zip_path: &PathBuf, target_dir: &PathBuf, binary_names: &[&str]) -> Result<(), String> {
    let file = File::open(zip_path).map_err(|e| e.to_string())?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| e.to_string())?;

    for i in 0..archive.len() {
        let mut file = archive.by_index(i).map_err(|e| e.to_string())?;
        let outpath = match file.enclosed_name() {
            Some(path) => path.to_owned(),
            None => continue,
        };

        if let Some(file_name) = outpath.file_name() {
            let file_name_str = file_name.to_string_lossy();
            if binary_names.contains(&file_name_str.as_ref()) {
                let mut out_file = File::create(target_dir.join(file_name)).map_err(|e| e.to_string())?;
                std::io::copy(&mut file, &mut out_file).map_err(|e| e.to_string())?;
                
                #[cfg(unix)]
                {
                    use std::os::unix::fs::PermissionsExt;
                    let mut perms = out_file.metadata().map_err(|e| e.to_string())?.permissions();
                    perms.set_mode(0o755);
                    out_file.set_permissions(perms).map_err(|e| e.to_string())?;
                }
            }
        }
    }
    Ok(())
}

fn extract_tar_xz_finding_binary(tar_path: &PathBuf, target_dir: &PathBuf, binary_names: &[&str]) -> Result<(), String> {
    let tar_gz = File::open(tar_path).map_err(|e| e.to_string())?;
    let tar = xz2::read::XzDecoder::new(tar_gz);
    let mut archive = tar::Archive::new(tar);

    for entry in archive.entries().map_err(|e| e.to_string())? {
        let mut entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path().map_err(|e| e.to_string())?.into_owned();
        
        if let Some(file_name) = path.file_name() {
            let file_name_str = file_name.to_string_lossy();
            if binary_names.contains(&file_name_str.as_ref()) {
                entry.unpack(target_dir.join(file_name)).map_err(|e| e.to_string())?;
            }
        }
    }
    Ok(())
}


// --- Providers ---

pub struct YtDlpProvider;
#[async_trait]
impl DependencyProvider for YtDlpProvider {
    fn get_name(&self) -> String { "yt-dlp".to_string() }
    fn get_binaries(&self) -> Vec<&str> {
        if cfg!(windows) { vec!["yt-dlp.exe"] } else { vec!["yt-dlp"] }
    }
    async fn install(&self, app_handle: AppHandle, target_dir: PathBuf) -> Result<(), String> {
        let filename = self.get_binaries()[0];
        let target_path = target_dir.join(filename);
        
        download_file(YT_DLP_URL, &target_path, "yt-dlp", &app_handle).await?;
        
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut perms = fs::metadata(&target_path).map_err(|e| e.to_string())?.permissions();
            perms.set_mode(0o755);
            fs::set_permissions(&target_path, perms).map_err(|e| e.to_string())?;
        }

        Ok(())
    }
}

pub struct FfmpegProvider;
#[async_trait]
impl DependencyProvider for FfmpegProvider {
    fn get_name(&self) -> String { "ffmpeg".to_string() }
    fn get_binaries(&self) -> Vec<&str> {
        if cfg!(windows) { vec!["ffmpeg.exe", "ffprobe.exe"] } else { vec!["ffmpeg", "ffprobe"] }
    }
    async fn install(&self, app_handle: AppHandle, target_dir: PathBuf) -> Result<(), String> {
        let archive_name = if cfg!(windows) || cfg!(target_os = "macos") { "ffmpeg.zip" } else { "ffmpeg.tar.xz" };
        let temp_dir = std::env::temp_dir();
        let archive_path = temp_dir.join(archive_name);

        download_file(FFMPEG_URL, &archive_path, "ffmpeg", &app_handle).await?;

        let _ = app_handle.emit_all("install-progress", InstallProgressPayload {
            name: "ffmpeg".to_string(), percentage: 100, status: "Extracting...".to_string()
        });

        if archive_path.extension().unwrap_or_default() == "zip" {
            extract_zip_finding_binary(&archive_path, &target_dir, &self.get_binaries())?;
        } else {
            extract_tar_xz_finding_binary(&archive_path, &target_dir, &self.get_binaries())?;
        }

        let _ = fs::remove_file(archive_path);
        Ok(())
    }
}

pub struct DenoProvider;
#[async_trait]
impl DependencyProvider for DenoProvider {
    fn get_name(&self) -> String { "js_runtime".to_string() }
    fn get_binaries(&self) -> Vec<&str> {
        if cfg!(windows) { vec!["deno.exe"] } else { vec!["deno"] }
    }
    async fn install(&self, app_handle: AppHandle, target_dir: PathBuf) -> Result<(), String> {
        let archive_path = std::env::temp_dir().join("deno.zip");

        download_file(DENO_URL, &archive_path, "js_runtime", &app_handle).await?;

        let _ = app_handle.emit_all("install-progress", InstallProgressPayload {
            name: "js_runtime".to_string(), percentage: 100, status: "Extracting...".to_string()
        });

        extract_zip_finding_binary(&archive_path, &target_dir, &self.get_binaries())?;
        let _ = fs::remove_file(archive_path);
        Ok(())
    }
}

// --- Factory ---

pub fn get_provider(name: &str) -> Option<Box<dyn DependencyProvider>> {
    match name {
        "yt-dlp" => Some(Box::new(YtDlpProvider)),
        "ffmpeg" => Some(Box::new(FfmpegProvider)),
        "js_runtime" => Some(Box::new(DenoProvider)),
        _ => None
    }
}

// --- Manager Logic ---

pub async fn install_dep(name: String, app_handle: AppHandle) -> Result<(), String> {
    let provider = get_provider(&name).ok_or("Unknown dependency")?;
    
    let app_dir = app_handle.path_resolver().app_data_dir().ok_or("Failed to resolve app data dir")?;
    let bin_dir = app_dir.join("bin");
    
    if !bin_dir.exists() {
        fs::create_dir_all(&bin_dir).map_err(|e| e.to_string())?;
    }

    provider.install(app_handle.clone(), bin_dir).await?;

    let _ = app_handle.emit_all("install-progress", InstallProgressPayload {
        name: name, percentage: 100, status: "Installed".to_string()
    });

    Ok(())
}