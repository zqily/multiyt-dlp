"""
Defines the main AppController class, which orchestrates the application's logic.
"""
import asyncio
import logging
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

    def __init__(self, config_manager: ConfigManager, config: Settings):
        """
        Initializes the AppController.

        Args:
            config_manager: The manager for handling configuration persistence.
            config: The loaded application settings.
        """
        self.config_manager = config_manager
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.gui = None  # Will be set by the GUI application

        # Application State
        self.job_store: Dict[str, DownloadJob] = {}
        self.is_downloading: bool = False
        self.pending_download_task: Optional[Tuple[List[str], Dict[str, Any]]] = None

        # Backend Managers
        self.dep_manager = DependencyManager(self._on_manager_event)
        self.download_manager = DownloadManager(self._on_manager_event)
        self.app_updater = AppUpdater(self._on_manager_event, self.config)

    def set_gui(self, gui):
         """Sets the GUI instance for direct callbacks and runs initial checks."""
         self.gui = gui

    async def run_startup_checks(self):
        """Runs initial async checks after the event loop has started."""
        # Defer synchronous I/O to avoid blocking the event loop on startup.
        await self.dep_manager.initialize()

        # Initialize managers that need async setup
        await self.download_manager.initialize()

        if self.config.check_for_updates_on_startup:
             task = asyncio.create_task(self.check_for_updates())
             task.add_done_callback(self._handle_task_exception)
        if not self.dep_manager.yt_dlp_path:
            task = asyncio.create_task(self.gui.initiate_dependency_prompt('yt-dlp'))
            task.add_done_callback(self._handle_task_exception)

    def _handle_task_exception(self, task: asyncio.Task) -> None:
        """Callback to log exceptions from fire-and-forget tasks."""
        try:
            task.result()
        except asyncio.CancelledError:
            pass  # Expected
        except Exception:
            self.logger.exception(f"Exception in background task {task.get_name()}:")

    async def _on_manager_event(self, event: Tuple[str, Any]):
        """
        Handles events from backend managers, updates state, and calls GUI methods.
        This method is async and called directly by the managers.
        """
        msg_type, value = event
        handler_map = {
            'add_job': self._handle_add_job,
            'update_job': self._handle_update_job,
            'done': self._handle_done,
            'new_version_available': self._handle_new_version_available,
            'url_processing_done': self._handle_url_processing_done,
            'dependency_progress': self._handle_dependency_progress,
        }
        handler = handler_map.get(msg_type)
        if handler:
            await handler(value)
        else:
            self.logger.warning(f"Unhandled manager event type: {msg_type}")

    async def _handle_add_job(self, job: DownloadJob):
        self.job_store[job.job_id] = job
        await self._update_and_send_progress()

    async def _handle_update_job(self, value: Tuple[str, str, Any]):
        job_id, column, new_value = value
        if job_id in self.job_store and hasattr(self.job_store[job_id], column):
            setattr(self.job_store[job_id], column, new_value)
        await self._update_and_send_progress()

    async def _handle_done(self, value: Tuple[str, str]):
        job_id, status = value
        if job_id in self.job_store:
            self.job_store[job_id].status = status
        await self._update_and_send_progress()

    async def _handle_new_version_available(self, value: Dict[str, str]):
        await self.gui.show_update_dialog(value['version'], value['url'])

    async def _handle_url_processing_done(self, _):
        await self.gui.toggle_url_input_state(True)

    async def _handle_dependency_progress(self, value: Dict[str, Any]):
        await self.gui.update_dependency_progress(value)

    async def _update_and_send_progress(self):
        """Calculates progress and sends a single update message to the GUI."""
        completed, total = await self.download_manager.get_stats()
        jobs_in_order = list(self.job_store.values())

        await self.gui.update_progress_view({
            'completed': completed,
            'total': total,
            'jobs': jobs_in_order
        })

        if total > 0 and completed >= total and self.is_downloading:
            self.logger.info("--- All queued downloads are complete! ---")
            self.is_downloading = False
            await self.gui.update_button_states(False)

    async def _handle_dependency_result(self, result: Dict[str, Any]):
        """Handles the result of a dependency download attempt."""
        dep_type = result.get('type')
        if dep_type == 'yt-dlp':
            await asyncio.to_thread(self.dep_manager.find_yt_dlp)  # Re-find path
            if not self.dep_manager.yt_dlp_path:
                await self.gui.show_critical_error("yt-dlp is required. The application will now exit.")
        elif dep_type == 'ffmpeg':
            await asyncio.to_thread(self.dep_manager.find_ffmpeg)  # Re-find path
            if result.get('success') and self.pending_download_task:
                self.logger.info("FFmpeg installed. Resuming queued downloads...")
                urls, options = self.pending_download_task
                self.pending_download_task = None
                await self.start_downloads(urls, options)
            elif not result.get('success') and self.pending_download_task:
                self.logger.warning("FFmpeg download failed. Aborting pending downloads.")
                self.pending_download_task = None
                self.is_downloading = False
                await self.gui.update_button_states(False)

    async def start_downloads(self, urls: List[str], options: Dict[str, Any]):
        """Validates conditions and starts the download process."""
        if self.is_downloading: return

        if not self.dep_manager.yt_dlp_path:
            await self.gui.show_message({'type': 'error', 'title': 'Error', 'message': 'Cannot start: yt-dlp is not available.'})
            return

        output_path = options['output_path']
        try:
            test_file = output_path / f".writetest_{os.getpid()}"
            await asyncio.to_thread(test_file.touch)
            await asyncio.to_thread(test_file.unlink)
        except (IOError, OSError) as e:
            await self.gui.show_message({'type': 'error', 'title': 'Permission Error', 'message': f"Cannot write to directory:\n{e}"})
            return

        is_audio_dl = options.get('download_type') == 'audio'
        if (options.get('embed_thumbnail') or is_audio_dl) and not self.dep_manager.ffmpeg_path:
            self.pending_download_task = (urls, options)
            self.is_downloading = True
            await self.gui.update_button_states(True)
            self.logger.info("FFmpeg is required for the selected options. Prompting user to download.")
            await self.gui.initiate_dependency_prompt('ffmpeg')
            return

        self.is_downloading = True
        await self.gui.update_button_states(True)
        await self.gui.set_status("Processing URLs...")
        self.logger.info("--- Queuing new URLs ---")

        self.download_manager.set_config(self.config.max_concurrent_downloads, self.dep_manager.yt_dlp_path, self.dep_manager.ffmpeg_path)
        await self.download_manager.start_downloads(urls, options)

    async def stop_all_downloads(self):
        """Stops all active and queued downloads."""
        if not self.is_downloading: return
        await self.gui.set_status("Stopping all downloads...")
        await self.download_manager.stop_all_downloads()
        self.job_store.clear()
        self.is_downloading = False
        await self.gui.update_button_states(False)
        await self.gui.reset_progress_view()

    async def clear_completed_jobs(self):
        """Removes all finished (completed, failed, cancelled) jobs from the list."""
        finished_statuses = {'completed', 'failed', 'cancelled', 'error'}
        jobs_to_remove = [job_id for job_id, job in self.job_store.items()
                          if any(s in job.status.lower() for s in finished_statuses)]

        for job_id in jobs_to_remove:
            del self.job_store[job_id]

        await self.gui.remove_jobs_from_view(jobs_to_remove)
        await self._update_and_send_progress()
        self.logger.info(f"Cleared {len(jobs_to_remove)} finished item(s) from the list.")

    async def add_jobs_for_retry(self, job_ids_to_retry: List[str]):
        """Retries a list of failed jobs by their IDs."""
        jobs_to_retry = [self.job_store[item_id] for item_id in job_ids_to_retry if item_id in self.job_store]
        if not jobs_to_retry:
            self.logger.warning("Could not find job data for selected failed items.")
            return

        for job_id in job_ids_to_retry:
            del self.job_store[job_id]

        await self.gui.remove_jobs_from_view(job_ids_to_retry)
        self.is_downloading = True
        await self.gui.update_button_states(True)
        await self.download_manager.add_jobs(jobs_to_retry)

    async def on_app_closing(self, ui_settings: Dict[str, Any]):
        """Handles application shutdown logic."""
        self.logger.info("Application closing.")
        if self.is_downloading:
            await self.download_manager.stop_all_downloads()

        self.config.download_type = ui_settings.get('download_type', self.config.download_type)
        self.config.video_resolution = ui_settings.get('video_resolution', self.config.video_resolution)
        self.config.audio_format = ui_settings.get('audio_format', self.config.audio_format)
        self.config.embed_thumbnail = ui_settings.get('embed_thumbnail', self.config.embed_thumbnail)
        self.config.embed_metadata = ui_settings.get('embed_metadata', self.config.embed_metadata)
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

    async def initiate_dependency_download(self, dep_type: str):
        """Starts the download process for a dependency and handles the result."""
        await self.gui.show_dependency_progress_window(f"Downloading {dep_type.upper()}")
        try:
            if dep_type == "yt-dlp":
                result = await self.dep_manager.install_or_update_yt_dlp()
            else:
                result = await self.dep_manager.download_ffmpeg()
        except Exception as e:
            self.logger.exception(f"Error during dependency download for {dep_type}")
            result = {'type': dep_type, 'success': False, 'error': str(e)}

        await self.gui.close_dependency_progress_window()
        await self.gui.show_message({
            'type': 'info' if result.get('success') else 'error',
            'title': "Success" if result.get('success') else "Download Failed",
            'message': f"{result.get('type','Dependency').upper()} downloaded successfully." if result.get('success') else f"An error occurred: {result.get('error')}"
        })
        await self._handle_dependency_result(result)

    def cancel_dependency_download(self):
        """Cancels an in-progress dependency download."""
        self.dep_manager.cancel_download()

    async def check_for_updates(self):
        """Starts the application update check."""
        await self.app_updater.check_for_updates()

    def skip_update_version(self, version: str):
        """Stores a skipped version in config and saves it."""
        self.config.skipped_update_version = version
        self.config_manager.save(self.config)

    async def get_dependency_versions(self):
        """Asynchronously fetches dependency versions and sends them to the GUI."""
        async def check_and_report(dep_type: str, path: Optional[Path]):
            version = await self.dep_manager.get_version(path)
            await self.gui.update_dependency_version({'type': dep_type, 'version': version})

        await asyncio.gather(
            check_and_report('yt-dlp', self.dep_manager.yt_dlp_path),
            check_and_report('ffmpeg', self.dep_manager.ffmpeg_path)
        )

    async def open_folder(self, path_str: str):
        """Opens the specified folder in the system's file explorer."""
        path = Path(path_str)
        if not await asyncio.to_thread(path.is_dir):
            await self.gui.show_message({'type': 'error', 'title': 'Error', 'message': f"Folder does not exist:\n{path}"})
            return
        try:
            if sys.platform == 'win32':
                await asyncio.to_thread(os.startfile, str(path))
            elif sys.platform == 'darwin':
                await asyncio.to_thread(subprocess.run, ['open', str(path)], check=True)
            else:
                await asyncio.to_thread(subprocess.run, ['xdg-open', str(path)], check=True)
        except (OSError, subprocess.CalledProcessError) as e:
            await self.gui.show_message({'type': 'error', 'title': 'Error', 'message': f"Failed to open folder:\n{e}"})

    async def open_link(self, url: str):
        """Opens a URL in the default web browser."""
        await asyncio.to_thread(webbrowser.open, url)