"""Manages the download queue, worker tasks, and yt-dlp processes."""
import asyncio
import re
import os
import sys
import uuid
import signal
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Tuple, Coroutine

from .constants import SUBPROCESS_CREATION_FLAGS, TEMP_DOWNLOAD_DIR
from .url_extractor import URLInfoExtractor
from .exceptions import URLExtractionError, DownloadCancelledError
from .jobs import DownloadJob

class DownloadManager:
    """Manages the download queue, worker tasks, and yt-dlp processes."""
    def __init__(self, event_callback: Callable[[Tuple[str, Any]], Coroutine[Any, Any, None]]):
        """
        Initializes the DownloadManager.

        Args:
            event_callback: The async function to call with manager events.
        """
        self.event_callback = event_callback
        self.logger = logging.getLogger(__name__)
        self.job_queue: asyncio.Queue[DownloadJob] = asyncio.Queue()
        self.url_processing_queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
        self.worker_tasks: set[asyncio.Task] = set()
        self.url_processor_tasks: set[asyncio.Task] = set()
        self.completed_jobs: int = 0
        self.total_jobs: int = 0
        self.stats_lock = asyncio.Lock()
        self.active_processes_lock = asyncio.Lock()
        self.active_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.max_concurrent_downloads: int = 4
        self.yt_dlp_path: Optional[Path] = None
        self.ffmpeg_path: Optional[Path] = None

    async def initialize(self):
        """Performs asynchronous initialization, such as cleaning temp files."""
        await self.cleanup_temporary_files()

    def set_config(self, max_concurrent: int, yt_dlp_path: Optional[Path], ffmpeg_path: Optional[Path]):
        """Sets runtime configuration for the manager."""
        self.max_concurrent_downloads = max_concurrent
        self.yt_dlp_path = yt_dlp_path
        self.ffmpeg_path = ffmpeg_path

    async def get_stats(self) -> tuple[int, int]:
        """Gets the current download statistics."""
        async with self.stats_lock:
            return self.completed_jobs, self.total_jobs

    async def start_downloads(self, urls: List[str], options: Dict[str, Any]):
        """Starts the process of fetching and downloading a list of URLs."""
        if not self.yt_dlp_path:
            self.logger.error("yt-dlp path is not set. Cannot start downloads.")
            return
        async with self.stats_lock:
            self.completed_jobs, self.total_jobs = 0, 0

        self._start_workers()

        for url in urls:
            self.url_processing_queue.put_nowait((url, options))

        async def monitor_url_queue():
            await self.url_processing_queue.join()
            await self.event_callback(('url_processing_done', None))

        asyncio.create_task(monitor_url_queue())

        num_url_processors = min(8, len(urls))
        for _ in range(num_url_processors):
            task = asyncio.create_task(self._url_processor_task())
            self.url_processor_tasks.add(task)
            task.add_done_callback(self._task_done_callback(self.url_processor_tasks))

    async def add_jobs(self, jobs_to_add: List[DownloadJob]):
        """Adds a list of pre-defined jobs to the download queue."""
        if not self.yt_dlp_path:
            self.logger.error("yt-dlp path is not set. Cannot add jobs.")
            return
        self.logger.info(f"Retrying {len(jobs_to_add)} failed download(s).")

        for job in jobs_to_add:
            job.status = "Queued"; job.progress = "0%"
            await self.event_callback(('add_job', job))
            self.job_queue.put_nowait(job)

        async with self.stats_lock:
            self.total_jobs += len(jobs_to_add)
        self._start_workers()

    async def stop_all_downloads(self):
        """Stops all active and queued downloads and terminates processes."""
        self.logger.info("STOP signal received. Terminating downloads...")
        
        all_tasks = self.worker_tasks.union(self.url_processor_tasks)
        for task in all_tasks:
            task.cancel()
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)

        while not self.job_queue.empty():
            job = self.job_queue.get_nowait()
            await self.event_callback(('done', (job.job_id, 'Cancelled')))
        while not self.url_processing_queue.empty():
            self.url_processing_queue.get_nowait()
            self.url_processing_queue.task_done()

        async with self.active_processes_lock:
            procs_to_terminate = list(self.active_processes.items())

        for job_id, process in procs_to_terminate:
            self.logger.info(f"Terminating process for {job_id} (PID: {process.pid})...")
            try:
                if sys.platform == 'win32':
                    process.send_signal(signal.CTRL_C_EVENT)
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGINT)
                await asyncio.wait_for(process.wait(), timeout=10)
            except (asyncio.TimeoutError, ProcessLookupError, OSError) as e:
                self.logger.warning(f"Graceful shutdown for {job_id} failed: {e}. Forcing termination...")
                try: process.kill()
                except (ProcessLookupError, OSError): pass # Already gone

            await self.event_callback(('done', (job_id, 'Cancelled')))
            async with self.active_processes_lock:
                if job_id in self.active_processes: del self.active_processes[job_id]

        await self.cleanup_temporary_files()
        async with self.stats_lock: self.total_jobs, self.completed_jobs = 0, 0

    async def _url_processor_task(self):
        """Worker task that processes URLs to create DownloadJob objects."""
        if not self.yt_dlp_path: return
        extractor = URLInfoExtractor(self.yt_dlp_path)
        try:
            while True:
                url, options = await self.url_processing_queue.get()
                try:
                    video_count = await extractor.get_video_count(url)
                    if video_count > 0:
                        async with self.stats_lock: self.total_jobs += video_count

                    if video_count == 1:
                        title = await extractor.get_single_video_title(url)
                        job = DownloadJob(str(uuid.uuid4()), url, options.copy(), title=title)
                        await self.event_callback(('add_job', job))
                        self.job_queue.put_nowait(job)
                    elif video_count > 1:
                        for i in range(1, video_count + 1):
                            job = DownloadJob(str(uuid.uuid4()), url, options.copy(), title=f"Item {i}/{video_count}...", playlist_index=i)
                            await self.event_callback(('add_job', job))
                            self.job_queue.put_nowait(job)
                except (URLExtractionError, DownloadCancelledError) as e:
                    job = DownloadJob(str(uuid.uuid4()), url, {}, title=f"Error: {e}", status=f"Error: {e}", progress="N/A")
                    await self.event_callback(('add_job', job))
                    await self.event_callback(('done', (job.job_id, "Failed")))
                except Exception:
                    self.logger.exception(f"Unhandled error processing URL: {url}")
                finally:
                    self.url_processing_queue.task_done()
        except asyncio.CancelledError:
            self.logger.info("URL processor task cancelled.")

    async def cleanup_temporary_files(self):
        """Cleans up temporary download files in the dedicated temp directory."""
        if not await asyncio.to_thread(TEMP_DOWNLOAD_DIR.is_dir): return
        count = 0
        
        # Note: iterdir() itself is blocking and must be wrapped
        items_to_check = await asyncio.to_thread(list, TEMP_DOWNLOAD_DIR.iterdir())

        for item in items_to_check:
            if item.suffix in {".part", ".ytdl", ".webm"}:
                try:
                    await asyncio.to_thread(item.unlink)
                    count += 1
                except OSError as e:
                    self.logger.error(f"Error deleting temp file {item.name}: {e}")
        if count > 0: self.logger.info(f"Deleted {count} temporary file(s).")
    
    def _task_done_callback(self, task_set: set) -> Callable:
        """Creates a callback to remove a task from a set and log exceptions."""
        def callback(task: asyncio.Task):
            task_set.discard(task)
            try:
                task.result()
            except asyncio.CancelledError:
                pass # Normal cancellation
            except Exception:
                self.logger.exception(f"Exception in background task {task.get_name()}:")
        return callback

    def _start_workers(self):
        """Starts download worker tasks up to the configured maximum."""
        needed = self.max_concurrent_downloads - len(self.worker_tasks)
        for _ in range(needed):
            task = asyncio.create_task(self._worker_task())
            self.worker_tasks.add(task)
            task.add_done_callback(self._task_done_callback(self.worker_tasks))

    async def _worker_task(self):
        """Main loop for a download worker task."""
        assert self.yt_dlp_path is not None
        try:
            while True:
                job = await self.job_queue.get()
                try:
                    await self.event_callback(('update_job', (job.job_id, 'status', 'Downloading')))
                    await self._run_download_process(job)
                finally:
                    self.job_queue.task_done()
        except asyncio.CancelledError:
            self.logger.info("Download worker task cancelled.")

    def _build_yt_dlp_command(self, job: DownloadJob) -> List[str]:
        """Builds the full yt-dlp command list based on a DownloadJob."""
        assert self.yt_dlp_path is not None
        output_path_template = job.options['output_path'] / job.options['filename_template']
        command = [str(self.yt_dlp_path), '--newline', '--progress-template', 'PROGRESS::%(progress._percent_str)s', '--no-mtime', '--paths', f'temp:{str(TEMP_DOWNLOAD_DIR)}', '-o', str(output_path_template)]
        if self.ffmpeg_path: command.extend(['--ffmpeg-location', str(self.ffmpeg_path.parent)])

        if job.options['download_type'] == 'video':
            res = job.options['video_resolution']
            f_str = f'bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best[height<={res}]' if res.lower() != 'best' else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            command.extend(['-f', f_str])
        elif job.options['download_type'] == 'audio':
            audio_format = job.options['audio_format']
            command.extend(['-f', 'bestaudio/best', '-x'])
            if audio_format != 'best':
                command.extend(['--audio-format', audio_format])
                if audio_format == 'mp3': command.extend(['--audio-quality', '192K'])
        if job.options['embed_thumbnail']: command.append('--embed-thumbnail')
        if job.options.get('embed_metadata', True): command.append('--embed-metadata')
        if job.playlist_index is not None: command.extend(['--playlist-items', str(job.playlist_index)])
        command.append(job.original_url)
        return command

    async def _run_download_process(self, job: DownloadJob):
        """Executes the yt-dlp subprocess for a single job."""
        error_message, final_status = None, 'Failed'
        try:
            command = self._build_yt_dlp_command(job)
            
            kwargs: Dict[str, Any] = {}
            if sys.platform == 'win32':
                kwargs['creationflags'] = SUBPROCESS_CREATION_FLAGS | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs['preexec_fn'] = os.setsid

            async with self.active_processes_lock:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    **kwargs
                )
                self.active_processes[job.job_id] = process

            assert process.stdout is not None
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes: break
                clean_line = line_bytes.decode('utf-8', 'replace').strip()
                self.logger.debug(f"[{job.job_id}] {clean_line}")

                if dest_match := re.search(r'\[download\] Destination: (.*)', clean_line):
                    new_title = Path(dest_match.group(1).strip()).stem
                    if new_title and new_title != job.title:
                        job.title = new_title
                        await self.event_callback(('update_job', (job.job_id, 'title', new_title)))
                if clean_line.startswith('ERROR:'): error_message = clean_line[6:].strip()
                if status_match := re.search(r'\[(\w+)\]', clean_line):
                    status_map = {'merger': 'Merging...', 'extractaudio': 'Extracting Audio...', 'embedthumbnail': 'Embedding...', 'fixupm4a': 'Fixing M4a...', 'metadata': 'Writing Metadata...'}
                    if (status_key := status_match.group(1).lower()) in status_map:
                        await self.event_callback(('update_job', (job.job_id, 'status', status_map[status_key])))
                
                percentage = None
                if clean_line.startswith('PROGRESS::'):
                    try: percentage = float(clean_line.split('::', 1)[1].strip().rstrip('%'))
                    except (IndexError, ValueError): pass
                elif '[download]' in clean_line and (match := re.search(r'(\d+\.?\d*)%', clean_line)):
                    try: percentage = float(match.group(1))
                    except ValueError: pass
                if percentage is not None:
                    await self.event_callback(('update_job', (job.job_id, 'progress', f"{percentage:.1f}%")))
            
            return_code = await process.wait()
            if return_code == 0: final_status = 'Completed'
            elif error_message: final_status = f"Failed: {error_message[:60]}"
        except asyncio.CancelledError: final_status = 'Cancelled'
        except FileNotFoundError: final_status = "Error: yt-dlp executable not found"
        except OSError as e: final_status = f"Error: OS error: {e}"
        except Exception:
            self.logger.exception(f"Unexpected error during download for job {job.job_id}")
            final_status = "Error: An unexpected exception occurred"
        finally:
            async with self.active_processes_lock:
                if job.job_id in self.active_processes: del self.active_processes[job.job_id]
            async with self.stats_lock: self.completed_jobs += 1
            await self.event_callback(('done', (job.job_id, final_status)))