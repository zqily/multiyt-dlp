"""Manages the download queue, worker threads, and yt-dlp processes."""
import queue
import threading
import subprocess
import re
import os
import sys
import uuid
import signal
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from .constants import SUBPROCESS_CREATION_FLAGS, TEMP_DOWNLOAD_DIR
from .url_extractor import URLInfoExtractor
from .exceptions import URLExtractionError, DownloadCancelledError
from .jobs import DownloadJob

class DownloadManager:
    """Manages the download queue, worker threads, and yt-dlp processes."""
    def __init__(self, gui_queue: queue.Queue):
        """
        Initializes the DownloadManager.

        Args:
            gui_queue: The queue for sending messages to the GUI.
        """
        self.gui_queue = gui_queue
        self.logger = logging.getLogger(__name__)
        self.job_queue: queue.Queue[DownloadJob] = queue.Queue()
        self.url_processing_queue: queue.Queue[tuple[str, dict]] = queue.Queue()
        self.workers: List[threading.Thread] = []
        self.completed_jobs: int = 0
        self.total_jobs: int = 0
        self.stats_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.active_processes_lock = threading.Lock()
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self.max_concurrent_downloads: int = 4
        self.yt_dlp_path: Optional[Path] = None
        self.ffmpeg_path: Optional[Path] = None

    def set_config(self, max_concurrent: int, yt_dlp_path: Optional[Path], ffmpeg_path: Optional[Path]):
        """
        Sets runtime configuration for the manager.

        Args:
            max_concurrent: Maximum number of parallel downloads.
            yt_dlp_path: Path to the yt-dlp executable.
            ffmpeg_path: Path to the FFmpeg executable.
        """
        self.max_concurrent_downloads = max_concurrent
        self.yt_dlp_path = yt_dlp_path
        self.ffmpeg_path = ffmpeg_path

    def get_stats(self) -> tuple[int, int]:
        """
        Gets the current download statistics.

        Returns:
            A tuple containing (completed_jobs, total_jobs).
        """
        with self.stats_lock:
            return self.completed_jobs, self.total_jobs

    def start_downloads(self, urls: List[str], options: Dict[str, Any]):
        """
        Starts the process of fetching and downloading a list of URLs.

        Args:
            urls: A list of URLs to process.
            options: A dictionary of download options.
        """
        if not self.yt_dlp_path:
            self.logger.error("yt-dlp path is not set. Cannot start downloads.")
            return
        with self.stats_lock:
            self.completed_jobs, self.total_jobs = 0, 0
        self.gui_queue.put(('reset_progress', None))
        self.stop_event.clear()

        self._start_workers()

        for url in urls:
            self.url_processing_queue.put((url, options))

        def monitor_url_queue():
            self.url_processing_queue.join()
            if not self.stop_event.is_set():
                self.gui_queue.put(('url_processing_done', None))

        threading.Thread(target=monitor_url_queue, daemon=True, name="URL-Queue-Monitor").start()

        num_url_processors = min(8, len(urls))
        for i in range(num_url_processors):
            thread = threading.Thread(target=self._url_processor_worker, daemon=True, name=f"URL-Processor-{i+1}")
            thread.start()

    def add_jobs(self, jobs_to_add: List[DownloadJob]):
        """
        Adds a list of pre-defined jobs to the download queue (e.g., for retries).

        Args:
            jobs_to_add: A list of DownloadJob objects to queue.
        """
        if not self.yt_dlp_path:
            self.logger.error("yt-dlp path is not set. Cannot add jobs.")
            return
        self.logger.info(f"Retrying {len(jobs_to_add)} failed download(s).")

        for job in jobs_to_add:
            if self.stop_event.is_set(): break
            job.status = "Queued"
            job.progress = "0%"
            self.gui_queue.put(('add_job', job))
            self.job_queue.put(job)

        with self.stats_lock:
            self.total_jobs += len(jobs_to_add)
        self.gui_queue.put(('total_jobs_updated', None))
        self._start_workers()

    def stop_all_downloads(self):
        """Stops all active and queued downloads and terminates processes."""
        self.logger.info("STOP signal received. Terminating downloads...")
        self.stop_event.set()

        for q in [self.job_queue, self.url_processing_queue]:
            while not q.empty():
                try:
                    if q is self.job_queue:
                        job: DownloadJob = q.get_nowait()
                        self.gui_queue.put(('done', (job.job_id, 'Cancelled')))
                    else:
                        q.get_nowait()
                    q.task_done()
                except queue.Empty: break

        with self.active_processes_lock:
            procs_to_terminate = list(self.active_processes.items())

        for job_id, process in procs_to_terminate:
            self.logger.info(f"Requesting graceful shutdown for {job_id} (PID: {process.pid})...")
            try:
                if sys.platform == 'win32':
                    os.kill(process.pid, signal.CTRL_C_EVENT)
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGINT)

                process.wait(timeout=10)
                self.logger.info(f"Process {job_id} (PID: {process.pid}) terminated gracefully.")
            except (subprocess.TimeoutExpired, OSError, ProcessLookupError) as e:
                self.logger.warning(f"Graceful shutdown for {job_id} failed: {e}. Forcing termination...")
                try:
                    if sys.platform == 'win32':
                        subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, creationflags=SUBPROCESS_CREATION_FLAGS)
                    else:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                except (OSError, ProcessLookupError) as kill_e:
                    self.logger.error(f"Forceful termination for {job_id} also failed: {kill_e}")

            self.gui_queue.put(('done', (job_id, 'Cancelled')))
            with self.active_processes_lock:
                if job_id in self.active_processes: del self.active_processes[job_id]

        self.cleanup_temporary_files()
        with self.stats_lock: self.total_jobs, self.completed_jobs = 0, 0
        self.gui_queue.put(('reset_progress', None))

    def _url_processor_worker(self):
        """Worker thread that processes URLs to create DownloadJob objects."""
        if not self.yt_dlp_path:
            self.logger.critical("URL processor started without a valid yt-dlp path. Aborting worker.")
            return
        extractor = URLInfoExtractor(self.yt_dlp_path, self.stop_event)
        while not self.stop_event.is_set():
            try:
                url, options = self.url_processing_queue.get(timeout=1)
                thread_name = threading.current_thread().name
                try:
                    self.logger.info(f"[{thread_name}] Getting item count for: {url}")
                    video_count = extractor.get_video_count(url)
                    self.logger.info(f"[{thread_name}] Found {video_count} item(s) for '{url}'.")

                    if video_count > 0:
                        with self.stats_lock:
                            self.total_jobs += video_count
                        self.gui_queue.put(('total_jobs_updated', None))

                    if video_count == 1:
                        title = extractor.get_single_video_title(url)
                        job = DownloadJob(job_id=str(uuid.uuid4()), original_url=url, options=options.copy(), title=title)
                        self.gui_queue.put(('add_job', job))
                        self.job_queue.put(job)
                    elif video_count > 1:
                        for i in range(1, video_count + 1):
                            if self.stop_event.is_set(): break
                            job = DownloadJob(
                                job_id=str(uuid.uuid4()), original_url=url, options=options.copy(),
                                title=f"Item {i}/{video_count} from playlist...", playlist_index=i
                            )
                            self.gui_queue.put(('add_job', job))
                            self.job_queue.put(job)

                except DownloadCancelledError:
                    self.logger.info(f"[{thread_name}] URL processing for '{url}' was cancelled.")
                except URLExtractionError as e:
                    self.logger.error(f"[{thread_name}] Failed to process '{url}': {e}")
                    job_id = str(uuid.uuid4())
                    job = DownloadJob(job_id, url, {}, title=f"Error: {e}", status=f"Error: {e}", progress="N/A")
                    self.gui_queue.put(('add_job', job))
                    self.gui_queue.put(('done', (job_id, "Failed")))
                except Exception:
                    self.logger.exception(f"[{thread_name}] Unhandled error processing URL: {url}")
                finally:
                    self.url_processing_queue.task_done()
            except queue.Empty:
                break

    def cleanup_temporary_files(self):
        """Cleans up temporary download files in the dedicated temp directory."""
        if not TEMP_DOWNLOAD_DIR.is_dir(): return
        temp_extensions, count = {".part", ".ytdl", ".webm"}, 0
        self.logger.info(f"Scanning '{TEMP_DOWNLOAD_DIR}' for temp files...")
        try:
            for item in TEMP_DOWNLOAD_DIR.iterdir():
                if item.suffix in temp_extensions:
                    try:
                        item.unlink()
                        count += 1
                    except OSError as e:
                        self.logger.error(f"  - Error deleting {item.name}: {e}")
        except OSError as e:
            self.logger.error(f"Error scanning directory '{TEMP_DOWNLOAD_DIR}': {e}")
        if count > 0:
            self.logger.info(f"Cleanup complete. Deleted {count} temporary file(s).")

    def _start_workers(self):
        """Starts download worker threads up to the configured maximum."""
        self.workers = [w for w in self.workers if w.is_alive()]
        for _ in range(self.max_concurrent_downloads - len(self.workers)):
            worker = threading.Thread(target=self._worker_thread, daemon=True, name=f"Download-Worker-{len(self.workers) + 1}")
            self.workers.append(worker)
            worker.start()

    def _worker_thread(self):
        """Main loop for a download worker thread."""
        assert self.yt_dlp_path is not None, "yt-dlp path must be set before starting workers."
        while not self.stop_event.is_set():
            try:
                job: DownloadJob = self.job_queue.get(timeout=1)
                try:
                    if self.stop_event.is_set():
                        self.gui_queue.put(('done', (job.job_id, 'Cancelled')))
                        continue
                    self.gui_queue.put(('update_job', (job.job_id, 'status', 'Downloading')))
                    self._run_download_process(job)
                finally:
                    self.job_queue.task_done()
            except queue.Empty:
                continue

    def _build_yt_dlp_command(self, job: DownloadJob) -> List[str]:
        """Builds the full yt-dlp command list based on a DownloadJob."""
        assert self.yt_dlp_path is not None
        output_path_template = job.options['output_path'] / job.options['filename_template']

        command = [
            str(self.yt_dlp_path), '--newline',
            '--progress-template', 'PROGRESS::%(progress._percent_str)s',
            '--no-mtime',
            '--paths', f'temp:{str(TEMP_DOWNLOAD_DIR)}',
            '-o', str(output_path_template)
        ]

        if self.ffmpeg_path:
            command.extend(['--ffmpeg-location', str(self.ffmpeg_path.parent)])

        if job.options['download_type'] == 'video':
            res = job.options['video_resolution']
            f_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            if res.lower() != 'best':
                f_str = f'bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best[height<={res}]'
            command.extend(['-f', f_str])
        elif job.options['download_type'] == 'audio':
            audio_format = job.options['audio_format']
            command.extend(['-f', 'bestaudio/best', '-x'])
            if audio_format != 'best':
                command.extend(['--audio-format', audio_format])
                if audio_format == 'mp3':
                    command.extend(['--audio-quality', '192K'])

        if job.options['embed_thumbnail']:
            command.append('--embed-thumbnail')

        if job.playlist_index is not None:
            command.extend(['--playlist-items', str(job.playlist_index)])

        command.append(job.original_url)
        return command

    def _run_download_process(self, job: DownloadJob):
        """Executes the yt-dlp subprocess for a single job."""
        error_message, final_status = None, 'Failed'
        try:
            command = self._build_yt_dlp_command(job)

            popen_kwargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT, 'text': True, 'encoding': 'utf-8', 'errors': 'replace', 'bufsize': 1}
            if sys.platform == 'win32':
                popen_kwargs['creationflags'] = SUBPROCESS_CREATION_FLAGS | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs['preexec_fn'] = os.setsid

            with self.active_processes_lock:
                if self.stop_event.is_set(): return
                process = subprocess.Popen(command, **popen_kwargs)
                self.active_processes[job.job_id] = process

            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    if self.stop_event.is_set(): break
                    clean_line = line.strip()
                    self.logger.debug(f"[{job.job_id}] {clean_line}")

                    dest_match = re.search(r'\[download\] Destination: (.*)', clean_line)
                    if dest_match:
                        filepath = dest_match.group(1).strip()
                        new_title = Path(filepath).stem
                        if new_title and new_title != job.title:
                            self.logger.info(f"Updating title for {job.job_id} to '{new_title}'")
                            job.title = new_title
                            self.gui_queue.put(('update_job', (job.job_id, 'title', new_title)))

                    if clean_line.startswith('ERROR:'): error_message = clean_line[6:].strip()
                    status_match = re.search(r'\[(\w+)\]', clean_line)
                    if status_match:
                        status_key = status_match.group(1).lower()
                        status_map = {'merger': 'Merging...', 'extractaudio': 'Extracting Audio...', 'embedthumbnail': 'Embedding...', 'fixupm4a': 'Fixing M4a...', 'metadata': 'Writing Metadata...'}
                        if status_key in status_map: self.gui_queue.put(('update_job', (job.job_id, 'status', status_map[status_key])))
                    percentage = None
                    if clean_line.startswith('PROGRESS::'):
                        try: percentage = float(clean_line.split('::', 1)[1].strip().rstrip('%'))
                        except (IndexError, ValueError): pass
                    elif '[download]' in clean_line:
                        match = re.search(r'(\d+\.?\d*)%', clean_line)
                        if match:
                            try: percentage = float(match.group(1))
                            except ValueError: pass
                    if percentage is not None: self.gui_queue.put(('update_job', (job.job_id, 'progress', f"{percentage:.1f}%")))

                process.stdout.close()

            return_code = process.wait()
            if self.stop_event.is_set(): return
            if return_code == 0: final_status = 'Completed'
            elif error_message: final_status = f"Failed: {error_message[:60]}"
        except FileNotFoundError:
            final_status, error_message = "Error", "yt-dlp executable not found"
            self.logger.error(f"[{job.job_id}] yt-dlp executable not found at {self.yt_dlp_path}")
        except subprocess.TimeoutExpired:
            final_status, error_message = "Error", "Download process timed out"
            self.logger.error(f"[{job.job_id}] Download process timed out")
        except OSError as e:
            final_status, error_message = "Error", f"OS error: {e}"
            self.logger.error(f"[{job.job_id}] OS error during download: {e}")
        except Exception:
            final_status, error_message = "Error", "An unexpected exception occurred"
            self.logger.exception(f"[{job.job_id}] Exception occurred during download process")
        finally:
            with self.active_processes_lock:
                if job.job_id in self.active_processes: del self.active_processes[job.job_id]
            if not self.stop_event.is_set():
                with self.stats_lock: self.completed_jobs += 1
                self.gui_queue.put(('done', (job.job_id, final_status)))