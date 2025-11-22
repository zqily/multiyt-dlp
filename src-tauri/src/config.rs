use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;

// --- Configuration Structs ---

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct WindowConfig {
    pub width: f64,
    pub height: f64,
    pub x: f64,
    pub y: f64,
}

impl Default for WindowConfig {
    fn default() -> Self {
        Self {
            width: 1200.0,
            height: 800.0,
            x: 100.0,
            y: 100.0,
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GeneralConfig {
    pub download_path: Option<String>,
    pub filename_template: String,
    pub template_blocks_json: Option<String>,
    pub max_concurrent_downloads: u32,
    pub max_total_instances: u32,
    // NEW: Log Level
    pub log_level: String, 
}

impl Default for GeneralConfig {
    fn default() -> Self {
        Self {
            download_path: None, 
            filename_template: "%(title)s.%(ext)s".to_string(),
            template_blocks_json: None,
            max_concurrent_downloads: 4,
            max_total_instances: 10,
            log_level: "info".to_string(),
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PreferenceConfig {
    pub mode: String,
    pub format_preset: String,
    pub video_resolution: String, 
    pub embed_metadata: bool,
    pub embed_thumbnail: bool,
}

impl Default for PreferenceConfig {
    fn default() -> Self {
        Self {
            mode: "video".to_string(),
            format_preset: "best".to_string(),
            video_resolution: "best".to_string(),
            embed_metadata: false,
            embed_thumbnail: false,
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AppConfig {
    pub general: GeneralConfig,
    pub preferences: PreferenceConfig,
    pub window: WindowConfig,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            general: GeneralConfig::default(),
            preferences: PreferenceConfig::default(),
            window: WindowConfig::default(),
        }
    }
}

// --- Manager ---

pub struct ConfigManager {
    config: Mutex<AppConfig>,
    file_path: PathBuf,
}

impl ConfigManager {
    pub fn new() -> Self {
        let home = dirs::home_dir().expect("Could not find home directory");
        let config_dir = home.join(".multiyt-dlp");
        let file_path = config_dir.join("config.json");

        if !config_dir.exists() {
            let _ = fs::create_dir_all(&config_dir);
        }

        let config = Self::load_from_disk(&file_path).unwrap_or_default();

        Self {
            config: Mutex::new(config),
            file_path,
        }
    }

    fn load_from_disk(path: &PathBuf) -> Option<AppConfig> {
        if !path.exists() {
            return None;
        }

        let content = fs::read_to_string(path).ok()?;
        match serde_json::from_str::<AppConfig>(&content) {
            Ok(cfg) => Some(cfg),
            Err(e) => {
                println!("Error parsing config.json: {}. Using defaults.", e);
                let _ = fs::rename(path, path.with_extension("json.bak"));
                None
            }
        }
    }

    pub fn save(&self) -> Result<(), String> {
        let config = self.config.lock().unwrap();
        let json = serde_json::to_string_pretty(&*config)
            .map_err(|e| format!("Serialization error: {}", e))?;
        
        fs::write(&self.file_path, json)
            .map_err(|e| format!("Failed to write config file: {}", e))
    }

    pub fn get_config(&self) -> AppConfig {
        self.config.lock().unwrap().clone()
    }

    pub fn update_general(&self, general: GeneralConfig) {
        let mut cfg = self.config.lock().unwrap();
        cfg.general = general;
    }

    pub fn update_preferences(&self, prefs: PreferenceConfig) {
        let mut cfg = self.config.lock().unwrap();
        cfg.preferences = prefs;
    }

    pub fn update_window(&self, window: WindowConfig) {
        let mut cfg = self.config.lock().unwrap();
        cfg.window = window;
    }
}