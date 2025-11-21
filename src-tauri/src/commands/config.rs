use tauri::State;
use std::sync::Arc;
use crate::config::{AppConfig, ConfigManager, GeneralConfig, PreferenceConfig};

#[tauri::command]
pub fn get_app_config(config_manager: State<'_, Arc<ConfigManager>>) -> AppConfig {
    config_manager.get_config()
}

#[tauri::command]
pub fn save_general_config(
    config_manager: State<'_, Arc<ConfigManager>>,
    config: GeneralConfig
) -> Result<(), String> {
    config_manager.update_general(config);
    config_manager.save()
}

#[tauri::command]
pub fn save_preference_config(
    config_manager: State<'_, Arc<ConfigManager>>,
    config: PreferenceConfig
) -> Result<(), String> {
    config_manager.update_preferences(config);
    config_manager.save()
}