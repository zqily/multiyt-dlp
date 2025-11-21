// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::{Arc, Mutex};
use crate::core::manager::JobManager;

mod commands;
mod core;
mod models;
mod config;

fn main() {
    let job_manager = Arc::new(Mutex::new(JobManager::new()));

    tauri::Builder::default()
        .manage(job_manager)
        .invoke_handler(tauri::generate_handler![
            commands::system::check_dependencies,
            commands::system::open_external_link,
            commands::downloader::start_download,
            commands::downloader::cancel_download
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}