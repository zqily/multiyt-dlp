use std::collections::HashMap;
use uuid::Uuid;
use crate::{models::Job, core::error::AppError};

#[derive(Default)]
pub struct JobManager {
    jobs: HashMap<Uuid, Job>,
}

impl JobManager {
    pub fn new() -> Self {
        Self {
            jobs: HashMap::new(),
        }
    }

    pub fn add_job(&mut self, id: Uuid, job: Job) -> Result<(), AppError> {
        if self.jobs.values().any(|j| j.url == job.url) {
            return Err(AppError::JobAlreadyExists);
        }
        self.jobs.insert(id, job);
        Ok(())
    }

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
    
    pub fn update_job_status(&mut self, id: Uuid, status: crate::models::JobStatus) -> Result<(), AppError> {
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

pub use crate::models::JobStatus;
