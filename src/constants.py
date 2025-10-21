"""
Defines application-wide constants, paths, and utility functions.

This module centralizes configuration for paths, URLs, and subprocess behavior,
adapting to whether the application is running from source or as a frozen executable.
"""

import sys
import subprocess
from pathlib import Path

# --- Application Path and Configuration Setup ---
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # sets the app path to the executable's directory.
    APP_PATH = Path(sys.executable).parent
else:
    # In development, the app path is the project root (parent of 'src').
    APP_PATH = Path(__file__).resolve().parent.parent

# Use a user-specific directory for configuration to avoid permission issues.
USER_DATA_DIR: Path = Path.home() / '.multiyt-dlp'
CONFIG_FILE: Path = USER_DATA_DIR / 'config.json'
LOG_DIR: Path = USER_DATA_DIR / 'logs'
TEMP_DOWNLOAD_DIR: Path = USER_DATA_DIR / 'temp_downloads'

# Centralize subprocess creation flags to avoid console windows on Windows.
SUBPROCESS_CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

def resource_path(relative_path: str) -> Path:
    """
    Get absolute path to resource, works for dev and for PyInstaller.

    Args:
        relative_path: The path to the resource relative to the application root.

    Returns:
        An absolute Path object to the resource.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)  # type: ignore
    except AttributeError:
        base_path = APP_PATH
    return base_path / relative_path

# --- Constants ---
YT_DLP_URLS = {
    'win32': 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe',
    'linux': 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp',
    'darwin': 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos'
}
FFMPEG_URLS = {
    'win32': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
    'linux': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz',
    'darwin': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-macos64-gpl.zip'
}
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
REQUEST_TIMEOUTS = (10, 60)  # (connect_timeout, read_timeout)

# --- Application Update Checker ---
GITHUB_OWNER = 'zqily'
GITHUB_REPO = 'multiyt-dlp'
GITHUB_API_URL = f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest'