// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::{Arc, Mutex};
use tauri::{Manager, WindowEvent};
use crate::core::manager::JobManager;
use crate::config::ConfigManager;

mod commands;
mod core;
mod models;
mod config;

fn main() {
    let job_manager = Arc::new(Mutex::new(JobManager::new()));
    let config_manager = Arc::new(ConfigManager::new());

    // Clone for setup closure
    let config_manager_setup = config_manager.clone();
    // Clone for window event closure
    let config_manager_event = config_manager.clone();

    tauri::Builder::default()
        .manage(job_manager)
        .manage(config_manager) // Register state
        .setup(move |app| {
            let main_window = app.get_window("main").unwrap();
            let config = config_manager_setup.get_config();
            
            // Apply saved window state
            let _ = main_window.set_size(tauri::Size::Physical(tauri::PhysicalSize {
                width: config.window.width as u32,
                height: config.window.height as u32,
            }));
            let _ = main_window.set_position(tauri::Position::Physical(tauri::PhysicalPosition {
                x: config.window.x as i32,
                y: config.window.y as i32,
            }));
            
            // Note: We don't show main window here. It stays hidden until Splash invokes close_splash

            Ok(())
        })
        .on_window_event(move |event| {
            if let WindowEvent::Moved(pos) = event.event() {
                let mut current_config = config_manager_event.get_config();
                current_config.window.x = pos.x as f64;
                current_config.window.y = pos.y as f64;
                config_manager_event.update_window(current_config.window);
                let _ = config_manager_event.save();
            }
            if let WindowEvent::Resized(size) = event.event() {
                // Ignore 0x0 resizes (can happen on minimize on Windows)
                if size.width > 0 && size.height > 0 {
                    let mut current_config = config_manager_event.get_config();
                    current_config.window.width = size.width as f64;
                    current_config.window.height = size.height as f64;
                    config_manager_event.update_window(current_config.window);
                    let _ = config_manager_event.save();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            commands::system::check_dependencies,
            commands::system::open_external_link,
            commands::system::close_splash, // Added here
            commands::downloader::start_download,
            commands::downloader::cancel_download,
            commands::config::get_app_config,
            commands::config::save_general_config,
            commands::config::save_preference_config,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}