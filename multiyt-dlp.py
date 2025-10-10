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
import urllib.error
import urllib.parse
import zipfile
import tarfile
import json
import uuid
import time
import socket
import tempfile
import signal

# --- Application Path and Configuration Setup ---
if getattr(sys, 'frozen', False):
    APP_PATH = os.path.dirname(sys.executable)
else:
    APP_PATH = os.path.dirname(os.path.abspath(__file__))

# Use a user-specific directory for configuration to avoid permission issues.
USER_DATA_DIR = os.path.join(os.path.expanduser('~'), '.multiyt-dlp')
os.makedirs(USER_DATA_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(USER_DATA_DIR, 'config.json')

# Centralize subprocess creation flags to avoid console windows on Windows.
SUBPROCESS_CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
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
URL_TIMEOUT = 30

# --- Configuration Management ---

class ConfigManager:
    """Handles loading, saving, and validating the application configuration."""
    def __init__(self, config_path):
        self.config_path = config_path
        self.defaults = {
            'download_type': 'video', 'video_resolution': '1080', 'audio_format': 'mp3',
            'embed_thumbnail': True, 'filename_template': '%(title).100s [%(id)s].%(ext)s',
            'max_concurrent_downloads': 4, 'last_output_path': os.path.expanduser("~")
        }

    def load(self):
        """Loads config, merges with defaults, validates, and returns it."""
        if not os.path.exists(self.config_path):
            return self.defaults.copy()
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # Merge with defaults to ensure all keys exist
            for key, value in self.defaults.items():
                config.setdefault(key, value)
            self.validate(config)
            return config
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config.json: {e}. Backing up and using defaults.")
            try:
                if os.path.exists(self.config_path):
                    shutil.move(self.config_path, f"{self.config_path}.{int(time.time())}.bak")
            except IOError:
                pass
            return self.defaults.copy()

    def save(self, settings_dict):
        """Saves the provided settings dictionary to the config file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=4)
        except IOError as e:
            print(f"Error saving config file: {e}")

    def validate(self, config):
        """Validates configuration values and reverts invalid ones to defaults."""
        if not isinstance(config.get('max_concurrent_downloads'), int) or not (1 <= config['max_concurrent_downloads'] <= 20):
            print(f"Warning: Invalid max_concurrent_downloads '{config.get('max_concurrent_downloads')}'. Reverting to default.")
            config['max_concurrent_downloads'] = self.defaults['max_concurrent_downloads']

        template = config.get('filename_template', '')
        is_invalid = (
            not template or
            not re.search(r'%\((title|id)', template) or
            '/' in template or '\\' in template or '..' in template or
            os.path.isabs(template)
        )
        if is_invalid:
            print(f"Warning: Invalid filename_template '{template}'. Reverting to default.")
            config['filename_template'] = self.defaults['filename_template']
        
        if not os.path.isdir(config.get('last_output_path', '')):
            config['last_output_path'] = self.defaults['last_output_path']

# --- Dependency Management Class ---

class DependencyManager:
    """Manages the discovery, download, and updates for yt-dlp and FFmpeg."""
    def __init__(self, gui_queue):
        self.gui_queue = gui_queue
        self.yt_dlp_path = self.find_yt_dlp()
        self.ffmpeg_path = self.find_ffmpeg()

    def find_yt_dlp(self):
        self.yt_dlp_path = self._find_executable('yt-dlp')
        return self.yt_dlp_path

    def find_ffmpeg(self):
        self.ffmpeg_path = self._find_executable('ffmpeg')
        return self.ffmpeg_path

    def _find_executable(self, name):
        # Prefer locally managed executable over one in PATH
        local_path = os.path.join(APP_PATH, f'{name}.exe' if sys.platform == 'win32' else name)
        if os.path.exists(local_path): return local_path
        
        path_in_system = shutil.which(name)
        if path_in_system: return path_in_system
        
        return None

    def get_version(self, executable_path):
        """Returns the version of a given executable by running it with '--version'."""
        if not executable_path or not os.path.exists(executable_path): return "Not found"
        try:
            command = [executable_path, '-version'] if 'ffmpeg' in os.path.basename(executable_path).lower() else [executable_path, '--version']
            kwargs = {'text': True, 'stderr': subprocess.STDOUT}
            if sys.platform == 'win32':
                kwargs['creationflags'] = SUBPROCESS_CREATION_FLAGS
            result = subprocess.check_output(command, **kwargs)
            return result.strip().split('\n')[0]
        except FileNotFoundError:
            return "Not found"
        except PermissionError:
            return "Permission error"
        except subprocess.CalledProcessError:
            return "Cannot execute"
        except Exception as e:
            print(f"Error checking version for {executable_path}: {e}")
            return "Error checking version"

    def _download_file_with_progress(self, url, save_path, dep_type):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                text = f'Preparing download (Attempt {attempt + 1}/{max_retries})...'
                self.gui_queue.put(('dependency_progress', {'type': dep_type, 'status': 'determinate', 'text': text, 'value': 0}))
                req = urllib.request.Request(url, headers=REQUEST_HEADERS)
                with urllib.request.urlopen(req, timeout=URL_TIMEOUT) as response:
                    total_size = int(response.getheader('Content-Length', 0))
                    if total_size <= 0:
                        text = f'Downloading {dep_type}... (Size unknown)'
                        self.gui_queue.put(('dependency_progress', {'type': dep_type, 'status': 'indeterminate', 'text': text}))
                    chunk_size, bytes_downloaded = 8192, 0
                    with open(save_path, 'wb') as f_out:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk: break
                            f_out.write(chunk)
                            bytes_downloaded += len(chunk)
                            if total_size > 0:
                                progress_percent = (bytes_downloaded / total_size) * 100
                                text = f'Downloading... {bytes_downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB'
                                self.gui_queue.put(('dependency_progress', {'type': dep_type, 'status': 'determinate', 'text': text, 'value': progress_percent}))
                self.gui_queue.put(('dependency_progress', {
                    'type': dep_type, 'status': 'determinate', 
                    'text': 'Download complete. Preparing...', 'value': 100
                }))
                return  # Success
            except (urllib.error.URLError, socket.timeout) as e:
                log_msg = f"Network error on attempt {attempt + 1} for {dep_type}: {e}"
                self.gui_queue.put(('log', log_msg))
                print(log_msg)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise e

    def install_or_update_yt_dlp(self):
        threading.Thread(target=self._install_or_update_yt_dlp_thread, daemon=True, name="yt-dlp-Installer").start()

    def _install_or_update_yt_dlp_thread(self):
        platform = sys.platform
        if platform not in YT_DLP_URLS:
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': f"Unsupported OS: {platform}"}))
            return
        try:
            url = YT_DLP_URLS[platform]
            filename = os.path.basename(urllib.parse.unquote(url))
            save_path = os.path.join(APP_PATH, 'yt-dlp' if platform == 'darwin' and filename == 'yt-dlp_macos' else filename)
            self._download_file_with_progress(url, save_path, 'yt-dlp')
            if platform in ['linux', 'darwin']: os.chmod(save_path, 0o755)
            self.yt_dlp_path = save_path
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': True, 'path': save_path}))
        except Exception as e:
            error_message = f"Network error: {getattr(e, 'reason', '')}" if isinstance(e, urllib.error.URLError) else str(e)
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': error_message}))

    def download_ffmpeg(self):
        threading.Thread(target=self._download_ffmpeg_thread, daemon=True, name="FFmpeg-Installer").start()

    def _download_ffmpeg_thread(self):
        platform = sys.platform
        if platform not in FFMPEG_URLS:
            self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': f"Unsupported OS: {platform}"}))
            return
        url = FFMPEG_URLS[platform]
        final_ffmpeg_name = 'ffmpeg.exe' if platform == 'win32' else 'ffmpeg'
        final_ffmpeg_path = os.path.join(APP_PATH, final_ffmpeg_name)
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                archive_path = os.path.join(temp_dir, os.path.basename(urllib.parse.unquote(url)))
                extract_dir = os.path.join(temp_dir, "ffmpeg_extracted")
                self._download_file_with_progress(url, archive_path, 'ffmpeg')
                
                self.gui_queue.put(('dependency_progress', {'type': 'ffmpeg', 'status': 'indeterminate', 'text': 'Extracting FFmpeg...'}))
                os.makedirs(extract_dir, exist_ok=True)
                if archive_path.endswith('.zip'):
                    with zipfile.ZipFile(archive_path, 'r') as zip_ref: zip_ref.extractall(extract_dir)
                elif archive_path.endswith('.tar.xz'):
                    with tarfile.open(archive_path, 'r:xz') as tar_ref: tar_ref.extractall(path=extract_dir)
                
                self.gui_queue.put(('dependency_progress', {'type': 'ffmpeg', 'status': 'indeterminate', 'text': 'Locating executable...'}))
                ffmpeg_exe_path = next((os.path.join(root, f) for root, _, files in os.walk(extract_dir) for f in files if f.lower() == final_ffmpeg_name), None)
                
                if not ffmpeg_exe_path: raise FileNotFoundError(f"Could not find '{final_ffmpeg_name}' in archive.")
                
                if os.path.exists(final_ffmpeg_path): os.remove(final_ffmpeg_path)
                shutil.move(ffmpeg_exe_path, final_ffmpeg_path)
                if platform in ['linux', 'darwin']: os.chmod(final_ffmpeg_path, 0o755)
                self.ffmpeg_path = final_ffmpeg_path
                self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': True, 'path': final_ffmpeg_path}))
            except Exception as e:
                error_message = f"Network error: {getattr(e, 'reason', '')}" if isinstance(e, urllib.error.URLError) else str(e)
                self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': error_message}))

# --- Download Management Class ---

class DownloadManager:
    """Manages the download queue, worker threads, and yt-dlp processes."""
    def __init__(self, gui_queue):
        self.gui_queue = gui_queue
        self.job_queue = queue.Queue()
        self.url_processing_queue = queue.Queue()
        self.workers, self.completed_jobs, self.total_jobs = [], 0, 0
        self.stats_lock, self.stop_event = threading.Lock(), threading.Event()
        self.active_processes_lock, self.active_processes = threading.Lock(), {}
        self.max_concurrent_downloads, self.yt_dlp_path, self.ffmpeg_path, self.current_output_path = 4, None, None, None

    def set_config(self, max_concurrent, yt_dlp_path, ffmpeg_path):
        self.max_concurrent_downloads, self.yt_dlp_path, self.ffmpeg_path = max_concurrent, yt_dlp_path, ffmpeg_path

    def get_stats(self):
        with self.stats_lock: return self.completed_jobs, self.total_jobs

    def start_downloads(self, urls, options):
        if not self.yt_dlp_path:
            self.gui_queue.put(('log', "Error: yt-dlp path is not set."))
            return
        with self.stats_lock: self.completed_jobs, self.total_jobs = 0, 0
        self.gui_queue.put(('reset_progress', None))
        self.current_output_path = options['output_path']
        self.stop_event.clear()
        
        for url in urls:
            self.url_processing_queue.put((url, options))
        
        def monitor_url_queue():
            self.url_processing_queue.join()
            if not self.stop_event.is_set():
                self.gui_queue.put(('url_processing_done', None))
                self._start_workers()

        threading.Thread(target=monitor_url_queue, daemon=True, name="URL-Queue-Monitor").start()
        
        num_url_processors = min(8, len(urls))
        for i in range(num_url_processors):
            thread = threading.Thread(target=self._url_processor_worker, daemon=True, name=f"URL-Processor-{i+1}")
            thread.start()

    def add_jobs(self, urls, options):
        if not self.yt_dlp_path:
            self.gui_queue.put(('log', "Error: yt-dlp path is not set."))
            return
        self.gui_queue.put(('log', f"Retrying {len(urls)} failed download(s)."))
        with self.stats_lock: self.total_jobs += len(urls)
        for video_url in urls:
            if self.stop_event.is_set(): break
            job_id = str(uuid.uuid4())
            self.gui_queue.put(('add_job', (job_id, video_url, "Queued", "0%")))
            self.job_queue.put((job_id, video_url, options.copy()))
        self._start_workers()

    def stop_all_downloads(self):
        self.gui_queue.put(('log', "\n--- STOP signal received. Terminating downloads... ---"))
        self.stop_event.set()
        
        # Clear queues
        for q in [self.job_queue, self.url_processing_queue]:
            while not q.empty():
                try:
                    if q is self.job_queue:
                        job_id, *_ = q.get_nowait()
                        self.gui_queue.put(('done', (job_id, 'Cancelled')))
                    else:
                        q.get_nowait()
                    q.task_done()
                except queue.Empty: break

        # Terminate active processes
        with self.active_processes_lock:
            procs_to_terminate = list(self.active_processes.items())
        
        for job_id, process in procs_to_terminate:
            self.gui_queue.put(('log', f"Stopping process for {job_id} (PID: {process.pid})..."))
            try:
                if sys.platform == 'win32':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=SUBPROCESS_CREATION_FLAGS)
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except Exception as e:
                self.gui_queue.put(('log', f"Platform-specific kill failed for {job_id}: {e}. Falling back."))
                try: process.terminate()
                except: pass
            
            self.gui_queue.put(('done', (job_id, 'Cancelled')))
            with self.active_processes_lock:
                if job_id in self.active_processes: del self.active_processes[job_id]
        
        self._cleanup_temporary_files()
        with self.stats_lock: self.total_jobs, self.completed_jobs = 0, 0
        self.gui_queue.put(('reset_progress', None))

    def _url_processor_worker(self):
        while not self.stop_event.is_set():
            try:
                url, options = self.url_processing_queue.get(timeout=1)
                self.gui_queue.put(('log', f"[{threading.current_thread().name}] Started processing: {url}"))
                self._expand_url_and_queue_jobs(url, options)
                self.gui_queue.put(('log', f"[{threading.current_thread().name}] Finished processing: {url}"))
                self.url_processing_queue.task_done()
            except queue.Empty:
                break
            except Exception as e:
                self.gui_queue.put(('log', f"[{threading.current_thread().name}] Error processing URL {url}: {e}"))
                if not self.url_processing_queue.empty(): self.url_processing_queue.task_done()

    def _expand_url_and_queue_jobs(self, url, options):
        try:
            command = [self.yt_dlp_path, '--flat-playlist', '--print-json', '--no-warnings', url]
            kwargs = {'text': True, 'encoding': 'utf-8', 'errors': 'replace'}
            if sys.platform == 'win32':
                kwargs['creationflags'] = SUBPROCESS_CREATION_FLAGS
            json_output = subprocess.check_output(command, **kwargs)
            video_count = 0
            for line in json_output.strip().split('\n'):
                if self.stop_event.is_set(): break
                try:
                    video_info = json.loads(line)
                    video_url = video_info.get('webpage_url') or video_info.get('url')
                    if video_url:
                        video_count += 1
                        job_id = str(uuid.uuid4())
                        with self.stats_lock: self.total_jobs += 1
                        self.gui_queue.put(('add_job', (job_id, video_url, "Queued", "0%")))
                        self.job_queue.put((job_id, video_url, options.copy()))
                except json.JSONDecodeError:
                    self.gui_queue.put(('log', f"[URL_Processor] Could not parse line: {line}"))
            if video_count > 0: self.gui_queue.put(('log', f"Found and queued {video_count} video(s) for {url}."))
            elif not self.stop_event.is_set(): self.gui_queue.put(('log', f"Warning: No videos found for URL {url}"))
        except subprocess.CalledProcessError as e:
            error_output = e.output.strip() if e.output else "No output from yt-dlp."
            self.gui_queue.put(('log', f"yt-dlp failed to expand '{url}'. Output: {error_output}"))
            self.gui_queue.put(('log', f"Assuming '{url}' is a single video."))
            if not self.stop_event.is_set():
                job_id = str(uuid.uuid4())
                with self.stats_lock: self.total_jobs += 1
                self.gui_queue.put(('add_job', (job_id, url, "Queued", "0%")))
                self.job_queue.put((job_id, url, options.copy()))
        except Exception as e:
            self.gui_queue.put(('log', f"An error occurred while processing {url}: {e}"))

    def _cleanup_temporary_files(self):
        if not self.current_output_path or not os.path.isdir(self.current_output_path): return
        temp_extensions, count = {".part", ".ytdl", ".webm"}, 0
        self.gui_queue.put(('log', f"Scanning '{self.current_output_path}' for temp files..."))
        for filename in os.listdir(self.current_output_path):
            if any(filename.endswith(ext) for ext in temp_extensions):
                try: os.remove(os.path.join(self.current_output_path, filename)); count += 1
                except OSError as e: self.gui_queue.put(('log', f"  - Error deleting {filename}: {e}"))
        if count > 0: self.gui_queue.put(('log', f"Cleanup complete. Deleted {count} temporary file(s)."))

    def _start_workers(self):
        self.workers = [w for w in self.workers if w.is_alive()]
        for _ in range(self.max_concurrent_downloads - len(self.workers)):
            worker = threading.Thread(target=self._worker_thread, daemon=True, name=f"Download-Worker-{len(self.workers) + 1}")
            self.workers.append(worker); worker.start()

    def _worker_thread(self):
        while not self.stop_event.is_set():
            try:
                job_id, url, options = self.job_queue.get(timeout=1)
                if self.stop_event.is_set():
                    self.gui_queue.put(('done', (job_id, 'Cancelled')))
                    self.job_queue.task_done()
                    continue
                self.gui_queue.put(('update_job', (job_id, 'status', 'Downloading')))
                self._run_download_process(job_id, url, options)
                self.job_queue.task_done()
            except queue.Empty:
                break

    def _run_download_process(self, job_id, url, options):
        error_message, final_status = None, 'Failed'
        try:
            command = [self.yt_dlp_path, '--newline', '--progress-template', 'PROGRESS::%(progress._percent_str)s', '--no-mtime', '-o', os.path.join(options['output_path'], options['filename_template'])]
            if self.ffmpeg_path: command.extend(['--ffmpeg-location', os.path.dirname(self.ffmpeg_path)])
            if options['download_type'] == 'video':
                res, f_str = options['video_resolution'], 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                if res.lower() != 'best': f_str = f'bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best[height<={res}]'
                command.extend(['-f', f_str])
            elif options['download_type'] == 'audio':
                audio_format = options['audio_format']
                command.extend(['-f', 'bestaudio/best', '-x'])
                if audio_format != 'best':
                    command.extend(['--audio-format', audio_format])
                    if audio_format == 'mp3': command.extend(['--audio-quality', '192K'])
            if options['embed_thumbnail']: command.append('--embed-thumbnail')
            command.append(url)
            
            popen_kwargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT, 'text': True, 'encoding': 'utf-8', 'errors': 'replace', 'bufsize': 1}
            if sys.platform == 'win32':
                popen_kwargs['creationflags'] = SUBPROCESS_CREATION_FLAGS
            else:
                popen_kwargs['preexec_fn'] = os.setsid
            
            with self.active_processes_lock:
                if self.stop_event.is_set(): return
                process = subprocess.Popen(command, **popen_kwargs)
                self.active_processes[job_id] = process
            
            for line in iter(process.stdout.readline, ''):
                if self.stop_event.is_set(): break
                clean_line = line.strip()
                self.gui_queue.put(('log', f"[{job_id}] {clean_line}"))
                if clean_line.startswith('ERROR:'): error_message = clean_line[6:].strip()
                status_match = re.search(r'\[(\w+)\]', clean_line)
                if status_match:
                    status_key = status_match.group(1).lower()
                    status_map = {'merger': 'Merging...', 'extractaudio': 'Extracting Audio...', 'embedthumbnail': 'Embedding...', 'fixupm4a': 'Fixing M4a...', 'metadata': 'Writing Metadata...'}
                    if status_key in status_map: self.gui_queue.put(('update_job', (job_id, 'status', status_map[status_key])))
                percentage = None
                if clean_line.startswith('PROGRESS::'):
                    try: percentage = float(clean_line.split('::', 1)[1].strip().rstrip('%'))
                    except (IndexError, ValueError): pass
                elif '[download]' in clean_line:
                    match = re.search(r'(\d+\.?\d*)%', clean_line)
                    if match:
                        try: percentage = float(match.group(1))
                        except ValueError: pass
                if percentage is not None: self.gui_queue.put(('update_job', (job_id, 'progress', f"{percentage:.1f}%")))
            
            process.stdout.close(); return_code = process.wait()
            if self.stop_event.is_set(): return
            if return_code == 0: final_status = 'Completed'
            elif error_message: final_status = f"Failed: {error_message[:60]}"
        except Exception as e:
            final_status, error_message = "Error", str(e)
            self.gui_queue.put(('log', f"[{job_id}] Exception: {e}"))
        finally:
            with self.active_processes_lock:
                if job_id in self.active_processes: del self.active_processes[job_id]
            if not self.stop_event.is_set():
                with self.stats_lock: self.completed_jobs += 1
                self.gui_queue.put(('done', (job_id, final_status)))

# --- Main Application Class ---

class YTDlpDownloaderApp:
    """The main application class, handling the Tkinter GUI and event loop."""
    MAX_LOG_LINES = 2000

    def __init__(self, root):
        self.root = root
        self.root.title("Multiyt-dlp"); self.root.geometry("850x780")
        try: self.root.iconbitmap(resource_path('icon.ico'))
        except tk.TclError: print("Warning: Could not load 'icon.ico'.")
        
        self.config_manager = ConfigManager(CONFIG_FILE)
        self.config = self.config_manager.load()
        
        self.max_concurrent_downloads = self.config.get('max_concurrent_downloads')
        self.filename_template = tk.StringVar(value=self.config.get('filename_template'))
        self.gui_queue = queue.Queue()
        self.dependency_progress_win, self.settings_win = None, None
        self.is_downloading, self.is_updating_dependency, self.is_destroyed = False, False, False
        self.pending_download_task = None
        self.yt_dlp_version_var = tk.StringVar(value="Checking...")
        self.ffmpeg_status_var = tk.StringVar(value="Checking...")
        
        self.dep_manager = DependencyManager(self.gui_queue)
        self.download_manager = DownloadManager(self.gui_queue)
        
        self.create_widgets()
        self.log(f"Config path: {CONFIG_FILE}")
        self.log(f"Found yt-dlp: {self.dep_manager.yt_dlp_path or 'Not Found'}")
        self.log(f"Found FFmpeg: {self.dep_manager.ffmpeg_path or 'Not Found'}")
        
        if not self.dep_manager.yt_dlp_path:
            self.root.after(100, lambda: self.initiate_dependency_download('yt-dlp'))
        
        self.process_gui_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.set_status("Ready")

    def on_closing(self):
        if self.is_downloading and not messagebox.askyesno("Confirm Exit", "Downloads are in progress. Are you sure you want to exit?"):
            return
        
        if self.is_downloading:
            self.download_manager.stop_all_downloads()
        else:
            self.download_manager.current_output_path = self.output_path_var.get()
            self.download_manager._cleanup_temporary_files()

        self.config.update({
            'download_type': self.download_type_var.get(), 'video_resolution': self.video_resolution_var.get(),
            'audio_format': self.audio_format_var.get(), 'embed_thumbnail': self.embed_thumbnail_var.get(),
            'filename_template': self.filename_template.get(), 'max_concurrent_downloads': self.max_concurrent_downloads,
            'last_output_path': self.output_path_var.get()
        })
        self.config_manager.save(self.config)
        self.is_destroyed = True
        self.root.destroy()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10"); main_frame.pack(fill=tk.BOTH, expand=True)
        input_frame = ttk.LabelFrame(main_frame, text="Inputs", padding="10"); input_frame.pack(fill=tk.X, pady=5); input_frame.columnconfigure(1, weight=1)
        ttk.Label(input_frame, text="Video/Playlist URLs\n(one per line):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.url_text = tk.Text(input_frame, height=5, width=80); self.url_text.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Label(input_frame, text="Output Folder:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.output_path_var = tk.StringVar(value=self.config.get('last_output_path'))
        ttk.Entry(input_frame, textvariable=self.output_path_var, state='readonly').grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        self.browse_button = ttk.Button(input_frame, text="Browse...", command=self.browse_output_path); self.browse_button.grid(row=1, column=2, padx=5, pady=5)
        
        self.options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10"); self.options_frame.pack(fill=tk.X, pady=5)
        self.download_type_var = tk.StringVar(value=self.config.get('download_type')); self.download_type_var.trace_add("write", self.update_options_ui)
        ttk.Radiobutton(self.options_frame, text="Video", variable=self.download_type_var, value="video").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(self.options_frame, text="Audio", variable=self.download_type_var, value="audio").pack(side=tk.LEFT, padx=10)
        self.dynamic_options_frame = ttk.Frame(self.options_frame); self.dynamic_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20)
        
        self.video_options_frame = ttk.Frame(self.dynamic_options_frame)
        ttk.Label(self.video_options_frame, text="Resolution:").pack(side=tk.LEFT, padx=(0, 5)); self.video_resolution_var = tk.StringVar(value=self.config.get('video_resolution'))
        self.video_resolution_combo = ttk.Combobox(self.video_options_frame, textvariable=self.video_resolution_var, values=["Best", "1080", "720", "480"], state="readonly", width=10); self.video_resolution_combo.pack(side=tk.LEFT)
        
        self.audio_options_frame = ttk.Frame(self.dynamic_options_frame)
        ttk.Label(self.audio_options_frame, text="Format:").pack(side=tk.LEFT, padx=(0, 5)); self.audio_format_var = tk.StringVar(value=self.config.get('audio_format'))
        self.audio_format_combo = ttk.Combobox(self.audio_options_frame, textvariable=self.audio_format_var, values=["best", "mp3", "m4a", "flac", "wav"], state="readonly", width=10); self.audio_format_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.embed_thumbnail_var = tk.BooleanVar(value=self.config.get('embed_thumbnail')); self.thumbnail_check = ttk.Checkbutton(self.audio_options_frame, text="Embed Thumbnail", variable=self.embed_thumbnail_var); self.thumbnail_check.pack(side=tk.LEFT)
        self.update_options_ui()

        action_frame = ttk.Frame(main_frame); action_frame.pack(fill=tk.X, pady=10); action_frame.columnconfigure(0, weight=1)
        self.download_button = ttk.Button(action_frame, text="Add URLs to Queue & Download", command=self.queue_downloads); self.download_button.grid(row=0, column=0, sticky=tk.EW)
        self.stop_button = ttk.Button(action_frame, text="Stop All", command=self.stop_downloads, state='disabled'); self.stop_button.grid(row=0, column=1, padx=5)
        self.clear_button = ttk.Button(action_frame, text="Clear Completed", command=self.clear_completed_list); self.clear_button.grid(row=0, column=2, padx=5)
        self.settings_button = ttk.Button(action_frame, text="Settings", command=self.open_settings_window); self.settings_button.grid(row=0, column=3, padx=(5, 0))

        progress_frame = ttk.LabelFrame(main_frame, text="Progress & Log", padding="10"); progress_frame.pack(fill=tk.BOTH, expand=True, pady=5); progress_frame.rowconfigure(1, weight=1); progress_frame.columnconfigure(0, weight=1)
        overall_progress_frame = ttk.Frame(progress_frame); overall_progress_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        self.overall_progress_label = ttk.Label(overall_progress_frame, text="Overall Progress: 0 / 0"); self.overall_progress_label.pack(side=tk.LEFT, padx=5)
        self.overall_progress_bar = ttk.Progressbar(overall_progress_frame, orient='horizontal', mode='determinate'); self.overall_progress_bar.pack(fill=tk.X, expand=True)

        tree_frame = ttk.Frame(progress_frame); tree_frame.grid(row=1, column=0, sticky='nsew', pady=5)
        self.downloads_tree = ttk.Treeview(tree_frame, columns=('url', 'status', 'progress'), show='headings'); self.downloads_tree.heading('url', text='URL'); self.downloads_tree.heading('status', text='Status'); self.downloads_tree.heading('progress', text='Progress'); self.downloads_tree.column('url', width=450); self.downloads_tree.column('status', width=100, anchor=tk.CENTER); self.downloads_tree.column('progress', width=100, anchor=tk.CENTER)
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.downloads_tree.yview); self.downloads_tree.configure(yscrollcommand=tree_scrollbar.set); tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y); self.downloads_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.downloads_tree.tag_configure('failed', background='misty rose'); self.downloads_tree.tag_configure('completed', background='pale green'); self.downloads_tree.tag_configure('cancelled', background='light grey')
        self.tree_context_menu = tk.Menu(self.root, tearoff=0); self.tree_context_menu.add_command(label="Open Output Folder", command=self.open_output_folder); self.tree_context_menu.add_command(label="Retry Failed Download(s)", command=self.retry_failed_download)
        self.downloads_tree.bind("<Button-3>", self.show_context_menu) # Right-click
        if sys.platform == "darwin": self.downloads_tree.bind("<Button-2>", self.show_context_menu); self.downloads_tree.bind("<Control-Button-1>", self.show_context_menu)
        
        self.log_text = scrolledtext.ScrolledText(progress_frame, wrap=tk.WORD, height=10, state='disabled'); self.log_text.grid(row=2, column=0, sticky='ew', pady=5)

        status_bar_frame = ttk.Frame(self.root, relief=tk.SUNKEN); status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=2)
        self.status_label = ttk.Label(status_bar_frame, text="Ready"); self.status_label.pack(side=tk.LEFT, padx=5)

    def set_status(self, message): self.status_label.config(text=message)
    def update_options_ui(self, *args):
        self.video_options_frame.pack_forget(); self.audio_options_frame.pack_forget()
        if self.download_type_var.get() == "video": self.video_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        elif self.download_type_var.get() == "audio": self.audio_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def initiate_dependency_download(self, dep_type):
        if self.is_updating_dependency: return
        msg_map = {'yt-dlp': "yt-dlp not found.", 'ffmpeg': "FFmpeg is required for audio conversion but not found."}
        if messagebox.askyesno(f"{dep_type.upper()} Not Found", f"{msg_map[dep_type]}\n\nDownload the latest version?"):
            self.is_updating_dependency = True; self.toggle_ui_state(False); self.show_dependency_progress_window(f"Downloading {dep_type.upper()}")
            if dep_type == 'yt-dlp': self.dep_manager.install_or_update_yt_dlp()
            else: self.dep_manager.download_ffmpeg()
        elif dep_type == 'yt-dlp':
            messagebox.showerror("Critical Error", "yt-dlp is required. Exiting."); self.is_destroyed = True; self.root.after(1, self.root.destroy)

    def queue_downloads(self):
        if self.is_downloading or not self.dep_manager.yt_dlp_path: return
        
        urls_raw = self.url_text.get(1.0, tk.END).strip()
        if not urls_raw:
            messagebox.showwarning("Input Error", "Please enter at least one URL.")
            return

        valid_urls = [u for url in urls_raw.splitlines() if (u := url.strip()) and urllib.parse.urlparse(u).scheme]
        if not valid_urls:
            messagebox.showwarning("Input Error", "No valid URLs provided.")
            return
        
        output_path = self.output_path_var.get()
        if not os.path.isdir(output_path):
            if not messagebox.askyesno("Create Directory?", f"Output directory does not exist:\n{output_path}\nCreate it?"): return
            try: os.makedirs(output_path, exist_ok=True)
            except OSError as e: messagebox.showerror("Error", f"Failed to create directory: {e}"); return
        try:
            with open(os.path.join(output_path, f".writetest_{os.getpid()}"), 'w') as f: f.write('test')
            os.remove(os.path.join(output_path, f".writetest_{os.getpid()}"))
        except (IOError, OSError) as e: messagebox.showerror("Permission Error", f"Cannot write to directory:\n{e}"); return
        
        options = {'output_path': output_path, 'filename_template': self.filename_template.get(), 'download_type': self.download_type_var.get(), 'video_resolution': self.video_resolution_var.get(), 'audio_format': self.audio_format_var.get(), 'embed_thumbnail': self.embed_thumbnail_var.get()}
        
        if self.download_type_var.get() == 'audio' and not self.dep_manager.ffmpeg_path:
            self.pending_download_task = (valid_urls, options)
            self.url_text.delete(1.0, tk.END)
            self.log("FFmpeg is required. Attempting to download it now...")
            self.log("Your downloads will begin automatically after installation.")
            self.initiate_dependency_download('ffmpeg')
            return
        
        self.update_button_states(is_downloading=True); self.set_status("Processing URLs..."); self.toggle_url_input_state(False)
        self.url_text.delete(1.0, tk.END)
        self.log("--- Queuing new URLs ---")
        self.download_manager.set_config(self.max_concurrent_downloads, self.dep_manager.yt_dlp_path, self.dep_manager.ffmpeg_path)
        self.download_manager.start_downloads(valid_urls, options)

    def stop_downloads(self):
        if not self.is_downloading: return
        if messagebox.askyesno("Confirm Stop", "Stop all current and queued downloads?"):
            self.set_status("Stopping all downloads..."); self.download_manager.stop_all_downloads(); self.update_button_states(is_downloading=False)

    def clear_completed_list(self):
        to_remove = [item for item in self.downloads_tree.get_children() if any(tag in self.downloads_tree.item(item, 'tags') for tag in ['completed', 'failed', 'cancelled'])]
        for item in to_remove: self.downloads_tree.delete(item)
        self.log("Cleared finished items from the list.")

    def process_gui_queue(self):
        try:
            while True:
                msg_type, value = self.gui_queue.get_nowait()
                if msg_type == 'log': self.log(value)
                elif msg_type == 'add_job':
                    job_id, url, status, progress = value
                    self.downloads_tree.insert('', 'end', iid=job_id, values=(url, status, progress)); self.update_overall_progress()
                elif msg_type == 'update_job' and self.downloads_tree.exists(value[0]): self.downloads_tree.set(value[0], value[1], value[2])
                elif msg_type == 'done' and self.downloads_tree.exists(value[0]):
                    job_id, status = value
                    tags = ('cancelled',) if status == 'Cancelled' else ('completed',) if status == 'Completed' else ('failed',)
                    if status == 'Completed': self.downloads_tree.set(job_id, 'progress', '100.0%')
                    self.downloads_tree.item(job_id, tags=tags); self.downloads_tree.set(job_id, 'status', status); self.update_overall_progress()
                elif msg_type == 'reset_progress': self.update_overall_progress(reset=True)
                elif msg_type == 'dependency_progress': self.update_dependency_progress(value)
                elif msg_type == 'dependency_done': self.handle_dependency_result(value)
                elif msg_type == 'set_yt_dlp_version': self.yt_dlp_version_var.set(value)
                elif msg_type == 'set_ffmpeg_status': self.ffmpeg_status_var.set(value)
                elif msg_type == 'url_processing_done': self.toggle_url_input_state(True)
        except queue.Empty:
            if not self.is_destroyed: self.root.after(100, self.process_gui_queue)

    def handle_dependency_result(self, result):
        self.close_dependency_progress_window(); self.toggle_ui_state(True)
        dep_type = result.get('type')
        if result.get('success'): messagebox.showinfo("Success", f"{dep_type.upper()} downloaded successfully.")
        else: messagebox.showerror(f"Download Failed", f"An error occurred: {result.get('error')}")
        
        if dep_type == 'yt-dlp':
            if not self.dep_manager.find_yt_dlp(): self.is_destroyed = True; self.root.destroy()
            else: self.check_yt_dlp_version()
        elif dep_type == 'ffmpeg':
            self.check_ffmpeg_status()

        if dep_type == 'ffmpeg' and result.get('success') and self.pending_download_task:
            self.log("FFmpeg installed. Resuming queued downloads...")
            urls, options = self.pending_download_task
            self.pending_download_task = None
            self.update_button_states(is_downloading=True)
            self.toggle_url_input_state(False)
            self.download_manager.set_config(self.max_concurrent_downloads, self.dep_manager.yt_dlp_path, self.dep_manager.ffmpeg_path)
            self.download_manager.start_downloads(urls, options)
            
        if self.is_updating_dependency:
            self.is_updating_dependency = False; self.toggle_update_buttons(True)

    def update_overall_progress(self, reset=False):
        if reset:
            self.overall_progress_label.config(text="Overall Progress: 0 / 0")
            self.overall_progress_bar['value'] = 0
            self.set_status("Ready")
            return

        completed, total = self.download_manager.get_stats()
        self.overall_progress_label.config(text=f"Overall Progress: {completed} / {total}")
        if total > 0:
            self.overall_progress_bar['value'] = (completed / total) * 100
            if completed < total: self.set_status(f"Downloading... ({completed}/{total})")
            else: self.set_status(f"All downloads complete! ({completed}/{total})")
        
        if total > 0 and completed >= total and self.is_downloading:
            self.gui_queue.put(('log', "\n--- All queued downloads are complete! ---")); self.update_button_states(is_downloading=False)

    def update_button_states(self, is_downloading):
        self.is_downloading = is_downloading
        state = 'disabled' if is_downloading else 'normal'
        self.download_button.config(state=state); self.settings_button.config(state=state); self.stop_button.config(state='normal' if is_downloading else 'disabled')

    def toggle_ui_state(self, enabled):
        state, combo_state = ('normal' if enabled else 'disabled'), ('readonly' if enabled else 'disabled')
        self.toggle_url_input_state(enabled)
        for child in self.options_frame.winfo_children():
            if isinstance(child, (ttk.Radiobutton, ttk.Checkbutton)): child.config(state=state)
        self.video_resolution_combo.config(state=combo_state); self.audio_format_combo.config(state=combo_state)

    def toggle_url_input_state(self, enabled):
        state = 'normal' if enabled else 'disabled'
        self.url_text.config(state=state); self.browse_button.config(state=state); self.download_button.config(state=state)

    def show_dependency_progress_window(self, title):
        if self.dependency_progress_win and self.dependency_progress_win.winfo_exists(): return
        self.dependency_progress_win = tk.Toplevel(self.root); self.dependency_progress_win.title(title); self.dependency_progress_win.geometry("400x120"); self.dependency_progress_win.resizable(False, False); self.dependency_progress_win.transient(self.root); self.dependency_progress_win.protocol("WM_DELETE_WINDOW", lambda: None)
        self.dep_progress_label = tk.Label(self.dependency_progress_win, text="Initializing...", pady=10); self.dep_progress_label.pack(fill=tk.X, padx=10)
        self.dep_progress_bar = ttk.Progressbar(self.dependency_progress_win, orient='horizontal', length=380); self.dep_progress_bar.pack(pady=10)

    def update_dependency_progress(self, data):
        if not self.dependency_progress_win or not self.dependency_progress_win.winfo_exists(): self.show_dependency_progress_window(f"Downloading {data.get('type')}")
        self.dep_progress_label.config(text=data.get('text', ''))
        if data.get('status') == 'indeterminate': self.dep_progress_bar.config(mode='indeterminate'); self.dep_progress_bar.start(10)
        else: self.dep_progress_bar.stop(); self.dep_progress_bar.config(mode='determinate'); self.dep_progress_bar['value'] = data.get('value', 0)

    def close_dependency_progress_window(self):
        if self.dependency_progress_win: self.dep_progress_bar.stop(); self.dependency_progress_win.destroy(); self.dependency_progress_win = None

    def open_settings_window(self):
        if self.settings_win and self.settings_win.winfo_exists(): self.settings_win.lift(); return
        self.settings_win = tk.Toplevel(self.root); self.settings_win.title("Settings"); self.settings_win.geometry("600x400"); self.settings_win.resizable(False, False); self.settings_win.transient(self.root)
        try: self.settings_win.iconbitmap(resource_path('icon.ico'))
        except tk.TclError: pass
        settings_frame = ttk.Frame(self.settings_win, padding="10"); settings_frame.pack(fill=tk.BOTH, expand=True)
        concurrent_var, temp_filename_template = tk.IntVar(value=self.max_concurrent_downloads), tk.StringVar(value=self.filename_template.get())
        ttk.Label(settings_frame, text="Max Concurrent Downloads:").grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)
        ttk.Spinbox(settings_frame, from_=1, to=20, textvariable=concurrent_var, width=5).grid(row=0, column=1, padx=5, pady=10, sticky=tk.W)
        ttk.Label(settings_frame, text="Filename Template:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(settings_frame, textvariable=temp_filename_template, width=50).grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        help_text = "Must include %(title)s or %(id)s. Cannot contain / \\ .. or be an absolute path."
        ttk.Label(settings_frame, text=help_text, font=("TkDefaultFont", 8, "italic")).grid(row=2, column=1, sticky=tk.W, padx=5)
        
        update_frame = ttk.LabelFrame(settings_frame, text="Dependencies", padding=10); update_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=15); update_frame.columnconfigure(1, weight=1)
        ttk.Label(update_frame, text="yt-dlp:").grid(row=0, column=0, sticky=tk.W, padx=5); ttk.Label(update_frame, textvariable=self.yt_dlp_version_var).grid(row=0, column=1, sticky=tk.W, padx=5); self.check_yt_dlp_version()
        ttk.Label(update_frame, text="FFmpeg:").grid(row=1, column=0, sticky=tk.W, padx=5); ttk.Label(update_frame, textvariable=self.ffmpeg_status_var, wraplength=400).grid(row=1, column=1, sticky=tk.W, padx=5); self.check_ffmpeg_status()
        update_buttons_frame = ttk.Frame(update_frame); update_buttons_frame.grid(row=2, column=0, columnspan=2, pady=(10,0))
        self.yt_dlp_update_button = ttk.Button(update_buttons_frame, text="Update yt-dlp", command=self.start_yt_dlp_update); self.yt_dlp_update_button.pack(side=tk.LEFT, padx=5)
        self.ffmpeg_update_button = ttk.Button(update_buttons_frame, text="Download/Update FFmpeg", command=self.start_ffmpeg_update); self.ffmpeg_update_button.pack(side=tk.LEFT, padx=5)
        
        def save_and_close():
            if self.is_updating_dependency: messagebox.showwarning("Busy", "Cannot close settings while updating.", parent=self.settings_win); return
            new_concurrent_val = concurrent_var.get(); new_template = temp_filename_template.get().strip()
            if not (1 <= new_concurrent_val <= 20): messagebox.showwarning("Invalid Value", "Concurrent downloads must be between 1 and 20.", parent=self.settings_win); return
            if not new_template or not re.search(r'%\((title|id)', new_template): messagebox.showwarning("Invalid Template", "Template must include %(title)s or %(id)s.", parent=self.settings_win); return
            if any(c in new_template for c in '/\\') or '..' in new_template or os.path.isabs(new_template): messagebox.showerror("Invalid Template", "Template cannot contain path separators ('/', '\\'), '..', or be absolute.", parent=self.settings_win); return
            
            self.max_concurrent_downloads = new_concurrent_val
            self.filename_template.set(new_template)
            self.config['max_concurrent_downloads'] = self.max_concurrent_downloads
            self.config['filename_template'] = self.filename_template.get()
            self.config_manager.save(self.config)
            self.settings_win.destroy()

        buttons_frame = ttk.Frame(settings_frame); buttons_frame.grid(row=4, column=0, columnspan=2, pady=15, sticky=tk.E)
        ttk.Button(buttons_frame, text="Save", command=save_and_close).pack(side=tk.LEFT, padx=5); ttk.Button(buttons_frame, text="Cancel", command=self.settings_win.destroy).pack(side=tk.LEFT); self.settings_win.protocol("WM_DELETE_WINDOW", self.settings_win.destroy)

    def check_yt_dlp_version(self):
        self.yt_dlp_version_var.set("Checking...")
        threading.Thread(target=lambda: self.gui_queue.put(('set_yt_dlp_version', self.dep_manager.get_version(self.dep_manager.yt_dlp_path))), daemon=True, name="yt-dlp-Version-Check").start()
    
    def check_ffmpeg_status(self):
        self.ffmpeg_status_var.set("Checking...")
        threading.Thread(target=lambda: self.gui_queue.put(('set_ffmpeg_status', self.dep_manager.get_version(self.dep_manager.ffmpeg_path))), daemon=True, name="FFmpeg-Version-Check").start()

    def toggle_update_buttons(self, enabled):
        state = 'normal' if enabled else 'disabled'
        for btn in [getattr(self, 'yt_dlp_update_button', None), getattr(self, 'ffmpeg_update_button', None)]:
            if btn and btn.winfo_exists(): btn.config(state=state)

    def start_yt_dlp_update(self): self._start_dep_update("yt-dlp", "Download latest yt-dlp?")
    def start_ffmpeg_update(self): self._start_dep_update("ffmpeg", "Download latest FFmpeg? (Large file)")
    def _start_dep_update(self, dep_type, message):
        if self.is_updating_dependency: return
        if messagebox.askyesno(f"Confirm Update", message, parent=self.settings_win or self.root):
            self.is_updating_dependency = True; self.toggle_update_buttons(False); self.show_dependency_progress_window(f"Updating {dep_type}"); getattr(self.dep_manager, f'{"install_or_update" if dep_type == "yt-dlp" else "download"}_{dep_type}')()

    def show_context_menu(self, event):
        selection = self.downloads_tree.selection()
        if not selection:
            item_id = self.downloads_tree.identify_row(event.y)
            if not item_id: return
            self.downloads_tree.selection_set(item_id)
            selection = (item_id,)
        
        is_failed = any('failed' in self.downloads_tree.item(s_item_id, 'tags') for s_item_id in selection)
        self.tree_context_menu.entryconfig("Retry Failed Download(s)", state='normal' if is_failed else 'disabled')
        self.tree_context_menu.post(event.x_root, event.y_root)

    def open_output_folder(self):
        path = self.output_path_var.get()
        if not os.path.isdir(path): messagebox.showerror("Error", f"Folder does not exist:\n{path}"); return
        try:
            if sys.platform == 'win32': os.startfile(path)
            elif sys.platform == 'darwin': subprocess.run(['open', path], check=True)
            else: subprocess.run(['xdg-open', path], check=True)
        except Exception as e: messagebox.showerror("Error", f"Failed to open folder:\n{e}")

    def retry_failed_download(self):
        to_retry = [(self.downloads_tree.item(item, 'values')[0], item) for item in self.downloads_tree.selection() if 'failed' in self.downloads_tree.item(item, 'tags')]
        if not to_retry: return
        for _, item_id in to_retry: self.downloads_tree.delete(item_id)
        options = {'output_path': self.output_path_var.get(), 'filename_template': self.filename_template.get(), 'download_type': self.download_type_var.get(), 'video_resolution': self.video_resolution_var.get(), 'audio_format': self.audio_format_var.get(), 'embed_thumbnail': self.embed_thumbnail_var.get()}
        self.update_button_states(is_downloading=True); self.download_manager.add_jobs([url for url, _ in to_retry], options)

    def browse_output_path(self):
        path = filedialog.askdirectory(initialdir=self.output_path_var.get(), title="Select Output Folder")
        if path: self.output_path_var.set(path)

    def log(self, message):
        if self.is_destroyed: return
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + '\n')
        num_lines = int(self.log_text.index('end-1c').split('.')[0])
        if num_lines > self.MAX_LOG_LINES:
            self.log_text.delete('1.0', f'{num_lines - self.MAX_LOG_LINES + 1}.0')
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

if __name__ == "__main__":
    root = tk.Tk()
    app = YTDlpDownloaderApp(root)
    root.mainloop()
