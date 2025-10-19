import tkinter as tk
import queue
import sys
import logging
import os
from src.gui import YTDlpDownloaderApp
from src.logging_config import setup_logging
from src.config import ConfigManager
from src.constants import CONFIG_FILE, TEMP_DOWNLOAD_DIR

def handle_exception(exc_type, exc_value, exc_traceback):
    """Logs unhandled exceptions."""
    logger = logging.getLogger()
    # Don't log KeyboardInterrupt, let the system handle it
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback))

if __name__ == "__main__":
    """
    Main entry point for the application.
    """
    # Ensure temp directory exists before anything else
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
    
    # Load configuration before setting up logging
    gui_queue = queue.Queue()
    config_manager = ConfigManager(CONFIG_FILE)
    config = config_manager.load()
    
    # Use the configured log level for file logging
    file_log_level = config.get('log_level', 'INFO')
    setup_logging(gui_queue, file_log_level)
    
    sys.excepthook = handle_exception
    
    root = tk.Tk()
    # Pass the loaded config and manager to the app to avoid reloading
    app = YTDlpDownloaderApp(root, gui_queue, config_manager, config)
    root.mainloop()