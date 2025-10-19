import os
import sys
import queue
import logging
import logging.handlers
from datetime import datetime

from .constants import LOG_DIR

def setup_logging(gui_queue: queue.Queue, file_log_level_str: str = 'INFO'):
    """
    Configures the root logger for file and GUI logging.
    Implements a "Minecraft-style" log rotation.
    """
    # 1. Ensure Log Directory Exists
    os.makedirs(LOG_DIR, exist_ok=True)

    # 2. Implement Log Rotation
    latest_log_path = os.path.join(LOG_DIR, 'latest.log')
    if os.path.exists(latest_log_path):
        try:
            # Get modification time and format it
            mod_time = os.path.getmtime(latest_log_path)
            timestamp_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d_%H-%M-%S')
            
            # Construct archive path and rename
            archive_log_path = os.path.join(LOG_DIR, f"{timestamp_str}.log")
            os.rename(latest_log_path, archive_log_path)
        except OSError as e:
            # Use a basic print to stderr if logging is not yet available
            print(f"Error rotating log file: {e}", file=sys.stderr)

    # 3. Configure Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG) # Capture all levels of messages at the root

    # Clear any existing handlers to avoid duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 4. Define a Formatter
    log_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)-8s - %(name)-25s - %(message)s'
    )

    # 5. Configure File Handler (for latest.log)
    # Convert string level to logging constant; default to INFO if invalid
    file_log_level = getattr(logging, file_log_level_str.upper(), logging.INFO)
    
    file_handler = logging.FileHandler(latest_log_path, encoding='utf-8')
    file_handler.setLevel(file_log_level) # Log at the configured level to the file
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)

    # 6. Configure GUI Queue Handler
    # QueueHandler does not need a formatter, as it passes the raw LogRecord
    # to the queue for the GUI thread to format.
    queue_handler = logging.handlers.QueueHandler(gui_queue)
    queue_handler.setLevel(logging.INFO) # Only show INFO and above in the GUI
    root_logger.addHandler(queue_handler)

    logging.info("--- Logging initialized ---")
    logging.debug(f"File log level set to: {logging.getLevelName(file_log_level)}")