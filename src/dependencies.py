"""Manages the discovery, download, and updates for yt-dlp and FFmpeg."""
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
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from typing import Optional, List, Tuple

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
        """
        Initializes the DependencyManager.

        Args:
            gui_queue: The queue for sending progress updates to the GUI.
        """
        self.gui_queue = gui_queue
        self.logger = logging.getLogger(__name__)
        self.yt_dlp_path: Optional[Path] = self.find_yt_dlp()
        self.ffmpeg_path: Optional[Path] = self.find_ffmpeg()
        self.stop_event = threading.Event()

    def cancel_download(self):
        """Signals the download process to stop."""
        self.logger.info("Cancellation signal sent to dependency downloader.")
        self.stop_event.set()

    def find_yt_dlp(self) -> Optional[Path]:
        """
        Finds the yt-dlp executable.

        Returns:
            A Path object to the executable, or None if not found.
        """
        self.yt_dlp_path = self._find_executable('yt-dlp')
        return self.yt_dlp_path

    def find_ffmpeg(self) -> Optional[Path]:
        """
        Finds the ffmpeg executable.

        Returns:
            A Path object to the executable, or None if not found.
        """
        self.ffmpeg_path = self._find_executable('ffmpeg')
        return self.ffmpeg_path

    def _find_executable(self, name: str) -> Optional[Path]:
        """
        Finds an executable, preferring a locally managed one.

        Args:
            name: The name of the executable (e.g., 'yt-dlp').

        Returns:
            A Path object to the executable, or None if not found.
        """
        local_path = APP_PATH / (f'{name}.exe' if sys.platform == 'win32' else name)
        if local_path.exists():
            return local_path

        path_in_system = shutil.which(name)
        if path_in_system:
            return Path(path_in_system)

        return None

    def get_version(self, executable_path: Optional[Path]) -> str:
        """
        Returns the version of a given executable by running it with '--version'.

        Args:
            executable_path: Path to the executable.

        Returns:
            A string containing the version, or an error/status message.
        """
        if not executable_path or not executable_path.exists():
            return "Not found"
        try:
            command: List[str] = [str(executable_path)]
            if 'ffmpeg' in executable_path.name.lower():
                command.append('-version')
            else:
                command.append('--version')

            kwargs = {'text': True, 'encoding': 'utf-8', 'errors': 'replace', 'stderr': subprocess.STDOUT}
            if sys.platform == 'win32':
                kwargs['creationflags'] = SUBPROCESS_CREATION_FLAGS

            result = subprocess.check_output(command, timeout=15, **kwargs)
            return result.strip().split('\n')[0]
        except (FileNotFoundError, PermissionError):
            return "Not found or no permission"
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Version check for {executable_path} timed out.")
            return "Version check timed out"
        except (subprocess.CalledProcessError, OSError) as e:
            self.logger.error(f"Error checking version for {executable_path}: {e}")
            return "Cannot execute"
        except Exception:
            self.logger.exception(f"Unexpected error checking version for {executable_path}")
            return "Error checking version"

    def _download_file_with_progress(self, url: str, save_path: Path, dep_type: str):
        """
        Downloads a file, showing progress and handling chunked downloading.

        Args:
            url: The URL to download from.
            save_path: The local path to save the file to.
            dep_type: The type of dependency being downloaded (e.g., 'yt-dlp').

        Raises:
            DownloadCancelledError: If the download is cancelled by the user.
            requests.exceptions.RequestException: If a network error occurs.
        """
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

        try:
            if use_chunked:
                self.logger.info(f"Starting chunked download for {dep_type} ({total_size/1024/1024:.1f} MB)...")
                self._download_file_chunked(url, save_path, total_size, dep_type)
            else:
                log_msg = f"Starting single-stream download for {dep_type}."
                if 0 < total_size <= self.CHUNKED_DOWNLOAD_THRESHOLD: log_msg += " (File is small)"
                if total_size > 0 and not supports_ranges: log_msg += " (Server doesn't support ranged requests)"
                self.logger.info(log_msg)
                self._download_file_single_stream(url, save_path, dep_type)
        except (requests.exceptions.RequestException, IOError) as e:
            self.logger.exception(f"Download for {dep_type} failed: {e}. Falling back to single-stream.")
            if save_path.exists():
                try: save_path.unlink()
                except OSError: pass
            self._download_file_single_stream(url, save_path, dep_type)

        self.gui_queue.put(('dependency_progress', {
            'type': dep_type, 'status': 'determinate',
            'text': 'Download complete. Preparing...', 'value': 100
        }))

    def _download_file_single_stream(self, url: str, save_path: Path, dep_type: str):
        """Downloads a file as a single stream, with retries."""
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
                    with save_path.open('wb') as f_out:
                        for chunk in r.iter_content(chunk_size=chunk_size):
                            if self.stop_event.is_set(): raise DownloadCancelledError("Download cancelled during transfer.")
                            f_out.write(chunk)
                            bytes_downloaded += len(chunk)
                            if total_size > 0:
                                progress = (bytes_downloaded / total_size) * 100
                                elapsed = time.time() - start_time
                                speed = (bytes_downloaded / elapsed) / 1024 / 1024 if elapsed > 0 else 0
                                text = f'Downloading... {bytes_downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB ({speed:.1f} MB/s)'
                                self.gui_queue.put(('dependency_progress', {'type': dep_type, 'status': 'determinate', 'text': text, 'value': progress}))
                return
            except DownloadCancelledError: raise
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Single-stream error on attempt {attempt + 1}: {e}")
                if attempt < self.DOWNLOAD_RETRY_ATTEMPTS - 1: time.sleep(2 ** attempt)
                else: raise e

    def _download_file_chunked(self, url: str, save_path: Path, total_size: int, dep_type: str):
        """Downloads a file in parallel chunks."""
        chunk_size = total_size // self.DOWNLOAD_CHUNKS
        ranges = [(i * chunk_size, (i + 1) * chunk_size - 1) for i in range(self.DOWNLOAD_CHUNKS - 1)]
        ranges.append(((self.DOWNLOAD_CHUNKS - 1) * chunk_size, total_size - 1))

        with tempfile.TemporaryDirectory(prefix="multiyt-dlp-") as temp_dir:
            temp_path = Path(temp_dir)
            progress, progress_lock, start_time = [0] * self.DOWNLOAD_CHUNKS, threading.Lock(), time.time()
            with ThreadPoolExecutor(max_workers=self.DOWNLOAD_CHUNKS) as executor:
                futures = {executor.submit(self._download_chunk, url, temp_path / f'chunk_{i}', ranges[i], i, progress, progress_lock) for i in range(self.DOWNLOAD_CHUNKS)}

                while True:
                    _, not_done = wait(futures, timeout=0.5)

                    with progress_lock: bytes_downloaded = sum(progress)
                    if total_size > 0:
                        percent = (bytes_downloaded / total_size) * 100
                        elapsed = time.time() - start_time
                        speed = (bytes_downloaded / elapsed) / 1024 / 1024 if elapsed > 0 else 0
                        text = f'Downloading... {bytes_downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB ({speed:.1f} MB/s)'
                        self.gui_queue.put(('dependency_progress', {'type': dep_type, 'status': 'determinate', 'text': text, 'value': percent}))

                    if self.stop_event.is_set(): break
                    if not not_done: break

                for future in as_completed(futures):
                    future.result() # Raises any exception from the thread

            if self.stop_event.is_set(): raise DownloadCancelledError("Download cancelled before file assembly.")

            self.gui_queue.put(('dependency_progress', {'type': dep_type, 'status': 'indeterminate', 'text': 'Assembling file...'}))
            self._assemble_chunks(save_path, temp_path)

    def _download_chunk(self, url: str, chunk_path: Path, byte_range: Tuple[int, int], chunk_idx: int, progress: list, lock: threading.Lock):
        """Downloads a single chunk of a file."""
        for attempt in range(self.DOWNLOAD_RETRY_ATTEMPTS):
            if self.stop_event.is_set(): raise DownloadCancelledError(f"Chunk {chunk_idx} cancelled.")
            try:
                headers = REQUEST_HEADERS.copy()
                headers['Range'] = f'bytes={byte_range[0]}-{byte_range[1]}'
                bytes_dl = 0
                with requests.get(url, headers=headers, stream=True, timeout=REQUEST_TIMEOUTS) as r:
                    r.raise_for_status()
                    with chunk_path.open('wb') as f:
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
                else: raise e

    def _assemble_chunks(self, save_path: Path, temp_dir: Path):
        """Assembles downloaded chunks into a single file."""
        with save_path.open('wb') as f_out:
            for i in range(self.DOWNLOAD_CHUNKS):
                with (temp_dir / f'chunk_{i}').open('rb') as f_in:
                    shutil.copyfileobj(f_in, f_out)

    def install_or_update_yt_dlp(self):
        """Starts the yt-dlp download/update process in a new thread."""
        threading.Thread(target=self._install_or_update_yt_dlp_thread, daemon=True, name="yt-dlp-Installer").start()

    def _install_or_update_yt_dlp_thread(self):
        """The actual logic for downloading and setting up yt-dlp."""
        self.stop_event.clear()
        platform = sys.platform
        if platform not in YT_DLP_URLS:
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': f"Unsupported OS: {platform}"}))
            return
        try:
            url = YT_DLP_URLS[platform]
            filename = Path(urllib.parse.unquote(url)).name
            save_path = APP_PATH / ('yt-dlp' if platform == 'darwin' and filename == 'yt-dlp_macos' else filename)

            self._download_file_with_progress(url, save_path, 'yt-dlp')

            if platform in ['linux', 'darwin']:
                save_path.chmod(0o755)

            self.yt_dlp_path = save_path
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': True, 'path': str(save_path)}))
        except DownloadCancelledError:
            self.logger.info("yt-dlp download cancelled by user.")
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': "Download cancelled by user."}))
        except requests.exceptions.RequestException as e:
            self.logger.exception("Network error during yt-dlp download.")
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': f"Network error: {e}"}))
        except (IOError, OSError) as e:
            self.logger.exception("File system error during yt-dlp installation.")
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': f"File error: {e}"}))
        except Exception:
            self.logger.exception("An unexpected error occurred during yt-dlp download.")
            self.gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': "An unexpected error occurred."}))

    def download_ffmpeg(self):
        """Starts the FFmpeg download process in a new thread."""
        threading.Thread(target=self._download_ffmpeg_thread, daemon=True, name="FFmpeg-Installer").start()

    def _download_ffmpeg_thread(self):
        """The actual logic for downloading and extracting FFmpeg."""
        self.stop_event.clear()
        platform = sys.platform
        if platform not in FFMPEG_URLS:
            self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': f"Unsupported OS: {platform}"}))
            return

        url = FFMPEG_URLS[platform]
        final_ffmpeg_name = 'ffmpeg.exe' if platform == 'win32' else 'ffmpeg'
        final_ffmpeg_path = APP_PATH / final_ffmpeg_name

        with tempfile.TemporaryDirectory(prefix="ffmpeg-dl-") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            try:
                archive_path = temp_dir / Path(urllib.parse.unquote(url)).name
                extract_dir = temp_dir / "ffmpeg_extracted"

                self._download_file_with_progress(url, archive_path, 'ffmpeg')

                self.gui_queue.put(('dependency_progress', {'type': 'ffmpeg', 'status': 'indeterminate', 'text': 'Extracting FFmpeg...'}))
                extract_dir.mkdir(exist_ok=True)

                if archive_path.suffix == '.zip':
                    with zipfile.ZipFile(archive_path, 'r') as zip_ref: zip_ref.extractall(extract_dir)
                elif '.tar.xz' in archive_path.name:
                    with tarfile.open(archive_path, 'r:xz') as tar_ref: tar_ref.extractall(path=extract_dir)

                self.gui_queue.put(('dependency_progress', {'type': 'ffmpeg', 'status': 'indeterminate', 'text': 'Locating executable...'}))

                found_files = list(extract_dir.rglob(final_ffmpeg_name))
                if not found_files: raise FileNotFoundError(f"Could not find '{final_ffmpeg_name}' in archive.")
                ffmpeg_exe_path = found_files[0]

                if final_ffmpeg_path.exists(): final_ffmpeg_path.unlink()
                shutil.move(str(ffmpeg_exe_path), str(final_ffmpeg_path))

                if platform in ['linux', 'darwin']: final_ffmpeg_path.chmod(0o755)

                self.ffmpeg_path = final_ffmpeg_path
                self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': True, 'path': str(final_ffmpeg_path)}))

            except DownloadCancelledError:
                self.logger.info("FFmpeg download cancelled by user.")
                self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': "Download cancelled by user."}))
            except requests.exceptions.RequestException as e:
                self.logger.exception("Network error during FFmpeg download.")
                self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': f"Network error: {e}"}))
            except (zipfile.BadZipFile, tarfile.ReadError) as e:
                self.logger.exception("Error extracting FFmpeg archive.")
                self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': f"Archive error: {e}"}))
            except FileNotFoundError as e:
                self.logger.exception("Could not find FFmpeg executable in extracted files.")
                self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': str(e)}))
            except (IOError, OSError) as e:
                self.logger.exception("File system error during FFmpeg installation.")
                self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': f"File error: {e}"}))
            except Exception:
                self.logger.exception("An unexpected error occurred during FFmpeg download.")
                self.gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': "An unexpected error occurred."}))