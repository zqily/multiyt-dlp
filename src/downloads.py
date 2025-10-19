import queue
import threading
import subprocess
import re
import os
import sys
import json
import uuid
import signal
import logging

from .constants import SUBPROCESS_CREATION_FLAGS, TEMP_DOWNLOAD_DIR
from .url_extractor import URLInfoExtractor
from .exceptions import URLExtractionError, DownloadCancelledError

class DownloadManager:
    """Manages the download queue, worker threads, and yt-dlp processes."""
    def __init__(self, gui_queue):
        self.gui_queue = gui_queue
        self.logger = logging.getLogger(__name__)
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
            self.logger.error("yt-dlp path is not set. Cannot start downloads.")
            return
        with self.stats_lock: self.completed_jobs, self.total_jobs = 0, 0
        self.gui_queue.put(('reset_progress', None))
        self.current_output_path = options['output_path']
        self.stop_event.clear()
        
        # Start download workers immediately. They will begin processing jobs as soon as they appear in the job_queue.
        self._start_workers()

        for url in urls:
            self.url_processing_queue.put((url, options))
        
        # This monitor thread signals the GUI when all initial URLs have finished processing,
        # allowing the URL input box to be re-enabled.
        def monitor_url_queue():
            self.url_processing_queue.join()
            if not self.stop_event.is_set():
                self.gui_queue.put(('url_processing_done', None))

        threading.Thread(target=monitor_url_queue, daemon=True, name="URL-Queue-Monitor").start()
        
        num_url_processors = min(8, len(urls))
        for i in range(num_url_processors):
            thread = threading.Thread(target=self._url_processor_worker, daemon=True, name=f"URL-Processor-{i+1}")
            thread.start()

    def add_jobs(self, urls, options):
        if not self.yt_dlp_path:
            self.logger.error("yt-dlp path is not set. Cannot add jobs.")
            return
        self.logger.info(f"Retrying {len(urls)} failed download(s).")
        with self.stats_lock:
            self.total_jobs += len(urls)
        for video_url in urls:
            if self.stop_event.is_set(): break
            job_id = str(uuid.uuid4())
            self.gui_queue.put(('add_job', (job_id, video_url, "Queued", "0%")))
            self.job_queue.put((job_id, video_url, options.copy()))
        self._start_workers()

    def stop_all_downloads(self):
        self.logger.info("STOP signal received. Terminating downloads...")
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
            self.logger.info(f"Requesting graceful shutdown for {job_id} (PID: {process.pid})...")
            try:
                if sys.platform == 'win32':
                    os.kill(process.pid, signal.CTRL_C_EVENT)
                else:
                    # os.setsid makes the process a group leader, so we can kill the whole group
                    os.killpg(os.getpgid(process.pid), signal.SIGINT)
                
                process.wait(timeout=10)
                self.logger.info(f"Process {job_id} (PID: {process.pid}) terminated gracefully.")
            except (subprocess.TimeoutExpired, OSError, ProcessLookupError) as e:
                self.logger.warning(f"Graceful shutdown for {job_id} failed: {e}. Forcing termination...")
                try:
                    # Fallback to forceful termination
                    if sys.platform == 'win32':
                        subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, creationflags=SUBPROCESS_CREATION_FLAGS)
                    else:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM) # SIGTERM is less abrupt than SIGKILL
                except Exception as kill_e:
                    self.logger.error(f"Forceful termination for {job_id} also failed: {kill_e}")
            
            self.gui_queue.put(('done', (job_id, 'Cancelled')))
            with self.active_processes_lock:
                if job_id in self.active_processes: del self.active_processes[job_id]
        
        self.cleanup_temporary_files()
        with self.stats_lock: self.total_jobs, self.completed_jobs = 0, 0
        self.gui_queue.put(('reset_progress', None))

    def _url_processor_worker(self):
        if not self.yt_dlp_path:
            self.logger.critical("URL processor started without a valid yt-dlp path. Aborting worker.")
            return
        extractor = URLInfoExtractor(self.yt_dlp_path, self.stop_event)
        while not self.stop_event.is_set():
            try:
                url, options = self.url_processing_queue.get(timeout=1)
                thread_name = threading.current_thread().name
                try:
                    self.logger.info(f"[{thread_name}] Started processing: {url}")
                    videos_to_queue, was_partial = extractor.extract_videos(url)
                    
                    if videos_to_queue:
                        self.logger.info(f"[{thread_name}] Found {len(videos_to_queue)} video(s) for '{url}'.")
                        for video in videos_to_queue:
                            if self.stop_event.is_set(): break
                            job_id = str(uuid.uuid4())
                            with self.stats_lock:
                                self.total_jobs += 1
                            self.gui_queue.put(('add_job', (job_id, video['url'], "Queued", "0%")))
                            self.job_queue.put((job_id, video['url'], options.copy()))

                    if was_partial:
                        self.logger.warning(f"[{thread_name}] Playlist expansion for '{url}' was incomplete or failed.")
                        job_id = str(uuid.uuid4())
                        self.gui_queue.put(('add_job', (job_id, url, "Error: Incomplete playlist", "N/A")))
                        self.gui_queue.put(('done', (job_id, "Failed")))

                except DownloadCancelledError:
                    self.logger.info(f"[{thread_name}] URL processing for '{url}' was cancelled.")
                except URLExtractionError as e:
                    self.logger.error(f"[{thread_name}] Failed to process '{url}': {e}")
                    job_id = str(uuid.uuid4())
                    self.gui_queue.put(('add_job', (job_id, url, f"Error: {e}", "N/A")))
                    self.gui_queue.put(('done', (job_id, "Failed")))
                except Exception:
                    self.logger.exception(f"[{thread_name}] Unhandled error processing URL: {url}")
                finally:
                    self.url_processing_queue.task_done()
            except queue.Empty:
                break

    def cleanup_temporary_files(self):
        """Cleans up temporary download files in the dedicated temp directory."""
        cleanup_path = TEMP_DOWNLOAD_DIR
        if not os.path.isdir(cleanup_path): return
        temp_extensions, count = {".part", ".ytdl", ".webm"}, 0
        self.logger.info(f"Scanning '{cleanup_path}' for temp files...")
        try:
            for filename in os.listdir(cleanup_path):
                if any(filename.endswith(ext) for ext in temp_extensions):
                    try:
                        os.remove(os.path.join(cleanup_path, filename))
                        count += 1
                    except OSError as e:
                        self.logger.error(f"  - Error deleting {filename}: {e}")
        except OSError as e:
            self.logger.error(f"Error scanning directory '{cleanup_path}': {e}")
        if count > 0:
            self.logger.info(f"Cleanup complete. Deleted {count} temporary file(s).")

    def _start_workers(self):
        self.workers = [w for w in self.workers if w.is_alive()]
        for _ in range(self.max_concurrent_downloads - len(self.workers)):
            worker = threading.Thread(target=self._worker_thread, daemon=True, name=f"Download-Worker-{len(self.workers) + 1}")
            self.workers.append(worker)
            worker.start()

    def _worker_thread(self):
        while not self.stop_event.is_set():
            try:
                job_id, url, options = self.job_queue.get(timeout=1)
                try:
                    if self.stop_event.is_set():
                        self.gui_queue.put(('done', (job_id, 'Cancelled')))
                        continue
                    self.gui_queue.put(('update_job', (job_id, 'status', 'Downloading')))
                    self._run_download_process(job_id, url, options)
                finally:
                    self.job_queue.task_done()
            except queue.Empty:
                continue

    def _build_yt_dlp_command(self, url, options):
        """Builds the full yt-dlp command list based on options."""
        command = [
            self.yt_dlp_path,
            '--newline',
            '--progress-template', 'PROGRESS::%(progress._percent_str)s',
            '--no-mtime',
            '--paths', f'temp:{TEMP_DOWNLOAD_DIR}',
            '-o', os.path.join(options['output_path'], options['filename_template'])
        ]

        if self.ffmpeg_path:
            command.extend(['--ffmpeg-location', os.path.dirname(self.ffmpeg_path)])

        if options['download_type'] == 'video':
            res = options['video_resolution']
            f_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            if res.lower() != 'best':
                f_str = f'bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best[height<={res}]'
            command.extend(['-f', f_str])
        elif options['download_type'] == 'audio':
            audio_format = options['audio_format']
            command.extend(['-f', 'bestaudio/best', '-x'])
            if audio_format != 'best':
                command.extend(['--audio-format', audio_format])
                if audio_format == 'mp3':
                    command.extend(['--audio-quality', '192K'])

        if options['embed_thumbnail']:
            command.append('--embed-thumbnail')

        command.append(url)
        return command

    def _run_download_process(self, job_id, url, options):
        error_message, final_status = None, 'Failed'
        try:
            command = self._build_yt_dlp_command(url, options)
            
            popen_kwargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT, 'text': True, 'encoding': 'utf-8', 'errors': 'replace', 'bufsize': 1}
            if sys.platform == 'win32':
                popen_kwargs['creationflags'] = SUBPROCESS_CREATION_FLAGS | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs['preexec_fn'] = os.setsid
            
            with self.active_processes_lock:
                if self.stop_event.is_set(): return
                process = subprocess.Popen(command, **popen_kwargs)
                self.active_processes[job_id] = process
            
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    if self.stop_event.is_set(): break
                    clean_line = line.strip()
                    self.logger.debug(f"[{job_id}] {clean_line}")
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
                
                process.stdout.close()
            
            return_code = process.wait()
            if self.stop_event.is_set(): return
            if return_code == 0: final_status = 'Completed'
            elif error_message: final_status = f"Failed: {error_message[:60]}"
        except FileNotFoundError:
            final_status, error_message = "Error", "yt-dlp executable not found"
            self.logger.error(f"[{job_id}] yt-dlp executable not found at {self.yt_dlp_path}")
        except Exception:
            final_status, error_message = "Error", "An unexpected exception occurred"
            self.logger.exception(f"[{job_id}] Exception occurred during download process")
        finally:
            with self.active_processes_lock:
                if job_id in self.active_processes: del self.active_processes[job_id]
            if not self.stop_event.is_set():
                with self.stats_lock: self.completed_jobs += 1
                self.gui_queue.put(('done', (job_id, final_status)))