use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Manager};
use uuid::Uuid;
use crate::{models::{Job, JobStatus, QueuedJob}, core::error::AppError, config::ConfigManager};
use crate::core::process::run_download_process;

pub struct JobManager {
    jobs: HashMap<Uuid, Job>,
    queue: VecDeque<QueuedJob>,
    
    // Concurrency Counters
    active_network_jobs: u32,
    active_process_instances: u32,
}

impl JobManager {
    pub fn new() -> Self {
        Self {
            jobs: HashMap::new(),
            queue: VecDeque::new(),
            active_network_jobs: 0,
            active_process_instances: 0,
        }
    }

    // Adds a job to the registry and queues it
    pub fn add_job(&mut self, job_data: QueuedJob, app_handle: AppHandle) -> Result<(), AppError> {
        if self.jobs.values().any(|j| j.url == job_data.url) {
            return Err(AppError::JobAlreadyExists);
        }

        let job = Job::new(job_data.url.clone());
        self.jobs.insert(job_data.id, job);
        self.queue.push_back(job_data);

        // Attempt to start jobs immediately if slots are open
        self.process_queue(app_handle);
        
        Ok(())
    }

    // Called whenever a slot might open up (add_job, network_finished, process_finished)
    pub fn process_queue(&mut self, app_handle: AppHandle) {
        // Retrieve limits from config
        // Note: In a real high-perf scenario, we might cache these, but here it's safer to read fresh
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
            println!("Instance slot released. Total Instances: {}", self.active_process_instances);
            self.process_queue(app_handle);
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
    }
}