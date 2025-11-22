use std::fs;
use tracing::{info};
use tracing_subscriber::{
    fmt, 
    prelude::*, 
    reload, 
    Registry, 
    EnvFilter
};
use tracing_appender::non_blocking::WorkerGuard;

// We need to define the Handle type specifically to store it in the struct
// Generic params: <FilterType, RegistryType>
pub type LogHandle = reload::Handle<EnvFilter, Registry>;

pub struct LogManager {
    // We must keep the guard alive, otherwise file logging stops immediately
    _guard: WorkerGuard,
    // The handle allows us to swap the filter (log level) at runtime
    reload_handle: LogHandle,
}

impl LogManager {
    pub fn init(log_level: &str) -> Self {
        // 1. Determine Log Directory
        // In a real scenario, we might use tauri::api::path, but since this is init,
        // we'll use the dirs crate to find a standard location.
        let home = dirs::home_dir().expect("Could not find home directory");
        let log_dir = home.join(".multiyt-dlp").join("logs");
        
        if !log_dir.exists() {
            let _ = fs::create_dir_all(&log_dir);
        }

        // 2. File Appender (Rolling Daily)
        let file_appender = tracing_appender::rolling::daily(&log_dir, "app.log");
        let (non_blocking, guard) = tracing_appender::non_blocking(file_appender);

        // 3. Layers
        
        // Layer A: JSON File Output
        let file_layer = fmt::layer()
            .json()
            .with_writer(non_blocking)
            .with_target(true)
            .with_file(true)
            .with_line_number(true);

        // Layer B: Pretty Console Output
        let stdout_layer = fmt::layer()
            .pretty()
            .with_writer(std::io::stdout);

        // 4. Filter (Reloadable)
        // We wrap the EnvFilter in a reload layer.
        // This filter will apply to ALL layers (global toggle).
        let initial_filter = EnvFilter::try_new(log_level)
            .unwrap_or_else(|_| EnvFilter::new("info"));
            
        let (filter_layer, reload_handle) = reload::Layer::new(initial_filter);

        // 5. Registry Construction
        tracing_subscriber::registry()
            .with(filter_layer) // Apply filter first
            .with(file_layer)
            .with(stdout_layer)
            .init();

        info!("Logging initialized at level: {}", log_level);
        info!("Log directory: {:?}", log_dir);

        Self {
            _guard: guard,
            reload_handle,
        }
    }

    pub fn set_level(&self, level: &str) -> Result<(), String> {
        let new_filter = EnvFilter::try_new(level)
            .map_err(|e| format!("Invalid log level '{}': {}", level, e))?;
        
        self.reload_handle.reload(new_filter)
            .map_err(|e| format!("Failed to reload log level: {}", e))?;
            
        info!("Log level dynamically changed to: {}", level);
        Ok(())
    }
}