"""
Main entry point for the Multiyt-dlp application.

This script initializes the configuration, sets up logging, creates the main
Tkinter window, and starts the application event loop.
"""

import tkinter as tk
import queue
import sys
import logging
from types import TracebackType
from typing import Type

from src.gui import YTDlpDownloaderApp
from src.logging_config import setup_logging
from src.config import ConfigManager
from src.constants import CONFIG_FILE, TEMP_DOWNLOAD_DIR

def handle_exception(exc_type: Type[BaseException], exc_value: BaseException, exc_traceback: TracebackType):
    """
    Logs unhandled exceptions.

    This function is set as the global exception hook to ensure that any
    uncaught exceptions are logged before the application terminates.

    Args:
        exc_type: The type of the exception.
        exc_value: The exception instance.
        exc_traceback: The traceback object.
    """
    logger = logging.getLogger()
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback))

if __name__ == "__main__":
    """
    Main entry point for the application.
    """
    # 1. Ensure temp directory exists before anything else
    TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Load configuration before setting up logging
    gui_queue = queue.Queue()
    config_manager = ConfigManager(CONFIG_FILE)
    config = config_manager.load()

    # 3. Use the configured log level for file logging
    setup_logging(gui_queue, config.log_level)

    # 4. Set up global exception handler
    sys.excepthook = handle_exception

    # 5. Create and run the Tkinter application
    root = tk.Tk()
    app = YTDlpDownloaderApp(root, gui_queue, config_manager, config)
    root.mainloop()