import os
import sys
import shutil
import threading
import subprocess
import urllib.parse
import zipfile
import tarfile
import time
import tempfile
import queue
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

from .constants import (
    YT_DLP_URLS, FFMPEG_URLS, REQUEST_HEADERS, REQUEST_TIMEOUTS, APP_PATH, SUBPROCESS_CREATION_FLAGS
)
from .exceptions import DownloadCancelledError


class DependencyManager:
    """Manages the discovery, download, and updates for yt-dlp and FFmpeg."""
    CHUNKED_DOWNLOAD_THRESHOLD = 20 * 1024 * 1024  # 20 MB
    DOWNLOAD_CHUNKS = 8
    DOWNLOAD_RETRY_ATTEMPTS = 3

    def __init__(self, gui_queue: queue.Queue):
        self.gui_queue = gui_queue
        self.logger = logging.getLogger(__name__)
        self.yt_dlp_path = self.find_yt_dlp()
        self.ffmpeg_path = self.find_ffmpeg()
        self.stop_event = threading.Event()

    def cancel_download(self):
        """Signals the download process to stop."""
        self.logger.info("Cancellation signal sent to dependency downloader.")
        self.stop_event.set()

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
        except Exception:
            self.logger.exception(f"Error checking version for {executable_path}")
            return "Error checking version"

    def _download_file_with_progress(self, url, save_path, dep_type):
        self.gui_queue.put(('dependency_progress', {'type': dep_type, 'status': 'determinate', 'text': 'Preparing download...', 'value': 0}))
        
        total_size = 0
        supports_ranges = False
        try:
            with requests.head(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUTS[0], allow_redirects=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                supports_ranges = r.headers.get('accept-ranges', '').lower() == 'bytes'
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"HEAD request failed: {e}. Proceeding with single-stream download.")

        use_chunked = total_size > self.CHUNKED_DOWNLOAD_THRESHOLD and supports_ranges
        
        if use_chunked:
            try:
                self.logger.info(f"Starting chunked download for {dep_type} ({total_size/1024/1024:.1f} MB)...")
                self._download_file_chunked(url, save_path, total_size, dep_type)
            except Exception as e:
                if isinstance(e, DownloadCancelledError): raise
                self.logger.exception(f"Chunked download failed: {e}. Falling back to single-stream.")
                if os.path.exists(save_path):
                    try: os.remove(save_path)
                    except OSError: pass
                self._download_file_single_stream(url, save_path, dep_type)
        else:
            log_msg = f"Starting single-stream download for {dep_type}."
            if total_size > 0 and total_size <= self.CHUNKED_DOWNLOAD_THRESHOLD: log_msg += " (File is small)"
            if total_size > 0 and not supports_ranges: log_msg += " (Server doesn't support ranged requests)"
            self.logger.info(log_msg)
            self._download_file_single_stream(url, save_path, dep_type)

        if self.stop_event.is_set(): raise DownloadCancelledError("Download cancelled after completion.")

        self.gui_queue.put(('dependency_progress', {
            'type': dep_type, 'status': 'determinate',
            'text': 'Download complete. Preparing...', 'value': 100
        }))

    def _download_file_single_stream(self, url, save_path, dep_type):
        for attempt in range(self.DOWNLOAD_RETRY_ATTEMPTS):
            if self.stop_event.is_set(): raise DownloadCancelledError("Download cancelled before starting.")
            try:
                with requests.get(url, stream=True, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUTS) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get('Content-Length', 0))
                    if total_size <= 0:
                        self.gui_queue.put(('dependency_progress', {'type': dep_type, 'status': 'indeterminate', 'text': f'Downloading {dep_type}... (Size unknown)'}))
                    
                    bytes_downloaded, chunk_size = 0, 8192
                    start_time = time.time()
                    with open(save_path, 'wb') as f_out:
                        for chunk in r.iter_content(chunk_size=chunk_size):
                            if self.stop_event.is_set(): raise DownloadCancelledError("Download cancelled during transfer.")
                            f_out.write(chunk)
                            bytes_downloaded += len(chunk)
                            if total_size > 0:
                                progress = (bytes_downloaded / total_size) * 100
                                speed = (bytes_downloaded / (time.time() - start_time)) / 1024 / 1024 if time.time() > start_time else 0
                                text = f'Downloading... {bytes_downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB ({speed:.1f} MB/s)'
                                self.gui_queue.put(('dependency_progress', {'type': dep_type, 'status': 'determinate', 'text': text, 'value': progress}))
                return
            except DownloadCancelledError: raise
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Single-stream error on attempt {attempt + 1}: {e}")
                if attempt < self.DOWNLOAD_RETRY_ATTEMPTS - 1: time.sleep(2 ** attempt)
                else: raise e
    
    def _download_file_chunked(self, url, save_path, total_size, dep_type):
        chunk_size = total_size // self.DOWNLOAD_CHUNKS
        ranges = [(i * chunk_size, (i + 1) * chunk_size - 1) for i in range(self.DOWNLOAD_CHUNKS - 1)]
        ranges.append(((self.DOWNLOAD_CHUNKS - 1) * chunk_size, total_size - 1))

        with tempfile.TemporaryDirectory(prefix="multiyt-dlp-") as temp_dir:
            progress, progress_lock, start_time = [0] * self.DOWNLOAD_CHUNKS, threading.Lock(), time.time()
            with ThreadPoolExecutor(max_workers=self.DOWNLOAD_CHUNKS) as executor:
                futures = {executor.submit(self._download_chunk, url, os.path.join(temp_dir, f'chunk_{i}'), ranges[i], i, progress, progress_lock) for i in range(self.DOWNLOAD_CHUNKS)}
                while any(f.running() for f in futures):
                    if self.stop_event.is_set(): break
                    with progress_lock: bytes_downloaded = sum(progress)
                    if total_size > 0:
                        percent = (bytes_downloaded / total_size) * 100
                        speed = (bytes_downloaded / (time.time() - start_time)) / 1024 / 1024 if time.time() > start_time else 0
                        text = f'Downloading... {bytes_downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB ({speed:.1f} MB/s)'
                        self.gui_queue.put(('dependency_progress', {'type': dep_type, 'status': 'determinate', 'text': text, 'value': percent}))
                    time.sleep(0.5)
                for future in as_completed(futures): future.result()
            
            if self.stop_event.is_set(): raise DownloadCancelledError("Download cancelled before file assembly.")
            self.gui_queue.put(('dependency_progress', {'type': dep_type, 'status': 'indeterminate', 'text': 'Assembling file...'}))
            self._assemble_chunks(save_path, temp_dir)

    def _download_chunk(self, url, chunk_path, byte_range, chunk_idx, progress, lock):
        for attempt in range(self.DOWNLOAD_RETRY_ATTEMPTS):
            if self.stop_event.is_set(): raise DownloadCancelledError(f"Chunk {chunk_idx} cancelled.")
            try:
                headers = REQUEST_HEADERS.copy()
                headers['Range'] = f'bytes={byte_range[0]}-{byte_range[1]}'
                bytes_dl = 0
                with requests.get(url, headers=headers, stream=True, timeout=REQUEST_TIMEOUTS) as r:
                    r.raise_for_status()
                    with open(chunk_path, 'wb') as f:
                        for part in r.iter_content(chunk_size=8192):
                            if self.stop_event.is_set(): raise DownloadCancelledError(f"Chunk {chunk_idx} cancelled.")
                            f.write(part)
                            bytes_dl += len(part)
                            with lock: progress[chunk_idx] = bytes_dl
                return
            except DownloadCancelledError: raise
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error on chunk {chunk_idx}, attempt {attempt + 1}: {e}")
                if attempt < self.DOWNLOAD_RETRY_ATTEMPTS - 1: time.sleep(2 ** attempt)
                else: raise Exception(f"Failed to download chunk {chunk_idx}.") from e

    def _assemble_chunks(self, save_path, temp_dir):
        with open(save_path, 'wb') as f_out:
            for i in range(self.DOWNLOAD_CHUNKS):
                with open(os.path.join(temp_dir, f'chunk_{i}'), 'rb') as f_in:
                    shutil.copyfileobj(f_in, f_out)

    def install_or_update_yt_dlp(self):
        threading.Thread(target=self._install_or_update_yt_dlp_thread, daemon=True, name="yt-dlp-Installer").start()

    def _install_or_update_yt_dlp_thread(self):
        self.stop_event.clear()
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
        except DownloadCancelledError:
            self.logger.info("yt-dlp download cancelled by user.")
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': "Download cancelled by user."}))
        except requests.exceptions.RequestException as e:
            self.logger.exception("Network error during yt-dlp download.")
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': f"Network error: {e}"}))
        except Exception:
            self.logger.exception("An unexpected error occurred during yt-dlp download.")
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': "An unexpected error occurred."}))

    def download_ffmpeg(self):
        threading.Thread(target=self._download_ffmpeg_thread, daemon=True, name="FFmpeg-Installer").start()

    def _download_ffmpeg_thread(self):
        self.stop_event.clear()
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
            except DownloadCancelledError:
                self.logger.info("FFmpeg download cancelled by user.")
                self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': "Download cancelled by user."}))
            except requests.exceptions.RequestException as e:
                self.logger.exception("Network error during FFmpeg download.")
                self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': f"Network error: {e}"}))
            except Exception:
                self.logger.exception("An unexpected error occurred during FFmpeg download.")
                self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': "An unexpected error occurred."}))