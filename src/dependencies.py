"""Manages the discovery, download, and updates for yt-dlp and FFmpeg."""
import sys
import shutil
import asyncio
import subprocess
import urllib.parse
import zipfile
import tarfile
import time
import tempfile
import logging
from pathlib import Path
from typing import Optional, List, Tuple, Callable, Any, Dict, Coroutine

import aiohttp
import aiofiles

from .constants import (
    YT_DLP_URLS, FFMPEG_URLS, REQUEST_HEADERS, APP_PATH, SUBPROCESS_CREATION_FLAGS
)
from .exceptions import DownloadCancelledError


class DependencyManager:
    """Manages the discovery, download, and updates for yt-dlp and FFmpeg."""
    CHUNKED_DOWNLOAD_THRESHOLD = 20 * 1024 * 1024  # 20 MB
    DOWNLOAD_CHUNKS = 8
    DOWNLOAD_RETRY_ATTEMPTS = 3

    def __init__(self, event_callback: Callable[[Tuple[str, Any]], Coroutine[Any, Any, None]]):
        """
        Initializes the DependencyManager.

        Args:
            event_callback: The async function to call with manager events.
        """
        self.event_callback = event_callback
        self.logger = logging.getLogger(__name__)
        self.yt_dlp_path: Optional[Path] = None
        self.ffmpeg_path: Optional[Path] = None
        self.download_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Asynchronously finds paths to dependencies to avoid blocking the event loop."""
        self.logger.info("Initializing dependency paths...")
        self.yt_dlp_path, self.ffmpeg_path = await asyncio.gather(
            asyncio.to_thread(self.find_yt_dlp),
            asyncio.to_thread(self.find_ffmpeg)
        )
        self.logger.info(f"yt-dlp path: {self.yt_dlp_path}")
        self.logger.info(f"FFmpeg path: {self.ffmpeg_path}")

    def cancel_download(self):
        """Signals the download process to stop."""
        if self.download_task and not self.download_task.done():
            self.logger.info("Cancellation signal sent to dependency downloader.")
            self.download_task.cancel()

    def find_yt_dlp(self) -> Optional[Path]:
        """Finds the yt-dlp executable."""
        self.yt_dlp_path = self._find_executable('yt-dlp')
        return self.yt_dlp_path

    def find_ffmpeg(self) -> Optional[Path]:
        """Finds the ffmpeg executable."""
        self.ffmpeg_path = self._find_executable('ffmpeg')
        return self.ffmpeg_path

    def _find_executable(self, name: str) -> Optional[Path]:
        """Finds an executable, preferring a locally managed one."""
        local_path = APP_PATH / (f'{name}.exe' if sys.platform == 'win32' else name)
        if local_path.exists():
            return local_path
        path_in_system = shutil.which(name)
        return Path(path_in_system) if path_in_system else None

    async def get_version(self, executable_path: Optional[Path]) -> str:
        """Asynchronously returns the version of an executable by running it with '--version'."""
        if not executable_path or not executable_path.exists():
            return "Not found"
        try:
            command: List[str] = [str(executable_path)]
            if 'ffmpeg' in executable_path.name.lower():
                command.append('-version')
            else:
                command.append('--version')

            kwargs = {'stdout': asyncio.subprocess.PIPE, 'stderr': asyncio.subprocess.PIPE}
            if sys.platform == 'win32':
                kwargs['creationflags'] = SUBPROCESS_CREATION_FLAGS

            process = await asyncio.create_subprocess_exec(*command, **kwargs)
            stdout_bytes, _ = await asyncio.wait_for(process.communicate(), timeout=15)
            
            if process.returncode != 0:
                return "Cannot execute"
                
            return stdout_bytes.decode('utf-8', 'replace').strip().split('\n')[0]
        except FileNotFoundError:
            return "Not found or no permission"
        except asyncio.TimeoutError:
            return "Version check timed out"
        except OSError:
            return "Cannot execute"
        except Exception:
            self.logger.exception(f"Error checking version for {executable_path}")
            return "Error checking version"

    async def _download_file_with_progress(self, session: aiohttp.ClientSession, url: str, save_path: Path, dep_type: str):
        """Downloads a file, showing progress and handling chunked downloading."""
        await self.event_callback(('dependency_progress', {'type': dep_type, 'status': 'determinate', 'text': 'Preparing download...', 'value': 0}))

        total_size, supports_ranges = 0, False
        try:
            async with session.head(url, headers=REQUEST_HEADERS, timeout=10, allow_redirects=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                supports_ranges = r.headers.get('accept-ranges', '').lower() == 'bytes'
        except aiohttp.ClientError as e:
            self.logger.warning(f"HEAD request failed: {e}. Proceeding with single-stream download.")

        use_chunked = total_size > self.CHUNKED_DOWNLOAD_THRESHOLD and supports_ranges
        try:
            if use_chunked:
                self.logger.info(f"Starting chunked download for {dep_type} ({total_size/1024/1024:.1f} MB)...")
                await self._download_file_chunked(session, url, save_path, total_size, dep_type)
            else:
                self.logger.info(f"Starting single-stream download for {dep_type}.")
                await self._download_file_single_stream(session, url, save_path, dep_type)
        except (aiohttp.ClientError, IOError) as e:
            self.logger.exception(f"Download for {dep_type} failed: {e}. Falling back to single-stream.")
            if save_path.exists():
                try: save_path.unlink()
                except OSError: pass
            await self._download_file_single_stream(session, url, save_path, dep_type)

        await self.event_callback(('dependency_progress', {'type': dep_type, 'status': 'determinate', 'text': 'Download complete. Preparing...', 'value': 100}))

    async def _download_file_single_stream(self, session: aiohttp.ClientSession, url: str, save_path: Path, dep_type: str):
        """Downloads a file as a single stream, with retries."""
        for attempt in range(self.DOWNLOAD_RETRY_ATTEMPTS):
            try:
                async with session.get(url, headers=REQUEST_HEADERS, timeout=aiohttp.ClientTimeout(total=None, sock_read=60)) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get('Content-Length', 0))
                    if total_size <= 0:
                        await self.event_callback(('dependency_progress', {'type': dep_type, 'status': 'indeterminate', 'text': f'Downloading {dep_type}... (Size unknown)'}))

                    bytes_downloaded, start_time = 0, time.monotonic()
                    async with aiofiles.open(save_path, 'wb') as f_out:
                        async for chunk in r.content.iter_chunked(8192):
                            await f_out.write(chunk)
                            bytes_downloaded += len(chunk)
                            if total_size > 0:
                                progress = (bytes_downloaded / total_size) * 100
                                elapsed = time.monotonic() - start_time
                                speed = (bytes_downloaded / elapsed) / 1024 / 1024 if elapsed > 0 else 0
                                text = f'Downloading... {bytes_downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB ({speed:.1f} MB/s)'
                                await self.event_callback(('dependency_progress', {'type': dep_type, 'status': 'determinate', 'text': text, 'value': progress}))
                return
            except aiohttp.ClientError as e:
                self.logger.error(f"Single-stream error on attempt {attempt + 1}: {e}")
                if attempt < self.DOWNLOAD_RETRY_ATTEMPTS - 1: await asyncio.sleep(2 ** attempt)
                else: raise e

    async def _download_file_chunked(self, session: aiohttp.ClientSession, url: str, save_path: Path, total_size: int, dep_type: str):
        """Downloads a file in parallel chunks."""
        chunk_size = total_size // self.DOWNLOAD_CHUNKS
        ranges = [(i * chunk_size, (i + 1) * chunk_size - 1) for i in range(self.DOWNLOAD_CHUNKS - 1)]
        ranges.append(((self.DOWNLOAD_CHUNKS - 1) * chunk_size, total_size - 1))

        with tempfile.TemporaryDirectory(prefix="multiyt-dlp-") as temp_dir:
            temp_path = Path(temp_dir)
            progress, start_time = [0] * self.DOWNLOAD_CHUNKS, time.monotonic()
            tasks = [self._download_chunk(session, url, temp_path / f'chunk_{i}', ranges[i], i, progress) for i in range(self.DOWNLOAD_CHUNKS)]
            
            progress_reporter = asyncio.create_task(self._report_chunked_progress(progress, total_size, start_time, dep_type))
            try:
                await asyncio.gather(*tasks)
            finally:
                progress_reporter.cancel()

            await self.event_callback(('dependency_progress', {'type': dep_type, 'status': 'indeterminate', 'text': 'Assembling file...'}))
            await self._assemble_chunks(save_path, temp_path)

    async def _report_chunked_progress(self, progress: list, total_size: int, start_time: float, dep_type: str):
        """Periodically reports progress for chunked downloads."""
        while True:
            try:
                bytes_downloaded = sum(progress)
                percent = (bytes_downloaded / total_size) * 100
                elapsed = time.monotonic() - start_time
                speed = (bytes_downloaded / elapsed) / 1024 / 1024 if elapsed > 0 else 0
                text = f'Downloading... {bytes_downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB ({speed:.1f} MB/s)'
                await self.event_callback(('dependency_progress', {'type': dep_type, 'status': 'determinate', 'text': text, 'value': percent}))
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break

    async def _download_chunk(self, session: aiohttp.ClientSession, url: str, chunk_path: Path, byte_range: Tuple[int, int], chunk_idx: int, progress: list):
        """Downloads a single chunk of a file."""
        for attempt in range(self.DOWNLOAD_RETRY_ATTEMPTS):
            try:
                headers = REQUEST_HEADERS.copy()
                headers['Range'] = f'bytes={byte_range[0]}-{byte_range[1]}'
                bytes_dl = 0
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=None, sock_read=60)) as r:
                    r.raise_for_status()
                    async with aiofiles.open(chunk_path, 'wb') as f:
                        async for part in r.content.iter_chunked(8192):
                            await f.write(part)
                            bytes_dl += len(part)
                            progress[chunk_idx] = bytes_dl
                return
            except aiohttp.ClientError as e:
                self.logger.error(f"Error on chunk {chunk_idx}, attempt {attempt + 1}: {e}")
                if attempt < self.DOWNLOAD_RETRY_ATTEMPTS - 1: await asyncio.sleep(2 ** attempt)
                else: raise e

    async def _assemble_chunks(self, save_path: Path, temp_dir: Path):
        """Assembles downloaded chunks into a single file."""
        async with aiofiles.open(save_path, 'wb') as f_out:
            for i in range(self.DOWNLOAD_CHUNKS):
                async with aiofiles.open(temp_dir / f'chunk_{i}', 'rb') as f_in:
                    while chunk := await f_in.read(8192*4):
                        await f_out.write(chunk)

    async def install_or_update_yt_dlp(self) -> Dict[str, Any]:
        """Coroutine for downloading and setting up yt-dlp."""
        self.download_task = asyncio.current_task()
        try:
            platform = sys.platform
            if platform not in YT_DLP_URLS:
                return {'type': 'yt-dlp', 'success': False, 'error': f"Unsupported OS: {platform}"}
            
            url = YT_DLP_URLS[platform]
            filename = Path(urllib.parse.unquote(url)).name
            save_path = APP_PATH / ('yt-dlp' if platform == 'darwin' and filename == 'yt-dlp_macos' else filename)

            async with aiohttp.ClientSession() as session:
                await self._download_file_with_progress(session, url, save_path, 'yt-dlp')

            if platform in ['linux', 'darwin']:
                await asyncio.to_thread(save_path.chmod, 0o755)

            self.yt_dlp_path = save_path
            return {'type': 'yt-dlp', 'success': True, 'path': str(save_path)}
        except asyncio.CancelledError:
            self.logger.info("yt-dlp download cancelled by user.")
            raise DownloadCancelledError("Download cancelled by user.")
        except aiohttp.ClientError as e:
            return {'type': 'yt-dlp', 'success': False, 'error': f"Network error: {e}"}
        except (IOError, OSError) as e:
            return {'type': 'yt-dlp', 'success': False, 'error': f"File error: {e}"}
        except Exception:
            self.logger.exception("An unexpected error occurred during yt-dlp download.")
            return {'type': 'yt-dlp', 'success': False, 'error': "An unexpected error occurred."}

    async def download_ffmpeg(self) -> Dict[str, Any]:
        """Coroutine for downloading and extracting FFmpeg."""
        self.download_task = asyncio.current_task()
        platform = sys.platform
        if platform not in FFMPEG_URLS:
            return {'type': 'ffmpeg', 'success': False, 'error': f"Unsupported OS: {platform}"}

        url = FFMPEG_URLS[platform]
        final_ffmpeg_name = 'ffmpeg.exe' if platform == 'win32' else 'ffmpeg'
        final_ffmpeg_path = APP_PATH / final_ffmpeg_name

        with tempfile.TemporaryDirectory(prefix="ffmpeg-dl-") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            try:
                archive_path = temp_dir / Path(urllib.parse.unquote(url)).name
                extract_dir = temp_dir / "ffmpeg_extracted"

                async with aiohttp.ClientSession() as session:
                    await self._download_file_with_progress(session, url, archive_path, 'ffmpeg')

                await self.event_callback(('dependency_progress', {'type': 'ffmpeg', 'status': 'indeterminate', 'text': 'Extracting FFmpeg...'}))
                await asyncio.to_thread(extract_dir.mkdir, exist_ok=True)

                if archive_path.suffix == '.zip':
                    await asyncio.to_thread(zipfile.ZipFile(archive_path, 'r').extractall, extract_dir)
                elif '.tar.xz' in archive_path.name:
                    await asyncio.to_thread(tarfile.open(archive_path, 'r:xz').extractall, path=extract_dir)

                await self.event_callback(('dependency_progress', {'type': 'ffmpeg', 'status': 'indeterminate', 'text': 'Locating executable...'}))
                found_files = list(extract_dir.rglob(final_ffmpeg_name))
                if not found_files: raise FileNotFoundError(f"Could not find '{final_ffmpeg_name}' in archive.")
                ffmpeg_exe_path = found_files[0]

                if final_ffmpeg_path.exists(): await asyncio.to_thread(final_ffmpeg_path.unlink)
                await asyncio.to_thread(shutil.move, str(ffmpeg_exe_path), str(final_ffmpeg_path))

                if platform in ['linux', 'darwin']: await asyncio.to_thread(final_ffmpeg_path.chmod, 0o755)
                self.ffmpeg_path = final_ffmpeg_path
                return {'type': 'ffmpeg', 'success': True, 'path': str(final_ffmpeg_path)}
            except asyncio.CancelledError:
                self.logger.info("FFmpeg download cancelled by user.")
                raise DownloadCancelledError("Download cancelled by user.")
            except aiohttp.ClientError as e: return {'type': 'ffmpeg', 'success': False, 'error': f"Network error: {e}"}
            except (zipfile.BadZipFile, tarfile.ReadError) as e: return {'type': 'ffmpeg', 'success': False, 'error': f"Archive error: {e}"}
            except FileNotFoundError as e: return {'type': 'ffmpeg', 'success': False, 'error': str(e)}
            except (IOError, OSError) as e: return {'type': 'ffmpeg', 'success': False, 'error': f"File error: {e}"}
            except Exception:
                self.logger.exception("An unexpected error occurred during FFmpeg download.")
                return {'type': 'ffmpeg', 'success': False, 'error': "An unexpected error occurred."}