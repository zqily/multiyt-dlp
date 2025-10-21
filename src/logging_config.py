"""
Configures the application's logging setup.

This module sets up a root logger that directs messages to both a rotating
file log and a queue for display in the GUI.
"""

import sys
import queue
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

from .constants import LOG_DIR

def setup_logging(gui_queue: queue.Queue, file_log_level_str: str = 'INFO'):
    """
    Configures the root logger for file and GUI logging.

    Implements a "Minecraft-style" log rotation where `latest.log` is renamed
    to a timestamped file on application startup.

    Args:
        gui_queue: The queue to which log records for the GUI will be sent.
        file_log_level_str: The minimum logging level for the file handler (e.g., 'INFO').
    """
    # 1. Ensure Log Directory Exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Implement Log Rotation
    latest_log_path = LOG_DIR / 'latest.log'
    if latest_log_path.exists():
        try:
            mod_time = latest_log_path.stat().st_mtime
            timestamp_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d_%H-%M-%S')

            archive_log_path = LOG_DIR / f"{timestamp_str}.log"
            latest_log_path.rename(archive_log_path)
        except OSError as e:
            print(f"Error rotating log file: {e}", file=sys.stderr)

    # 3. Configure Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG) # Capture all levels at the root

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 4. Define a Formatter
    log_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)-8s - %(name)-25s - %(message)s'
    )

    # 5. Configure File Handler
    file_log_level = getattr(logging, file_log_level_str.upper(), logging.INFO)

    file_handler = logging.FileHandler(str(latest_log_path), encoding='utf-8')
    file_handler.setLevel(file_log_level)
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)

    # 6. Configure GUI Queue Handler
    queue_handler = logging.handlers.QueueHandler(gui_queue)
    queue_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(queue_handler)

    logging.info("--- Logging initialized ---")
    logging.debug(f"File log level set to: {logging.getLevelName(file_log_level)}")