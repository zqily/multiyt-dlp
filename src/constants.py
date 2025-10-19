import sys
import os
import subprocess

# --- Application Path and Configuration Setup ---
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # sets the app path to the executable's directory.
    APP_PATH = os.path.dirname(sys.executable)
else:
    # In development, the app path is the project root (parent of 'src').
    APP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Use a user-specific directory for configuration to avoid permission issues.
USER_DATA_DIR = os.path.join(os.path.expanduser('~'), '.multiyt-dlp')
CONFIG_FILE = os.path.join(USER_DATA_DIR, 'config.json')
LOG_DIR = os.path.join(USER_DATA_DIR, 'logs')
TEMP_DOWNLOAD_DIR = os.path.join(USER_DATA_DIR, 'temp_downloads')

# Centralize subprocess creation flags to avoid console windows on Windows.
SUBPROCESS_CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS  # type: ignore
    except Exception:
        base_path = APP_PATH
    return os.path.join(base_path, relative_path)

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