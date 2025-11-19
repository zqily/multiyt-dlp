use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct UserSettings {
    pub download_path: Option<String>,
    pub max_concurrent_downloads: u32,
}

impl Default for UserSettings {
    fn default() -> Self {
        Self {
            download_path: None, // None means use default downloads folder
            max_concurrent_downloads: 3,
        }
    }
}

// In a real application, you would add functions here to load/save settings from a file.
// For example, using the `tauri-plugin-store` or manually writing to the app's config directory.
