import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sys
import os
import shutil
import re
import threading
import queue
import subprocess
import urllib.request
import zipfile
import tarfile
import json

# --- Helper Function for PyInstaller ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- Constants ---
# URLs for the latest yt-dlp releases from GitHub.
YT_DLP_URLS = {
    'win32': 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe',
    'linux': 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp',
    'darwin': 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos'
}

# URLs for the latest FFmpeg releases from BtbN.
FFMPEG_URLS = {
    'win32': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
    'linux': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz',
    'darwin': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-macos64-gpl.zip'
}

# Configuration file name.
CONFIG_FILE = 'config.json'

# --- Configuration Management ---

def load_config():
    """
    Loads application settings from 'config.json'.
    
    Provides robust defaults if the file is missing, corrupt,
    or is missing keys, ensuring the application can always start.
    """
    defaults = {
        'download_type': 'video',
        'video_resolution': '1080',
        'audio_format': 'mp3',
        'embed_thumbnail': True,
        'filename_template': '%(title).100s [%(id)s].%(ext)s',
        'max_concurrent_downloads': 4,
        'last_output_path': os.getcwd()
    }
    if not os.path.exists(CONFIG_FILE):
        return defaults
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Ensure all default keys exist in the loaded config for forward compatibility.
            for key, value in defaults.items():
                config.setdefault(key, value)
            return config
    except (json.JSONDecodeError, IOError):
        return defaults

def save_config(config_data):
    """Saves the current application settings to 'config.json'."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
    except IOError as e:
        print(f"Error saving config file: {e}")

# --- Dependency Management Class ---

class DependencyManager:
    """Manages the discovery, download, and updates for yt-dlp and FFmpeg."""
    def __init__(self, gui_queue):
        self.gui_queue = gui_queue
        self.yt_dlp_path = None
        self.ffmpeg_path = None

    def find_yt_dlp(self):
        """Locates the yt-dlp executable, checking the system PATH first, then the script's directory."""
        self.yt_dlp_path = self._find_executable('yt-dlp')
        return self.yt_dlp_path
    
    def find_ffmpeg(self):
        """Locates the ffmpeg executable, checking the system PATH first, then the script's directory."""
        self.ffmpeg_path = self._find_executable('ffmpeg')
        return self.ffmpeg_path

    def _find_executable(self, name):
        """
        Helper to find an executable by name.
        
        Checks the system's PATH environment variable first, which is the preferred
        location. If not found, it checks the local directory where the script is running.
        """
        # Check system PATH for the executable.
        path = shutil.which(name)
        if path:
            return path
        
        # If not in PATH, check the script's local directory.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_path = os.path.join(script_dir, f'{name}.exe' if sys.platform == 'win32' else name)
        if os.path.exists(local_path):
            return local_path
            
        return None

    def get_yt_dlp_version(self):
        """Returns the version of the located yt-dlp executable as a string."""
        if not self.yt_dlp_path:
            return "Not found"
        try:
            command = [self.yt_dlp_path, '--version']
            # Execute the command without showing a console window on Windows.
            result = subprocess.check_output(
                command, text=True, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            return result.strip()
        except Exception:
            return "Error checking version"

    def install_or_update_yt_dlp(self):
        """Initiates the download/update of yt-dlp in a background thread."""
        threading.Thread(target=self._install_or_update_yt_dlp_thread, daemon=True).start()

    def _install_or_update_yt_dlp_thread(self):
        """Worker thread that handles the download and setup of yt-dlp."""
        platform = sys.platform
        if platform not in YT_DLP_URLS:
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': f"Unsupported OS: {platform}"}))
            return

        try:
            self.gui_queue.put(('dependency_progress', {'type': 'yt-dlp', 'status': 'determinate', 'text': 'Preparing download...', 'value': 0}))
            
            url = YT_DLP_URLS[platform]
            filename = os.path.basename(url)
            
            # Standardize macOS executable name to 'yt-dlp' for consistency.
            if platform == 'darwin' and filename == 'yt-dlp_macos':
                save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'yt-dlp')
            else:
                save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

            with urllib.request.urlopen(url) as response:
                total_size = int(response.getheader('Content-Length', 0))
                chunk_size = 8192
                bytes_downloaded = 0
                with open(save_path, 'wb') as f_out:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        bytes_downloaded += len(chunk)
                        if total_size > 0:
                            progress_percent = (bytes_downloaded / total_size) * 100
                            self.gui_queue.put(('dependency_progress', {
                                'type': 'yt-dlp', 'status': 'determinate',
                                'text': f'Downloading... {bytes_downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB',
                                'value': progress_percent
                            }))

            # Make the downloaded file executable on Linux/macOS.
            if platform in ['linux', 'darwin']:
                os.chmod(save_path, 0o755)

            self.yt_dlp_path = save_path
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': True, 'path': save_path}))

        except Exception as e:
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': str(e)}))
    
    def download_ffmpeg(self):
        """Initiates the download and extraction of FFmpeg in a background thread."""
        threading.Thread(target=self._download_ffmpeg_thread, daemon=True).start()

    def _download_ffmpeg_thread(self):
        """Worker thread that handles the multi-step process of installing FFmpeg."""
        platform = sys.platform
        if platform not in FFMPEG_URLS:
            self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': f"Unsupported OS for FFmpeg: {platform}"}))
            return

        script_dir = os.path.dirname(os.path.abspath(__file__))
        url = FFMPEG_URLS[platform]
        archive_filename = os.path.basename(url)
        archive_path = os.path.join(script_dir, archive_filename)
        extract_dir = os.path.join(script_dir, "ffmpeg_temp")
        final_ffmpeg_name = 'ffmpeg.exe' if platform == 'win32' else 'ffmpeg'
        final_ffmpeg_path = os.path.join(script_dir, final_ffmpeg_name)

        try:
            # 1. Download the compressed archive with progress reporting.
            self.gui_queue.put(('dependency_progress', {'type': 'ffmpeg', 'status': 'determinate', 'text': 'Preparing download...', 'value': 0}))
            with urllib.request.urlopen(url) as response:
                total_size = int(response.getheader('Content-Length', 0))
                chunk_size = 8192
                bytes_downloaded = 0
                with open(archive_path, 'wb') as f_out:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        bytes_downloaded += len(chunk)
                        if total_size > 0:
                            progress_percent = (bytes_downloaded / total_size) * 100
                            self.gui_queue.put(('dependency_progress', {
                                'type': 'ffmpeg', 'status': 'determinate', 
                                'text': f'Downloading... {bytes_downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB', 
                                'value': progress_percent
                            }))

            # 2. Extract the archive into a temporary directory.
            self.gui_queue.put(('dependency_progress', {'type': 'ffmpeg', 'status': 'indeterminate', 'text': 'Extracting FFmpeg...'}))
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            os.makedirs(extract_dir)

            if archive_path.endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            elif archive_path.endswith('.tar.xz'):
                with tarfile.open(archive_path, 'r:xz') as tar_ref:
                    tar_ref.extractall(path=extract_dir)
            
            # 3. Find the executable within the extracted folders and move it.
            self.gui_queue.put(('dependency_progress', {'type': 'ffmpeg', 'status': 'indeterminate', 'text': 'Locating executable...'}))
            ffmpeg_executable_path = None
            for root, _, files in os.walk(extract_dir):
                if final_ffmpeg_name in files:
                    ffmpeg_executable_path = os.path.join(root, final_ffmpeg_name)
                    break
            
            if not ffmpeg_executable_path:
                raise FileNotFoundError(f"Could not find '{final_ffmpeg_name}' in the extracted archive.")

            # Move the executable to the main script directory, replacing any old version.
            if os.path.exists(final_ffmpeg_path):
                os.remove(final_ffmpeg_path)
            shutil.move(ffmpeg_executable_path, final_ffmpeg_path)

            if platform in ['linux', 'darwin']:
                os.chmod(final_ffmpeg_path, 0o755)
            
            self.ffmpeg_path = final_ffmpeg_path
            self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': True, 'path': final_ffmpeg_path}))

        except Exception as e:
            self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': str(e)}))
        finally:
            # 4. Clean up the downloaded archive and temporary extraction folder.
            if os.path.exists(archive_path):
                os.remove(archive_path)
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)

# --- Download Management Class ---

class DownloadManager:
    """Manages the download queue, worker threads, and yt-dlp processes."""
    def __init__(self, gui_queue):
        self.gui_queue = gui_queue
        self.job_queue = queue.Queue()
        self.workers = []
        self.job_counter = 0
        self.completed_jobs = 0
        self.total_jobs = 0
        self.stats_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.active_processes_lock = threading.Lock()
        self.active_processes = {}  # {job_id: subprocess.Popen object}
        self.max_concurrent_downloads = 4
        self.yt_dlp_path = None
        self.current_output_path = None

    def set_config(self, max_concurrent, yt_dlp_path):
        """Applies essential settings like concurrent download limit and yt-dlp path."""
        self.max_concurrent_downloads = max_concurrent
        self.yt_dlp_path = yt_dlp_path

    def get_stats(self):
        """Returns thread-safe download statistics (completed jobs, total jobs)."""
        with self.stats_lock:
            return self.completed_jobs, self.total_jobs

    def start_downloads(self, urls, options):
        """
        Initializes a new download session.
        
        This method resets statistics and spawns a feeder thread to expand
        playlists and populate the job queue with individual video URLs.
        """
        if not self.yt_dlp_path:
            self.gui_queue.put(('log', "Error: yt-dlp path is not set."))
            return
        
        self.gui_queue.put(('downloads_started', None)) # Signal to the GUI to update its state.
        
        # Reset counters and flags for a new batch of downloads.
        with self.stats_lock:
            self.completed_jobs = 0
            self.total_jobs = 0
        self.gui_queue.put(('reset_progress', None))
        self.current_output_path = options['output_path']
        self.stop_event.clear()
        
        feeder_thread = threading.Thread(
            target=self._process_urls_and_feed_queue, 
            args=(urls, options), 
            daemon=True
        )
        feeder_thread.start()

    def add_jobs(self, urls, options):
        """
        Adds new URLs (e.g., for retries) to the existing job queue without resetting statistics.
        """
        if not self.yt_dlp_path:
            self.gui_queue.put(('log', "Error: yt-dlp path is not set."))
            return
        
        self.gui_queue.put(('downloads_started', None)) # Ensure the GUI is in a 'downloading' state.
        self.gui_queue.put(('log', f"Retrying {len(urls)} failed download(s)."))
        
        with self.stats_lock:
            self.total_jobs += len(urls)
        
        for video_url in urls:
            if self.stop_event.is_set(): break
            with self.stats_lock:
                job_id = f"job_{self.job_counter}"
                self.job_counter += 1
            
            self.gui_queue.put(('add_job', (job_id, video_url, "Queued", "0%")))
            self.job_queue.put((job_id, video_url, options.copy()))

        # Start workers if they are not already running.
        self._start_workers()

    def stop_all_downloads(self):
        """Gracefully stops all running and queued downloads."""
        self.gui_queue.put(('log', "\n--- STOP signal received. Terminating downloads... ---"))
        self.stop_event.set()

        # 1. Clear any jobs from the queue that haven't started.
        while not self.job_queue.empty():
            try:
                job_item = self.job_queue.get_nowait()
                job_id = job_item[0]
                self.gui_queue.put(('done', (job_id, 'Cancelled')))
                self.job_queue.task_done()
            except queue.Empty:
                break
        
        # 2. Get a snapshot of currently running processes.
        with self.active_processes_lock:
            procs_to_terminate = list(self.active_processes.items())

        # 3. Terminate all active subprocesses.
        for job_id, process in procs_to_terminate:
            
            # Check if the worker thread already finished this job while we were processing the list.
            is_active_when_terminating = False
            with self.active_processes_lock:
                if job_id in self.active_processes:
                    is_active_when_terminating = True
            
            if not is_active_when_terminating:
                # Job finished naturally before we could terminate it. Skip.
                continue
            
            self.gui_queue.put(('log', f"Stopping process for {job_id}..."))
            
            try:
                process.terminate() # Send SIGTERM.
            except Exception as e:
                self.gui_queue.put(('log', f"Error terminating process for {job_id}: {e}"))
                
            # Wait a short period, then kill if it's still running.
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.gui_queue.put(('log', f"Process for {job_id} unresponsive, killing."))
                try:
                    process.kill() # Send SIGKILL.
                    process.wait()
                except Exception:
                    pass
            except Exception as e:
                 self.gui_queue.put(('log', f"Error waiting for {job_id} to stop: {e}"))
            
            # Since we confirmed it was active and initiated a stop, mark it as cancelled.
            self.gui_queue.put(('done', (job_id, 'Cancelled')))

            # Final removal from the dictionary.
            with self.active_processes_lock:
                if job_id in self.active_processes:
                    del self.active_processes[job_id]

        # 4. Clean up any leftover temporary files.
        self._cleanup_temporary_files()
        
        # 5. Reset all stats and UI progress indicators.
        with self.stats_lock:
            self.total_jobs = 0
            self.completed_jobs = 0
            self.job_counter = 0
        self.gui_queue.put(('reset_progress', None))

    def _process_urls_and_feed_queue(self, urls, options):
        """
        Expands playlists/channels into individual video URLs and adds them to the job queue.
        """
        for url in urls:
            if self.stop_event.is_set():
                self.gui_queue.put(('log', "URL processing cancelled."))
                break
                
            self.gui_queue.put(('log', f"Processing URL: {url}"))
            try:
                # Use yt-dlp to get a flat list of all video URLs from a playlist/channel.
                command = [self.yt_dlp_path, '--flat-playlist', '--print', '%(webpage_url)s', url]
                
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                stdout, stderr = process.communicate()

                if process.returncode != 0:
                    self.gui_queue.put(('log', f"Error processing URL {url}: {stderr.strip()}"))
                    continue

                video_urls = [line for line in stdout.splitlines() if line.strip()]
                if not video_urls:
                     self.gui_queue.put(('log', f"Warning: No videos found for URL {url}"))
                     continue

                self.gui_queue.put(('log', f"Found {len(video_urls)} video(s) for {url}."))
                
                with self.stats_lock:
                    self.total_jobs += len(video_urls)
                
                # Add each individual video URL as a job to the main queue.
                for video_url in video_urls:
                    if self.stop_event.is_set(): break
                    with self.stats_lock:
                        job_id = f"job_{self.job_counter}"
                        self.job_counter += 1
                    
                    self.gui_queue.put(('add_job', (job_id, video_url, "Queued", "0%")))
                    self.job_queue.put((job_id, video_url, options.copy()))

            except Exception as e:
                self.gui_queue.put(('log', f"An unexpected error occurred while processing {url}: {e}"))

        self._start_workers()

    def _cleanup_temporary_files(self):
        """Scans the output directory and deletes temporary download files (e.g., .part, .ytdl)."""
        if not self.current_output_path or not os.path.isdir(self.current_output_path):
            self.gui_queue.put(('log', "Cleanup skipped: Output path not set."))
            return
        
        temp_extensions = {".part", ".ytdl"}
        self.gui_queue.put(('log', f"Scanning '{self.current_output_path}' for temporary files..."))
        count = 0
        try:
            for filename in os.listdir(self.current_output_path):
                if any(filename.endswith(ext) for ext in temp_extensions):
                    file_path = os.path.join(self.current_output_path, filename)
                    try:
                        os.remove(file_path)
                        self.gui_queue.put(('log', f"  - Deleted: {filename}"))
                        count += 1
                    except OSError as e:
                        self.gui_queue.put(('log', f"  - Error deleting {filename}: {e}"))
            
            self.gui_queue.put(('log', f"Cleanup complete. Deleted {count} temporary file(s)."))
        except Exception as e:
            self.gui_queue.put(('log', f"An error occurred during cleanup: {e}"))

    def _start_workers(self):
        """Ensures the correct number of worker threads are running."""
        # Clean up any finished worker threads from the list.
        self.workers = [w for w in self.workers if w.is_alive()]
        num_to_start = self.max_concurrent_downloads - len(self.workers)
        for _ in range(num_to_start):
            worker = threading.Thread(target=self._worker_thread, daemon=True)
            self.workers.append(worker)
            worker.start()

    def _worker_thread(self):
        """The main loop for a download worker. Pulls jobs from the queue and executes them."""
        while not self.stop_event.is_set():
            try:
                job_id, url, options = self.job_queue.get(timeout=1)
                self.gui_queue.put(('update_job', (job_id, 'status', 'Downloading')))
                self._run_download_process(job_id, url, options)
                self.job_queue.task_done()
            except queue.Empty:
                # Queue is empty, this thread can exit.
                break

    def _run_download_process(self, job_id, url, options):
        """
        Constructs and executes the yt-dlp command for a single download,
        parsing its output for progress updates and logs.
        """
        process = None
        try:
            # --- Build yt-dlp Command ---
            progress_template = 'PROGRESS::%(progress._percent_str)s'
            output_template = os.path.join(options['output_path'], options['filename_template'])
            
            command = [
                self.yt_dlp_path,
                '--newline',      # Force progress updates on new lines for easier parsing.
                '--progress-template', progress_template,
                '--no-mtime',     # Avoid modifying file timestamps.
                '-o', output_template
            ]

            # Add format-specific download options.
            if options['download_type'] == 'video':
                res = options['video_resolution']
                
                # If "Best" is selected, use a generic best-quality format string.
                # Otherwise, filter by the selected resolution height.
                if res.lower() == 'best':
                    format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                else:
                    format_str = f'bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                    
                command.extend(['-f', format_str])
            
            elif options['download_type'] == 'audio':
                audio_format = options['audio_format']
                command.extend(['-f', 'bestaudio/best', '-x']) # Extract audio.
                if audio_format != 'best':
                    command.extend(['--audio-format', audio_format])
                    # Set a reasonable default quality for MP3.
                    if audio_format == 'mp3':
                        command.extend(['--audio-quality', '192K'])

            if options['embed_thumbnail']:
                command.append('--embed-thumbnail')
            
            command.append(url)
            
            # --- Execute and Monitor Process ---
            with self.active_processes_lock:
                # If a stop signal was received just before starting, abort.
                if self.stop_event.is_set():
                    return

                process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    encoding='utf-8', errors='replace', bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                self.active_processes[job_id] = process

            # Read output line-by-line to parse progress in real time.
            for line in iter(process.stdout.readline, ''):
                if self.stop_event.is_set(): break
                clean_line = line.strip()
                self.gui_queue.put(('log', f"[{job_id}] {clean_line}"))
                
                # --- Robust Progress Parsing ---
                percentage = None
                
                # 1. Try parsing our custom progress template. It's fast and reliable.
                if clean_line.startswith('PROGRESS::'):
                    try:
                        percentage_str = clean_line.split('::', 1)[1].strip()
                        # Handle cases where yt-dlp might output "N/A" for progress.
                        if '%' in percentage_str:
                            percentage = float(percentage_str.rstrip('%'))
                    except (IndexError, ValueError):
                        pass # Ignore malformed progress lines.

                # 2. Fallback to parsing standard '[download]' lines if the template fails.
                if percentage is None and clean_line.lstrip().startswith('[download]'):
                    match = re.search(r'(\d+\.?\d*)%', clean_line)
                    if match:
                        try:
                            percentage = float(match.group(1))
                        except ValueError:
                            pass # Match was not a valid float.
                
                # If a valid percentage was found, update the GUI.
                if percentage is not None:
                    self.gui_queue.put(('update_job', (job_id, 'progress', f"{percentage:.1f}%")))


            process.stdout.close()
            return_code = process.wait()

            # If a stop was requested, the stop_all_downloads handler is responsible
            # for setting the final status to 'Cancelled'.
            if self.stop_event.is_set():
                return

            # Atomically remove the job from the active list *before* reporting completion.
            # This prevents stop_all_downloads() from incorrectly marking a finished job as 'Cancelled'.
            with self.active_processes_lock:
                if job_id in self.active_processes:
                    del self.active_processes[job_id]

            with self.stats_lock:
                self.completed_jobs += 1
            
            if return_code == 0:
                self.gui_queue.put(('done', (job_id, 'Completed')))
            else:
                self.gui_queue.put(('done', (job_id, 'Failed')))

        except Exception as e:
            if not self.stop_event.is_set():
                with self.stats_lock:
                    self.completed_jobs += 1
                self.gui_queue.put(('done', (job_id, f"Error")))
                self.gui_queue.put(('log', f"[{job_id}] Exception: {e}"))
        finally:
            # Final check to ensure the process is removed from the active list, even on an error.
            with self.active_processes_lock:
                if job_id in self.active_processes:
                    del self.active_processes[job_id]


# --- Main Application Class ---

class YTDlpDownloaderApp:
    """The main application class, handling the Tkinter GUI and event loop."""
    MAX_LOG_LINES = 2000  # Cap the number of log lines to prevent excessive memory usage.

    def __init__(self, root):
        self.root = root
        self.root.title("Multiyt-dlp")
        
        try:
            # Set the window icon
            self.root.iconbitmap(resource_path('icon.ico'))
        except tk.TclError:
            # Handle case where icon is not found or is invalid
            print("Warning: Could not load 'icon.ico'.")
        
        self.root.geometry("850x750")

        # Load configuration from file.
        self.config = load_config()
        self.max_concurrent_downloads = self.config.get('max_concurrent_downloads', 4)
        self.filename_template = tk.StringVar(value=self.config.get('filename_template'))

        # Application state management.
        self.gui_queue = queue.Queue()
        self.dependency_progress_win = None
        self.is_downloading = False
        self.is_updating_dependency = False
        self.yt_dlp_version_var = tk.StringVar(value="Checking...")
        self.is_destroyed = False
        
        # Core business logic components.
        self.dep_manager = DependencyManager(self.gui_queue)
        self.download_manager = DownloadManager(self.gui_queue)

        self.create_widgets()

        # Perform initial check for yt-dlp on startup.
        if not self.dep_manager.find_yt_dlp():
            if not self.initiate_dependency_download('yt-dlp'):
                return  # Abort if user declines to install the critical dependency.
        self.dep_manager.find_ffmpeg()

        # Start the main GUI update loop.
        self.process_gui_queue()
        
        # Register the handler for the window close event.
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """Handles saving configuration and gracefully exiting the application."""
        if self.is_downloading:
            if not messagebox.askyesno(
                "Confirm Exit",
                "Downloads are in progress. Are you sure you want to exit?\n\n"
                "Active downloads will be stopped and incomplete files will be deleted."
            ):
                return
            self.download_manager.stop_all_downloads()

        # Gather current settings from GUI variables to save them.
        self.config['download_type'] = self.download_type_var.get()
        self.config['video_resolution'] = self.video_resolution_var.get()
        self.config['audio_format'] = self.audio_format_var.get()
        self.config['embed_thumbnail'] = self.embed_thumbnail_var.get()
        self.config['filename_template'] = self.filename_template.get()
        self.config['max_concurrent_downloads'] = self.max_concurrent_downloads
        self.config['last_output_path'] = self.output_path_var.get()
        
        save_config(self.config)
        self.is_destroyed = True # Flag to stop the after() loop.
        self.root.destroy()

    def create_widgets(self):
        """Creates and arranges all GUI elements in the main window."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Input Section ---
        input_frame = ttk.LabelFrame(main_frame, text="Inputs", padding="10")
        input_frame.pack(fill=tk.X, pady=5)
        input_frame.columnconfigure(1, weight=1)

        ttk.Label(input_frame, text="Video/Playlist URLs\n(one per line):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.url_text = tk.Text(input_frame, height=5, width=80)
        self.url_text.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)

        ttk.Label(input_frame, text="Output Folder:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.output_path_var = tk.StringVar(value=self.config.get('last_output_path', os.getcwd()))
        output_entry = ttk.Entry(input_frame, textvariable=self.output_path_var, state='readonly')
        output_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        self.browse_button = ttk.Button(input_frame, text="Browse...", command=self.browse_output_path)
        self.browse_button.grid(row=1, column=2, padx=5, pady=5)

        # --- Options Section ---
        self.options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        self.options_frame.pack(fill=tk.X, pady=5)
        
        self.download_type_var = tk.StringVar(value=self.config.get('download_type', 'video'))
        self.download_type_var.trace_add("write", self.update_options_ui)
        ttk.Radiobutton(self.options_frame, text="Video", variable=self.download_type_var, value="video").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(self.options_frame, text="Audio", variable=self.download_type_var, value="audio").pack(side=tk.LEFT, padx=10)
        
        # A container for options that change based on download type.
        self.dynamic_options_frame = ttk.Frame(self.options_frame)
        self.dynamic_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20)

        # Video-specific options (initially hidden or shown by update_options_ui).
        self.video_options_frame = ttk.Frame(self.dynamic_options_frame)
        ttk.Label(self.video_options_frame, text="Resolution:").pack(side=tk.LEFT, padx=(0, 5))
        self.video_resolution_var = tk.StringVar(value=self.config.get('video_resolution', '1080'))
        video_resolutions = ["Best", "1080", "720", "480"]
        self.video_resolution_combo = ttk.Combobox(self.video_options_frame, textvariable=self.video_resolution_var, values=video_resolutions, state="readonly", width=10)
        self.video_resolution_combo.pack(side=tk.LEFT)

        # Audio-specific options (initially hidden or shown by update_options_ui).
        self.audio_options_frame = ttk.Frame(self.dynamic_options_frame)
        ttk.Label(self.audio_options_frame, text="Format:").pack(side=tk.LEFT, padx=(0, 5))
        self.audio_format_var = tk.StringVar(value=self.config.get('audio_format', 'mp3'))
        audio_formats = ["best", "mp3", "m4a", "flac", "wav"]
        self.audio_format_combo = ttk.Combobox(self.audio_options_frame, textvariable=self.audio_format_var, values=audio_formats, state="readonly", width=10)
        self.audio_format_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.embed_thumbnail_var = tk.BooleanVar(value=self.config.get('embed_thumbnail', True))
        self.thumbnail_check = ttk.Checkbutton(self.audio_options_frame, text="Embed Thumbnail", variable=self.embed_thumbnail_var)
        self.thumbnail_check.pack(side=tk.LEFT)
        
        self.update_options_ui() # Set initial visibility of dynamic options.

        # --- Action Buttons ---
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=10)
        action_frame.columnconfigure(0, weight=1)

        self.download_button = ttk.Button(action_frame, text="Add URLs to Queue & Download", command=self.queue_downloads)
        self.download_button.grid(row=0, column=0, sticky=tk.EW)
        
        self.stop_button = ttk.Button(action_frame, text="Stop All", command=self.stop_downloads, state='disabled')
        self.stop_button.grid(row=0, column=1, padx=5)

        self.clear_button = ttk.Button(action_frame, text="Clear Completed", command=self.clear_completed_list)
        self.clear_button.grid(row=0, column=2, padx=5)
        
        self.settings_button = ttk.Button(action_frame, text="Settings", command=self.open_settings_window)
        self.settings_button.grid(row=0, column=3, padx=(5, 0))

        # --- Progress & Log Section ---
        progress_frame = ttk.LabelFrame(main_frame, text="Progress & Log", padding="10")
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        overall_progress_frame = ttk.Frame(progress_frame)
        overall_progress_frame.pack(fill=tk.X, pady=(0, 10))
        self.overall_progress_label = ttk.Label(overall_progress_frame, text="Overall Progress: 0 / 0")
        self.overall_progress_label.pack(side=tk.LEFT, padx=5)
        self.overall_progress_bar = ttk.Progressbar(overall_progress_frame, orient='horizontal', mode='determinate')
        self.overall_progress_bar.pack(fill=tk.X, expand=True)

        tree_frame = ttk.Frame(progress_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.downloads_tree = ttk.Treeview(tree_frame, columns=('url', 'status', 'progress'), show='headings')
        self.downloads_tree.heading('url', text='URL')
        self.downloads_tree.heading('status', text='Status')
        self.downloads_tree.heading('progress', text='Progress')
        self.downloads_tree.column('url', width=450)
        self.downloads_tree.column('status', width=100, anchor=tk.CENTER)
        self.downloads_tree.column('progress', width=100, anchor=tk.CENTER)
        
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.downloads_tree.yview)
        self.downloads_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.downloads_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Define styles for different job statuses for visual feedback.
        self.downloads_tree.tag_configure('failed', background='misty rose')
        self.downloads_tree.tag_configure('completed', background='pale green')
        self.downloads_tree.tag_configure('cancelled', background='light grey')

        # Context menu for the downloads list.
        self.tree_context_menu = tk.Menu(self.root, tearoff=0)
        self.tree_context_menu.add_command(label="Open Output Folder", command=self.open_output_folder)
        self.tree_context_menu.add_command(label="Retry Failed Download", command=self.retry_failed_download)
        self.downloads_tree.bind("<Button-3>", self.show_context_menu)
        if sys.platform == "darwin": # Add macOS specific bindings for context menu.
            self.downloads_tree.bind("<Button-2>", self.show_context_menu)
            self.downloads_tree.bind("<Control-Button-1>", self.show_context_menu)

        self.log_text = scrolledtext.ScrolledText(progress_frame, wrap=tk.WORD, height=10, state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        ttk.Label(main_frame, text="Note: FFmpeg is required for audio conversion and video merging.", font=("TkDefaultFont", 8)).pack(pady=5)

    def update_options_ui(self, *args):
        """Toggles the visibility of video/audio specific options based on user selection."""
        self.video_options_frame.pack_forget()
        self.audio_options_frame.pack_forget()

        download_type = self.download_type_var.get()
        if download_type == "video":
            self.video_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        elif download_type == "audio":
            self.audio_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def initiate_dependency_download(self, dep_type):
        """
        Prompts the user to download a missing dependency and starts the process.
        Returns False if the user declines a critical download, prompting an exit.
        """
        if self.is_updating_dependency:
            return True # Don't start another download if one is already running.

        if dep_type == 'yt-dlp':
            if messagebox.askyesno(
                "yt-dlp Not Found",
                "yt-dlp executable not found.\n\nDownload the latest version automatically?"
            ):
                self.is_updating_dependency = True
                self.toggle_ui_state(False)
                self.show_dependency_progress_window("Downloading yt-dlp")
                self.dep_manager.install_or_update_yt_dlp()
            else:
                messagebox.showerror("Critical Error", "yt-dlp is required. Exiting.")
                self.is_destroyed = True
                self.root.after(1, self.root.destroy)
                return False  # Signal to exit.
        
        elif dep_type == 'ffmpeg':
            if messagebox.askyesno(
                "FFmpeg Not Found",
                "FFmpeg is required for this format but was not found.\n\nDownload it automatically? (This may be a large file)"
            ):
                self.is_updating_dependency = True
                self.toggle_ui_state(False)
                self.show_dependency_progress_window("Downloading FFmpeg")
                self.dep_manager.download_ffmpeg()

        return True  # Signal to continue.

    def queue_downloads(self):
        """Validates user inputs and starts the download process."""
        if self.is_downloading or not self.dep_manager.yt_dlp_path:
            return

        urls_raw = self.url_text.get(1.0, tk.END).strip()
        if not urls_raw:
            messagebox.showwarning("Input Error", "Please enter at least one URL.")
            return

        output_path = self.output_path_var.get()

        # Pre-flight check for the output directory's validity and permissions.
        if not os.path.isdir(output_path):
            if os.path.exists(output_path):
                messagebox.showerror(
                    "Path Error",
                    f"The specified output path exists but is a file, not a directory:\n\n{output_path}"
                )
                return
            
            # If the directory doesn't exist, ask the user for permission to create it.
            if not messagebox.askyesno(
                "Create Directory?",
                f"The output directory does not exist:\n\n{output_path}\n\nDo you want to create it?"
            ):
                return
            
            try:
                os.makedirs(output_path, exist_ok=True)
            except OSError as e:
                messagebox.showerror("Directory Creation Error", f"Failed to create directory:\n\n{e}")
                return

        # Check for write permissions in the target directory.
        try:
            test_file = os.path.join(output_path, f".writetest_{os.getpid()}")
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except (IOError, OSError) as e:
            messagebox.showerror(
                "Permission Error",
                f"The application cannot write to the selected output directory. Please check permissions.\n\nError: {e}"
            )
            return
        
        # Check for FFmpeg if it's required for the selected format.
        if self.download_type_var.get() == 'audio' and not self.dep_manager.find_ffmpeg():
            self.initiate_dependency_download('ffmpeg')
            return

        urls = [url for url in urls_raw.split('\n') if url.strip()]
        self.url_text.delete(1.0, tk.END)
        
        options = {
            'output_path': self.output_path_var.get(),
            'filename_template': self.filename_template.get(),
            'download_type': self.download_type_var.get(),
            'video_resolution': self.video_resolution_var.get(),
            'audio_format': self.audio_format_var.get(),
            'embed_thumbnail': self.embed_thumbnail_var.get()
        }
        
        self.log("--- Queuing new URLs ---")
        self.download_manager.set_config(self.max_concurrent_downloads, self.dep_manager.yt_dlp_path)
        self.download_manager.start_downloads(urls, options)

    def stop_downloads(self):
        """Asks for confirmation and then stops all downloads if confirmed."""
        if not self.is_downloading:
            return
        if messagebox.askyesno("Confirm Stop", "Stop all current and queued downloads?\n\nIncomplete files will be deleted."):
            self.download_manager.stop_all_downloads()
            self.update_button_states(is_downloading=False)

    def clear_completed_list(self):
        """Removes all finished, failed, or cancelled items from the download list."""
        items_to_remove = []
        for item_id in self.downloads_tree.get_children():
            tags = self.downloads_tree.item(item_id, 'tags')
            if 'completed' in tags or 'failed' in tags or 'cancelled' in tags:
                items_to_remove.append(item_id)
        
        for item_id in items_to_remove:
            self.downloads_tree.delete(item_id)
        self.log("Cleared completed and failed items from the list.")

    def process_gui_queue(self):
        """
        Processes messages from background threads via the GUI queue.
        
        This is the sole method responsible for updating the Tkinter UI to ensure thread safety.
        It runs on a timer using root.after().
        """
        try:
            while True:
                message_type, value = self.gui_queue.get_nowait()
                
                if message_type == 'log':
                    self.log(value)
                
                elif message_type == 'add_job':
                    job_id, url, status, progress = value
                    self.downloads_tree.insert('', 'end', iid=job_id, values=(url, status, progress))
                    self.update_overall_progress()

                elif message_type == 'update_job':
                    job_id, column, new_value = value
                    if self.downloads_tree.exists(job_id):
                        self.downloads_tree.set(job_id, column, new_value)

                elif message_type == 'done':
                    job_id, status = value
                    if self.downloads_tree.exists(job_id):
                        if status == 'Completed':
                           self.downloads_tree.set(job_id, 'progress', '100.0%')
                           self.downloads_tree.item(job_id, tags=('completed',))
                        elif status == 'Cancelled':
                            self.downloads_tree.item(job_id, tags=('cancelled',))
                        else: # Failed or Error
                            self.downloads_tree.item(job_id, tags=('failed',))
                        self.downloads_tree.set(job_id, 'status', status)
                    self.update_overall_progress()

                elif message_type == 'reset_progress':
                    self.update_overall_progress()
                
                elif message_type == 'downloads_started':
                    self.update_button_states(is_downloading=True)

                elif message_type == 'dependency_progress':
                    self.update_dependency_progress(value)

                elif message_type == 'dependency_done':
                    self.handle_dependency_result(value)

        except queue.Empty:
            # If the window has been destroyed, don't schedule the next check.
            if not self.is_destroyed:
                self.root.after(100, self.process_gui_queue)

    def handle_dependency_result(self, result):
        """Processes the success or failure result of a dependency download."""
        self.close_dependency_progress_window()
        self.toggle_ui_state(True)
        
        dep_type = result.get('type')
        if result.get('success'):
            path = result.get('path')
            messagebox.showinfo("Success", f"{dep_type.upper()} downloaded successfully to:\n{path}")
        else:
            error_msg = result.get('error')
            messagebox.showerror(f"{dep_type.upper()} Download Failed", f"An error occurred: {error_msg}")
            # Exit if the critical dependency (yt-dlp) failed on the initial install attempt.
            if dep_type == 'yt-dlp' and not self.dep_manager.yt_dlp_path:
                self.is_destroyed = True
                self.root.destroy()
        
        if self.is_updating_dependency:
            self.is_updating_dependency = False
            self.toggle_update_buttons(True)
            if dep_type == 'yt-dlp':
                self.check_yt_dlp_version() # Refresh version display in settings.

    def update_overall_progress(self):
        """Updates the main progress bar and its corresponding label."""
        completed, total = self.download_manager.get_stats()
        label_text = f"Overall Progress: {completed} / {total}"
        self.overall_progress_label.config(text=label_text)
        
        if total > 0:
            progress_percent = (completed / total) * 100
            self.overall_progress_bar['value'] = progress_percent
        else:
            self.overall_progress_bar['value'] = 0

        # Check if all jobs are finished and update the application state.
        if total > 0 and completed >= total and self.is_downloading:
             self.gui_queue.put(('log', "\n--- All queued downloads are complete! ---"))
             self.update_button_states(is_downloading=False)

    def update_button_states(self, is_downloading):
        """Enables or disables key buttons based on the application's download state."""
        self.is_downloading = is_downloading
        download_state = 'disabled' if is_downloading else 'normal'
        stop_state = 'normal' if is_downloading else 'disabled'
        
        self.download_button.config(state=download_state)
        self.settings_button.config(state=download_state)
        self.stop_button.config(state=stop_state)
                
    def toggle_ui_state(self, enabled):
        """Disables or enables major UI controls to prevent user interaction during critical operations."""
        state = 'normal' if enabled else 'disabled'
        combo_state = 'readonly' if enabled else 'disabled'

        self.url_text.config(state=state)
        self.browse_button.config(state=state)
        self.download_button.config(state=state)

        # Toggle all interactive widgets in the options frame.
        for child in self.options_frame.winfo_children():
            if isinstance(child, ttk.Radiobutton):
                child.config(state=state)

        self.video_resolution_combo.config(state=combo_state)
        self.audio_format_combo.config(state=combo_state)
        self.thumbnail_check.config(state=state)
                
    def show_dependency_progress_window(self, title):
        """Creates a modal progress window for dependency downloads."""
        if self.dependency_progress_win and self.dependency_progress_win.winfo_exists():
            return
        
        self.dependency_progress_win = tk.Toplevel(self.root)
        self.dependency_progress_win.title(title)
        self.dependency_progress_win.geometry("400x120")
        self.dependency_progress_win.resizable(False, False)
        self.dependency_progress_win.transient(self.root)
        self.dependency_progress_win.protocol("WM_DELETE_WINDOW", lambda: None) # Disable closing.

        self.dep_progress_label = tk.Label(self.dependency_progress_win, text="Initializing...", pady=10)
        self.dep_progress_label.pack(fill=tk.X, padx=10)
        self.dep_progress_bar = ttk.Progressbar(self.dependency_progress_win, orient='horizontal', length=380)
        self.dep_progress_bar.pack(pady=10)
    
    def update_dependency_progress(self, data):
        """Updates the widgets in the dependency download progress window."""
        if not self.dependency_progress_win or not self.dependency_progress_win.winfo_exists():
            self.show_dependency_progress_window(f"Downloading {data.get('type')}")

        self.dep_progress_label.config(text=data.get('text', ''))
        
        if data.get('status') == 'indeterminate':
            self.dep_progress_bar.config(mode='indeterminate')
            self.dep_progress_bar.start(10)
        else: # Assumes 'determinate'
            self.dep_progress_bar.stop()
            self.dep_progress_bar.config(mode='determinate')
            self.dep_progress_bar['value'] = data.get('value', 0)
    
    def close_dependency_progress_window(self):
        """Destroys the dependency progress window if it exists."""
        if self.dependency_progress_win:
            self.dep_progress_bar.stop()
            self.dependency_progress_win.destroy()
            self.dependency_progress_win = None

    def open_settings_window(self):
        """Opens the settings dialog window."""
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Settings")
        settings_win.geometry("500x350")
        settings_win.resizable(False, False)
        settings_win.transient(self.root) 

        settings_frame = ttk.Frame(settings_win, padding="10")
        settings_frame.pack(fill=tk.BOTH, expand=True)

        # Use temporary variables for settings to allow cancellation.
        concurrent_var = tk.IntVar(value=self.max_concurrent_downloads)
        temp_filename_template = tk.StringVar(value=self.filename_template.get()) 

        # Max Concurrent Downloads setting.
        ttk.Label(settings_frame, text="Max Concurrent Downloads:").grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)
        ttk.Spinbox(settings_frame, from_=1, to=20, textvariable=concurrent_var, width=5).grid(row=0, column=1, padx=5, pady=10, sticky=tk.W)

        # Filename Template setting.
        ttk.Label(settings_frame, text="Filename Template:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(settings_frame, textvariable=temp_filename_template, width=50).grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        
        help_text = "e.g., %(uploader)s - %(title)s [%(id)s].%(ext)s"
        ttk.Label(settings_frame, text=help_text, font=("TkDefaultFont", 8, "italic")).grid(row=2, column=1, sticky=tk.W, padx=5)

        # Dependency update section.
        update_frame = ttk.LabelFrame(settings_frame, text="Update Dependencies", padding=10)
        update_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=15)
        update_frame.columnconfigure(1, weight=1)
        
        ttk.Label(update_frame, text="yt-dlp version:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Label(update_frame, textvariable=self.yt_dlp_version_var).grid(row=0, column=1, sticky=tk.W, padx=5)
        self.check_yt_dlp_version()

        update_buttons_frame = ttk.Frame(update_frame)
        update_buttons_frame.grid(row=1, column=0, columnspan=2, pady=(10,0))
        
        self.yt_dlp_update_button = ttk.Button(update_buttons_frame, text="Update yt-dlp", command=self.start_yt_dlp_update)
        self.yt_dlp_update_button.pack(side=tk.LEFT, padx=5)

        self.ffmpeg_update_button = ttk.Button(update_buttons_frame, text="Update FFmpeg", command=self.start_ffmpeg_update)
        self.ffmpeg_update_button.pack(side=tk.LEFT, padx=5)

        def save_and_close():
            """Validates and applies settings, then closes the window."""
            if self.is_updating_dependency:
                messagebox.showwarning("Busy", "Cannot close settings while an update is in progress.", parent=settings_win)
                return

            try:
                # 1. Validate concurrent downloads value.
                new_concurrent_val = concurrent_var.get()
                if not (1 <= new_concurrent_val <= 20):
                    messagebox.showwarning("Invalid Value", "Concurrent downloads must be between 1 and 20.", parent=settings_win)
                    return
                
                # 2. Validate filename template for basic requirements.
                new_template = temp_filename_template.get().strip() 
                if not new_template or not re.search(r'%\((title|id)', new_template):
                    messagebox.showwarning("Invalid Value", "Template must include %(title)s or %(id)s.", parent=settings_win)
                    return

                # Prevent path traversal and absolute paths in the template for security.
                if '/' in new_template or '\\' in new_template:
                    messagebox.showerror(
                        "Invalid Filename Template",
                        "Filename template cannot contain path separators ('/' or '\\').",
                        parent=settings_win
                    )
                    return
                
                if os.path.isabs(new_template):
                    messagebox.showerror(
                        "Invalid Filename Template",
                        "Filename template cannot be an absolute path.",
                        parent=settings_win
                    )
                    return
                
                # 3. Apply settings only after all validation passes.
                self.max_concurrent_downloads = new_concurrent_val
                self.filename_template.set(new_template) 
                
                self.log(f"Settings updated: Max concurrent downloads set to {self.max_concurrent_downloads}.")
                self.log(f"Settings updated: Filename template set to '{self.filename_template.get()}'.")
                settings_win.destroy()
            except tk.TclError:
                 messagebox.showwarning("Invalid Value", "Please enter a valid number for concurrent downloads.", parent=settings_win)

        # Action buttons for the settings window.
        buttons_frame = ttk.Frame(settings_frame)
        buttons_frame.grid(row=4, column=0, columnspan=2, pady=15, sticky=tk.E)

        save_button = ttk.Button(buttons_frame, text="Save", command=save_and_close)
        save_button.pack(side=tk.LEFT, padx=5)
        
        cancel_button = ttk.Button(buttons_frame, text="Cancel", command=settings_win.destroy)
        cancel_button.pack(side=tk.LEFT)

        # Make the 'X' button act as a cancel button.
        settings_win.protocol("WM_DELETE_WINDOW", settings_win.destroy)

    def check_yt_dlp_version(self):
        """Gets the yt-dlp version in a background thread to avoid blocking the GUI."""
        self.yt_dlp_version_var.set("Checking...")
        def _get_version():
            version = self.dep_manager.get_yt_dlp_version()
            self.yt_dlp_version_var.set(version)
        threading.Thread(target=_get_version, daemon=True).start()

    def toggle_update_buttons(self, enabled):
        """Enables or disables the update buttons in the settings window."""
        state = 'normal' if enabled else 'disabled'
        if hasattr(self, 'yt_dlp_update_button') and self.yt_dlp_update_button.winfo_exists():
            self.yt_dlp_update_button.config(state=state)
        if hasattr(self, 'ffmpeg_update_button') and self.ffmpeg_update_button.winfo_exists():
            self.ffmpeg_update_button.config(state=state)

    def start_yt_dlp_update(self):
        """Starts the yt-dlp update process after user confirmation."""
        if self.is_updating_dependency: return
        if messagebox.askyesno("Confirm Update", "Download the latest version of yt-dlp?", parent=self.root):
            self.is_updating_dependency = True
            self.toggle_update_buttons(False)
            self.show_dependency_progress_window("Updating yt-dlp")
            self.dep_manager.install_or_update_yt_dlp()

    def start_ffmpeg_update(self):
        """Starts the FFmpeg download/update process after user confirmation."""
        if self.is_updating_dependency: return
        if messagebox.askyesno("Confirm Update", "Download the latest version of FFmpeg? This can be a large file.", parent=self.root):
            self.is_updating_dependency = True
            self.toggle_update_buttons(False)
            self.show_dependency_progress_window("Updating FFmpeg")
            self.dep_manager.download_ffmpeg()

    def show_context_menu(self, event):
        """Displays the right-click context menu over the downloads list."""
        item_id = self.downloads_tree.identify_row(event.y)
        if not item_id:
            return

        # Select the item under the cursor if it's not already part of a selection.
        if item_id not in self.downloads_tree.selection():
            self.downloads_tree.selection_set(item_id)
        
        # Enable the "Retry" option only if at least one selected item has a 'failed' status.
        is_failed = any('failed' in self.downloads_tree.item(s_item_id, 'tags') 
                        for s_item_id in self.downloads_tree.selection())
        
        retry_state = 'normal' if is_failed else 'disabled'
        self.tree_context_menu.entryconfig("Retry Failed Download", state=retry_state)
        
        self.tree_context_menu.post(event.x_root, event.y_root)

    def open_output_folder(self):
        """Opens the current output folder in the system's default file explorer."""
        path = self.output_path_var.get()
        if not os.path.isdir(path):
            messagebox.showerror("Error", f"Output folder does not exist:\n{path}")
            return
        
        try:
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin': # macOS
                subprocess.run(['open', path], check=True)
            else: # Linux
                subprocess.run(['xdg-open', path], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open output folder:\n{e}")

    def retry_failed_download(self):
        """Re-queues all selected downloads that have a 'failed' status."""
        urls_to_retry = []
        items_to_delete = []
        
        for item_id in self.downloads_tree.selection():
            if 'failed' in self.downloads_tree.item(item_id, 'tags'):
                url = self.downloads_tree.item(item_id, 'values')[0]
                urls_to_retry.append(url)
                items_to_delete.append(item_id)

        if not urls_to_retry:
            return

        # Delete the old failed entries from the list before re-queuing.
        for item_id in items_to_delete:
            self.downloads_tree.delete(item_id)

        # Get current options and add the jobs back to the download queue.
        options = {
            'output_path': self.output_path_var.get(),
            'filename_template': self.filename_template.get(),
            'download_type': self.download_type_var.get(),
            'video_resolution': self.video_resolution_var.get(),
            'audio_format': self.audio_format_var.get(),
            'embed_thumbnail': self.embed_thumbnail_var.get()
        }
        
        self.download_manager.add_jobs(urls_to_retry, options)

    def browse_output_path(self):
        """Opens a dialog to allow the user to select the output directory."""
        path = filedialog.askdirectory(initialdir=self.output_path_var.get())
        if path:
            self.output_path_var.set(path)
            
    def log(self, message):
        """
        Appends a message to the log widget, trimming old lines to save memory
        and prevent performance degradation with very large amounts of output.
        """
        # The state is toggled to allow insertion and then prevent user editing.
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + '\n')

        # Trim the log if it exceeds the maximum number of lines.
        num_lines = int(self.log_text.index('end-1c').split('.')[0])
        if num_lines > self.MAX_LOG_LINES:
            lines_to_delete = num_lines - self.MAX_LOG_LINES
            self.log_text.delete('1.0', f'{lines_to_delete + 1}.0')

        self.log_text.see(tk.END) # Scroll to the end.
        self.log_text.config(state='disabled')


if __name__ == "__main__":
    root = tk.Tk()
    app = YTDlpDownloaderApp(root)
    root.mainloop()