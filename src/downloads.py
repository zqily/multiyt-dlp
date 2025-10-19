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

from .constants import SUBPROCESS_CREATION_FLAGS

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
        with self.stats_lock: self.total_jobs += len(urls)
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
            self.logger.info(f"Stopping process for {job_id} (PID: {process.pid})...")
            try:
                if sys.platform == 'win32':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, creationflags=SUBPROCESS_CREATION_FLAGS)
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except Exception as e:
                self.logger.error(f"Platform-specific kill for {job_id} failed: {e}. Attempting process.terminate().")
                try: process.terminate()
                except Exception as term_e: self.logger.error(f"process.terminate() also failed: {term_e}")
            
            self.gui_queue.put(('done', (job_id, 'Cancelled')))
            with self.active_processes_lock:
                if job_id in self.active_processes: del self.active_processes[job_id]
        
        self.cleanup_temporary_files()
        with self.stats_lock: self.total_jobs, self.completed_jobs = 0, 0
        self.gui_queue.put(('reset_progress', None))

    def _url_processor_worker(self):
        while not self.stop_event.is_set():
            try:
                url, options = self.url_processing_queue.get(timeout=1)
                try:
                    self.logger.info(f"[{threading.current_thread().name}] Started processing: {url}")
                    self._expand_url_and_queue_jobs(url, options)
                    self.logger.info(f"[{threading.current_thread().name}] Finished processing: {url}")
                except Exception:
                    url_str = url if url else "an unknown URL"
                    self.logger.exception(f"[{threading.current_thread().name}] Error processing {url_str}")
                finally:
                    self.url_processing_queue.task_done()
            except queue.Empty:
                break

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
                    self.logger.warning(f"[URL_Processor] Could not parse line: {line}")
            if video_count > 0: self.logger.info(f"Found and queued {video_count} video(s) for {url}.")
            elif not self.stop_event.is_set(): self.logger.warning(f"No videos found for URL {url}")
        except subprocess.CalledProcessError as e:
            error_output = e.output.strip() if e.output else "No output from yt-dlp."
            self.logger.error(f"yt-dlp failed to expand '{url}'. Output: {error_output}")
            self.logger.info(f"Assuming '{url}' is a single video and queuing it directly.")
            if not self.stop_event.is_set():
                job_id = str(uuid.uuid4())
                with self.stats_lock: self.total_jobs += 1
                self.gui_queue.put(('add_job', (job_id, url, "Queued", "0%")))
                self.job_queue.put((job_id, url, options.copy()))
        except Exception:
            self.logger.exception(f"An error occurred while processing {url}")

    def cleanup_temporary_files(self, path=None):
        """Cleans up temporary download files in a given directory."""
        cleanup_path = path or self.current_output_path
        if not cleanup_path or not os.path.isdir(cleanup_path): return
        temp_extensions, count = {".part", ".ytdl", ".webm"}, 0
        self.logger.info(f"Scanning '{cleanup_path}' for temp files...")
        try:
            for filename in os.listdir(cleanup_path):
                if any(filename.endswith(ext) for ext in temp_extensions):
                    try: os.remove(os.path.join(cleanup_path, filename)); count += 1
                    except OSError as e: self.logger.error(f"  - Error deleting {filename}: {e}")
        except OSError as e:
            self.logger.error(f"Error scanning directory '{cleanup_path}': {e}")
        if count > 0: self.logger.info(f"Cleanup complete. Deleted {count} temporary file(s).")

    def _start_workers(self):
        self.workers = [w for w in self.workers if w.is_alive()]
        for _ in range(self.max_concurrent_downloads - len(self.workers)):
            worker = threading.Thread(target=self._worker_thread, daemon=True, name=f"Download-Worker-{len(self.workers) + 1}")
            self.workers.append(worker); worker.start()

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
        except Exception:
            final_status, error_message = "Error", "An exception occurred"
            self.logger.exception(f"[{job_id}] Exception occurred during download process")
        finally:
            with self.active_processes_lock:
                if job_id in self.active_processes: del self.active_processes[job_id]
            if not self.stop_event.is_set():
                with self.stats_lock: self.completed_jobs += 1
                self.gui_queue.put(('done', (job_id, final_status)))