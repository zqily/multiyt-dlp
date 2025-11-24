use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Manager};
use uuid::Uuid;
use std::fs;
use std::path::PathBuf;
use crate::{models::{Job, JobStatus, QueuedJob}, core::error::AppError, config::ConfigManager};
use crate::core::process::run_download_process;
use crate::core::native;

pub struct JobManager {
    // Runtime State
    jobs: HashMap<Uuid, Job>,
    queue: VecDeque<QueuedJob>,
    
    // Persistence Registry: Keeps track of the config for ALL active/queued jobs
    // This is what gets saved to jobs.json
    persistence_registry: HashMap<Uuid, QueuedJob>,

    // Concurrency Counters
    active_network_jobs: u32,
    active_process_instances: u32,

    // Session Stats
    completed_session_count: u32,
}

impl JobManager {
    pub fn new() -> Self {
        Self {
            jobs: HashMap::new(),
            queue: VecDeque::new(),
            persistence_registry: HashMap::new(),
            active_network_jobs: 0,
            active_process_instances: 0,
            completed_session_count: 0,
        }
    }

    fn get_persistence_path() -> PathBuf {
        let home = dirs::home_dir().expect("Could not find home directory");
        home.join(".multiyt-dlp").join("jobs.json")
    }

    fn save_state(&self) {
        let path = Self::get_persistence_path();
        // Convert registry values to a vector for saving
        let jobs: Vec<&QueuedJob> = self.persistence_registry.values().collect();
        
        if let Ok(json) = serde_json::to_string_pretty(&jobs) {
             let _ = fs::write(path, json);
        }
    }

    // Adds a job to the registry and queues it
    pub fn add_job(&mut self, job_data: QueuedJob, app_handle: AppHandle) -> Result<(), AppError> {
        if self.jobs.values().any(|j| j.url == job_data.url) {
            return Err(AppError::JobAlreadyExists);
        }

        let job = Job::new(job_data.url.clone());
        self.jobs.insert(job_data.id, job);
        
        // Add to persistence registry and Save
        self.persistence_registry.insert(job_data.id, job_data.clone());
        self.save_state();

        self.queue.push_back(job_data);

        // Update UI (Taskbar should show something if new items added)
        self.update_native_ui(&app_handle);

        // Attempt to start jobs immediately if slots are open
        self.process_queue(app_handle);
        
        Ok(())
    }

    // Called whenever a slot might open up (add_job, network_finished, process_finished)
    pub fn process_queue(&mut self, app_handle: AppHandle) {
        // Retrieve limits from config
        let config_manager = app_handle.state::<Arc<ConfigManager>>();
        let config = config_manager.get_config().general;

        while self.active_network_jobs < config.max_concurrent_downloads 
           && self.active_process_instances < config.max_total_instances 
        {
            if let Some(next_job) = self.queue.pop_front() {
                // Double check status hasn't been cancelled while in queue
                if let Some(job) = self.jobs.get(&next_job.id) {
                     if job.status == JobStatus::Cancelled {
                         continue;
                     }
                }

                self.active_network_jobs += 1;
                self.active_process_instances += 1;

                // Spawn the job
                let manager_state = app_handle.state::<Arc<Mutex<JobManager>>>().inner().clone();
                let job_id = next_job.id;
                
                let app_handle_clone = app_handle.clone();
                
                tokio::spawn(async move {
                    run_download_process(
                        next_job, 
                        app_handle_clone, 
                        manager_state
                    ).await;
                });
                
                println!("Started Job {}. Active Network: {}, Total Instances: {}", job_id, self.active_network_jobs, self.active_process_instances);

            } else {
                break; // Queue empty
            }
        }
    }

    // --- State Callbacks from Process ---

    pub fn notify_network_finished(&mut self, app_handle: AppHandle) {
        if self.active_network_jobs > 0 {
            self.active_network_jobs -= 1;
            println!("Network slot released. Active Network: {}", self.active_network_jobs);
            self.process_queue(app_handle);
        }
    }

    pub fn notify_process_finished(&mut self, app_handle: AppHandle) {
        if self.active_process_instances > 0 {
            self.active_process_instances -= 1;
            self.completed_session_count += 1;

            println!("Instance slot released. Total Instances: {}", self.active_process_instances);
            
            // Native UI Update: If we hit 0 instances, queue is done.
            if self.active_process_instances == 0 {
                self.trigger_finished_notification(&app_handle);
            }

            self.process_queue(app_handle.clone());
            self.update_native_ui(&app_handle);

            // Auto-cleanup Temp Directory if completely idle AND queue is empty
            if self.active_process_instances == 0 && self.queue.is_empty() {
                // Only clean if persistence is empty too (fully done or cleared)
                if self.persistence_registry.is_empty() {
                     self.clean_temp_directory();
                }
            }
        }
    }

    pub fn clean_temp_directory(&self) {
        let home = dirs::home_dir().unwrap_or_else(|| std::path::PathBuf::from("."));
        let temp_dir = home.join(".multiyt-dlp").join("temp_downloads");
        
        if temp_dir.exists() {
            println!("Cleaning temp directory: {:?}", temp_dir);
            if let Ok(entries) = fs::read_dir(&temp_dir) {
                for entry in entries {
                    if let Ok(entry) = entry {
                        let path = entry.path();
                        if path.is_dir() {
                            let _ = fs::remove_dir_all(path);
                        } else {
                            let _ = fs::remove_file(path);
                        }
                    }
                }
            }
        }
    }

    // --- Standard Getters/Setters ---

    pub fn get_job_pid(&self, id: Uuid) -> Option<u32> {
        self.jobs.get(&id).and_then(|job| job.pid)
    }

    pub fn get_job_status(&self, id: Uuid) -> Option<JobStatus> {
        self.jobs.get(&id).map(|job| job.status.clone())
    }

    pub fn update_job_pid(&mut self, id: Uuid, pid: u32) -> Result<(), AppError> {
        if let Some(job) = self.jobs.get_mut(&id) {
            job.pid = Some(pid);
            Ok(())
        } else {
            Err(AppError::JobNotFound)
        }
    }
    
    pub fn update_job_status(&mut self, id: Uuid, status: JobStatus) -> Result<(), AppError> {
        if let Some(job) = self.jobs.get_mut(&id) {
            job.status = status;
            Ok(())
        } else {
            Err(AppError::JobNotFound)
        }
    }

    pub fn remove_job(&mut self, id: Uuid) {
        self.jobs.remove(&id);
        // Also remove from persistence and save
        self.persistence_registry.remove(&id);
        self.save_state();
    }

    // --- Native UI Logic ---

    pub fn update_job_progress(&mut self, id: Uuid, progress: f32, app_handle: &AppHandle) {
        if let Some(job) = self.jobs.get_mut(&id) {
            job.progress = progress;
        }
        self.update_native_ui(app_handle);
    }

    fn update_native_ui(&self, app_handle: &AppHandle) {
        let active_jobs: Vec<&Job> = self.jobs.values()
            .filter(|j| j.status == JobStatus::Downloading || j.status == JobStatus::Pending)
            .collect();
        
        let active_count = active_jobs.len();

        if active_count == 0 {
            native::clear_taskbar_progress(app_handle);
            return;
        }

        let total_progress: f32 = active_jobs.iter().map(|j| j.progress).sum();
        let aggregated = total_progress / (active_count as f32);
        
        // Check for any errors in the current batch to tint the bar red
        let has_error = self.jobs.values().any(|j| j.status == JobStatus::Error);

        // Run on main thread to be safe with OS calls
        let app_for_thread = app_handle.clone(); // FIX: Clone dedicated handle for closure
        
        let _ = app_handle.run_on_main_thread(move || {
            native::set_taskbar_progress(&app_for_thread, (aggregated / 100.0) as f64, has_error);
        });
    }

    fn trigger_finished_notification(&mut self, app_handle: &AppHandle) {
        use tauri::api::notification::Notification;

        let count = self.completed_session_count;
        if count == 0 { return; } // Don't notify if nothing happened

        let title = "Downloads Finished";
        let body = format!("Queue processed. {} files handled.", count);
        
        let _ = Notification::new(app_handle.config().tauri.bundle.identifier.clone())
            .title(title)
            .body(body)
            .icon("icons/128x128.png") 
            .show();

        // Reset session count
        self.completed_session_count = 0;
    }
}