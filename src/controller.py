"""
Defines the main AppController class, which orchestrates the application's logic.
"""
import queue
import logging
import threading
import os
import sys
import subprocess
import webbrowser
from pydantic import ValidationError
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from .dependencies import DependencyManager
from .downloads import DownloadManager
from .app_updater import AppUpdater
from .jobs import DownloadJob
from .config import ConfigManager, Settings
from .constants import SUBPROCESS_CREATION_FLAGS


class AppController:
    """The central controller for the application's business logic."""

    def __init__(self, gui_queue: queue.Queue, config_manager: ConfigManager, config: Settings):
        """
        Initializes the AppController.

        Args:
            gui_queue: The queue for sending messages to the GUI.
            config_manager: The manager for handling configuration persistence.
            config: The loaded application settings.
        """
        self.gui_queue = gui_queue
        self.config_manager = config_manager
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Application State
        self.job_store: Dict[str, DownloadJob] = {}
        self.is_downloading: bool = False
        self.pending_download_task: Optional[Tuple[List[str], Dict[str, Any]]] = None

        # Backend Managers
        self.dep_manager = DependencyManager(self._on_manager_event)
        self.download_manager = DownloadManager(self._on_manager_event)
        self.app_updater = AppUpdater(self._on_manager_event, self.config)

        # Initial checks
        if self.config.check_for_updates_on_startup:
            self.check_for_updates()
        if not self.dep_manager.yt_dlp_path:
            self.gui_queue.put(('initiate_dependency_prompt', 'yt-dlp'))

    def _on_manager_event(self, event: Tuple[str, Any]):
        """
        Handles events from backend managers, updates state, and forwards synthesized events to GUI.
        This method runs in the manager's thread.
        """
        msg_type, value = event

        if msg_type == 'add_job':
            job: DownloadJob = value
            self.job_store[job.job_id] = job
        elif msg_type == 'update_job':
            job_id, column, new_value = value
            if job_id in self.job_store and hasattr(self.job_store[job_id], column):
                setattr(self.job_store[job_id], column, new_value)
        elif msg_type == 'done':
            job_id, status = value
            if job_id in self.job_store:
                self.job_store[job_id].status = status
        elif msg_type == 'dependency_done':
            self._handle_dependency_result(value)
            self.gui_queue.put(('close_dependency_progress_window', None))
            self.gui_queue.put(('show_message', {
                'type': 'info' if value.get('success') else 'error',
                'title': "Success" if value.get('success') else "Download Failed",
                'message': f"{value.get('type','Dependency').upper()} downloaded successfully." if value.get('success') else f"An error occurred: {value.get('error')}"
            }))
        else:
            # Forward other events directly (e.g., dependency_progress, new_version_available)
            self.gui_queue.put(event)

        # After state-changing events, send a consolidated update to the GUI
        if msg_type in ['add_job', 'update_job', 'done']:
            self._update_and_send_progress()

    def _update_and_send_progress(self):
        """Calculates progress and sends a single update message to the GUI."""
        completed, total = self.download_manager.get_stats()
        jobs_in_order = list(self.job_store.values())

        self.gui_queue.put(('update_progress_view', {
            'completed': completed,
            'total': total,
            'jobs': jobs_in_order
        }))

        if total > 0 and completed >= total and self.is_downloading:
            self.logger.info("--- All queued downloads are complete! ---")
            self.is_downloading = False
            self.gui_queue.put(('update_download_state', {'is_downloading': False}))

    def _handle_dependency_result(self, result: Dict[str, Any]):
        """Handles the result of a dependency download attempt."""
        dep_type = result.get('type')
        if dep_type == 'yt-dlp':
            self.dep_manager.find_yt_dlp()  # Re-find path
            if not self.dep_manager.yt_dlp_path:
                self.gui_queue.put(('critical_error', "yt-dlp is required. The application will now exit."))
        elif dep_type == 'ffmpeg':
            self.dep_manager.find_ffmpeg()  # Re-find path
            if result.get('success') and self.pending_download_task:
                self.logger.info("FFmpeg installed. Resuming queued downloads...")
                urls, options = self.pending_download_task
                self.pending_download_task = None
                self.start_downloads(urls, options)
            elif not result.get('success') and self.pending_download_task:
                self.logger.warning("FFmpeg download failed. Aborting pending downloads.")
                self.pending_download_task = None
                self.is_downloading = False
                self.gui_queue.put(('update_download_state', {'is_downloading': False}))

    def start_downloads(self, urls: List[str], options: Dict[str, Any]):
        """Validates conditions and starts the download process."""
        if self.is_downloading:
            return

        if not self.dep_manager.yt_dlp_path:
            self.gui_queue.put(('show_message', {'type': 'error', 'title': 'Error', 'message': 'Cannot start: yt-dlp is not available.'}))
            return

        output_path = options['output_path']
        try:
            (output_path / f".writetest_{os.getpid()}").touch()
            (output_path / f".writetest_{os.getpid()}").unlink()
        except (IOError, OSError) as e:
            self.gui_queue.put(('show_message', {'type': 'error', 'title': 'Permission Error', 'message': f"Cannot write to directory:\n{e}"}))
            return

        is_audio_dl = options.get('download_type') == 'audio'
        if (options.get('embed_thumbnail') or is_audio_dl) and not self.dep_manager.ffmpeg_path:
            self.pending_download_task = (urls, options)
            self.is_downloading = True
            self.gui_queue.put(('update_download_state', {'is_downloading': True}))
            self.logger.info("FFmpeg is required for the selected options. Prompting user to download.")
            self.gui_queue.put(('initiate_dependency_prompt', 'ffmpeg'))
            return

        self.is_downloading = True
        self.gui_queue.put(('update_download_state', {'is_downloading': True}))
        self.gui_queue.put(('set_status', "Processing URLs..."))
        self.logger.info("--- Queuing new URLs ---")

        self.download_manager.set_config(self.config.max_concurrent_downloads, self.dep_manager.yt_dlp_path, self.dep_manager.ffmpeg_path)
        self.download_manager.start_downloads(urls, options)

    def stop_all_downloads(self):
        """Stops all active and queued downloads."""
        if not self.is_downloading:
            return
        self.gui_queue.put(('set_status', "Stopping all downloads..."))
        self.download_manager.stop_all_downloads()
        self.job_store.clear()
        self.is_downloading = False
        self.gui_queue.put(('update_download_state', {'is_downloading': False}))
        self.gui_queue.put(('reset_progress_view', None))

    def clear_completed_jobs(self):
        """Removes all finished (completed, failed, cancelled) jobs from the list."""
        finished_statuses = {'completed', 'failed', 'cancelled', 'error'}
        jobs_to_remove = [job_id for job_id, job in self.job_store.items()
                          if any(s in job.status.lower() for s in finished_statuses)]

        for job_id in jobs_to_remove:
            del self.job_store[job_id]

        self.gui_queue.put(('remove_jobs_from_view', jobs_to_remove))
        self._update_and_send_progress()
        self.logger.info(f"Cleared {len(jobs_to_remove)} finished item(s) from the list.")

    def add_jobs_for_retry(self, job_ids_to_retry: List[str]):
        """Retries a list of failed jobs by their IDs."""
        jobs_to_retry = [self.job_store[item_id] for item_id in job_ids_to_retry if item_id in self.job_store]
        if not jobs_to_retry:
            self.logger.warning("Could not find job data for selected failed items.")
            return

        for job_id in job_ids_to_retry:
            del self.job_store[job_id]

        self.gui_queue.put(('remove_jobs_from_view', job_ids_to_retry))
        self.is_downloading = True
        self.gui_queue.put(('update_download_state', {'is_downloading': True}))
        self.download_manager.add_jobs(jobs_to_retry)

    def on_app_closing(self, ui_settings: Dict[str, Any]):
        """Handles application shutdown logic."""
        self.logger.info("Application closing.")
        if self.is_downloading:
            self.download_manager.stop_all_downloads()

        # Update config from UI state before saving
        self.config.download_type = ui_settings.get('download_type', self.config.download_type)
        self.config.video_resolution = ui_settings.get('video_resolution', self.config.video_resolution)
        self.config.audio_format = ui_settings.get('audio_format', self.config.audio_format)
        self.config.embed_thumbnail = ui_settings.get('embed_thumbnail', self.config.embed_thumbnail)
        self.config.last_output_path = ui_settings.get('last_output_path', self.config.last_output_path)

        self.config_manager.save(self.config)

    def save_settings(self, new_settings_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validates and saves new settings."""
        try:
            new_settings = self.config.model_copy(update=new_settings_data)
            self.config_manager.save(new_settings)
            self.config.__dict__.update(new_settings.model_dump())
            self.download_manager.set_config(self.config.max_concurrent_downloads, self.dep_manager.yt_dlp_path, self.dep_manager.ffmpeg_path)
            return True, "Settings have been saved."
        except ValidationError as e:
            error_details = e.errors()[0]
            field, msg = error_details['loc'][0], error_details['msg']
            return False, f"Error in field '{field}': {msg}"

    def initiate_dependency_download(self, dep_type: str):
        """Starts the download process for a dependency."""
        self.gui_queue.put(('show_dependency_progress_window', f"Downloading {dep_type.upper()}"))
        if dep_type == "yt-dlp":
            self.dep_manager.install_or_update_yt_dlp()
        else:
            self.dep_manager.download_ffmpeg()

    def cancel_dependency_download(self):
        """Cancels an in-progress dependency download."""
        self.dep_manager.cancel_download()

    def check_for_updates(self):
        """Starts the application update check."""
        self.app_updater.check_for_updates()

    def skip_update_version(self, version: str):
        """Stores a skipped version in config and saves it."""
        self.config.skipped_update_version = version
        self.config_manager.save(self.config)

    def get_dependency_versions(self):
        """Asynchronously fetches dependency versions and sends them to the GUI."""
        def check_and_report(dep_type: str, path: Optional[Path]):
            version = self.dep_manager.get_version(path)
            self.gui_queue.put(('update_dependency_version', {'type': dep_type, 'version': version}))

        threading.Thread(target=check_and_report, args=('yt-dlp', self.dep_manager.yt_dlp_path), daemon=True).start()
        threading.Thread(target=check_and_report, args=('ffmpeg', self.dep_manager.ffmpeg_path), daemon=True).start()

    def open_folder(self, path_str: str):
        """Opens the specified folder in the system's file explorer."""
        path = Path(path_str)
        if not path.is_dir():
            self.gui_queue.put(('show_message', {'type': 'error', 'title': 'Error', 'message': f"Folder does not exist:\n{path}"}))
            return
        try:
            if sys.platform == 'win32':
                os.startfile(str(path))
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(path)], check=True)
            else:
                subprocess.run(['xdg-open', str(path)], check=True)
        except (OSError, subprocess.CalledProcessError) as e:
            self.gui_queue.put(('show_message', {'type': 'error', 'title': 'Error', 'message': f"Failed to open folder:\n{e}"}))

    def open_link(self, url: str):
        """Opens a URL in the default web browser."""
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()