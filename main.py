"""
Main entry point for the Multiyt-dlp application.

This script initializes the configuration, sets up logging, creates the main
Tkinter window, and starts the application event loop.
"""

import tkinter as tk
import queue
import sys
import logging
import asyncio
from types import TracebackType
from typing import Type

from src.gui import YTDlpDownloaderApp
from src.logging_config import setup_logging
from src.config import ConfigManager
from src.constants import CONFIG_FILE, TEMP_DOWNLOAD_DIR
from src.controller import AppController

def handle_exception(exc_type: Type[BaseException], exc_value: BaseException, exc_traceback: TracebackType):
    """Logs unhandled exceptions from synchronous code."""
    logger = logging.getLogger()
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback))

def handle_async_exception(loop, context):
    """Logs unhandled exceptions from asyncio tasks."""
    logger = logging.getLogger()
    msg = context.get("exception", context["message"])
    logger.critical(f"Caught exception from asyncio task: {msg}", exc_info=context.get('exception'))


if __name__ == "__main__":
    """
    Main entry point for the application.
    """
    # 1. Ensure temp directory exists before anything else
    TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Load configuration before setting up logging
    gui_queue = queue.Queue() # Kept for the logging QueueHandler
    config_manager = ConfigManager(CONFIG_FILE)
    config = config_manager.load()

    # 3. Use the configured log level for file logging
    setup_logging(gui_queue, config.log_level)

    # 4. Set up global exception handlers
    sys.excepthook = handle_exception
    
    # Get the asyncio event loop and set its exception handler
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(handle_async_exception)

    # 5. Create the Controller, which holds all business logic
    controller = AppController(config_manager, config)

    # 6. Create the Tkinter application (the View)
    root = tk.Tk()
    app = YTDlpDownloaderApp(root, gui_queue, controller, config, loop)

    # 7. Start the Tkinter main loop. The GUI class now drives the asyncio loop.
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logging.info("Application interrupted by user.")