"""
Defines the Toplevel window for application settings.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
import logging

from ..constants import resource_path
from ..config import Settings
from ..controller import AppController


class SettingsWindow(tk.Toplevel):
    """A Toplevel window for managing application settings."""

    def __init__(self, master: tk.Tk, app_controller: AppController, config: Settings, yt_dlp_var: tk.StringVar, ffmpeg_var: tk.StringVar):
        """
        Initializes the Settings window.

        Args:
            master: The parent window.
            app_controller: The central application controller.
            config: The current application Settings object.
            yt_dlp_var: StringVar from main app for yt-dlp version.
            ffmpeg_var: StringVar from main app for FFmpeg status.
        """
        super().__init__(master)
        self.app_controller = app_controller
        self.config = config
        self.is_updating_dependency = False
        self.logger = logging.getLogger(__name__)

        self.title("Settings")
        self.geometry("600x480")
        self.resizable(False, False)
        self.transient(master)
        try: self.iconbitmap(resource_path('icon.ico'))
        except tk.TclError: pass

        self.yt_dlp_version_var = yt_dlp_var
        self.ffmpeg_status_var = ffmpeg_var

        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        
        task = asyncio.create_task(self.check_dependency_versions())
        task.add_done_callback(self._handle_task_exception)

    def _handle_task_exception(self, task: asyncio.Task) -> None:
        """Callback to log exceptions from background tasks."""
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            self.logger.exception(f"Exception in settings window task {task.get_name()}:")

    def _create_widgets(self):
        """Creates and lays out all widgets for the settings window."""
        settings_frame = ttk.Frame(self, padding="10"); settings_frame.pack(fill=tk.BOTH, expand=True)

        self.concurrent_var = tk.IntVar(value=self.config.max_concurrent_downloads)
        self.temp_filename_template = tk.StringVar(value=self.config.filename_template)
        ttk.Label(settings_frame, text="Max Concurrent Downloads:").grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)
        ttk.Spinbox(settings_frame, from_=1, to=20, textvariable=self.concurrent_var, width=5).grid(row=0, column=1, padx=5, pady=10, sticky=tk.W)
        ttk.Label(settings_frame, text="Filename Template:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(settings_frame, textvariable=self.temp_filename_template, width=50).grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        help_text = "Must include %(title)s or %(id)s. Cannot contain / \\ .. or be an absolute path."
        ttk.Label(settings_frame, text=help_text, font=("TkDefaultFont", 8, "italic")).grid(row=2, column=1, sticky=tk.W, padx=5)

        self.update_check_var = tk.BooleanVar(value=self.config.check_for_updates_on_startup)
        ttk.Checkbutton(settings_frame, text="Check for updates on startup", variable=self.update_check_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10, 0))

        log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        self.log_level_var = tk.StringVar(value=self.config.log_level)
        ttk.Label(settings_frame, text="File Log Level:").grid(row=4, column=0, padx=5, pady=10, sticky=tk.W)
        ttk.Combobox(settings_frame, textvariable=self.log_level_var, values=log_levels, state="readonly", width=15).grid(row=4, column=1, padx=5, pady=10, sticky=tk.W)
        log_level_help = "Sets verbosity of latest.log. Requires restart to take effect."
        ttk.Label(settings_frame, text=log_level_help, font=("TkDefaultFont", 8, "italic")).grid(row=5, column=1, sticky=tk.W, padx=5)

        update_frame = ttk.LabelFrame(settings_frame, text="Dependencies", padding=10); update_frame.grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=15); update_frame.columnconfigure(1, weight=1)
        ttk.Label(update_frame, text="yt-dlp:").grid(row=0, column=0, sticky=tk.W, padx=5); ttk.Label(update_frame, textvariable=self.yt_dlp_version_var).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(update_frame, text="FFmpeg:").grid(row=1, column=0, sticky=tk.W, padx=5); ttk.Label(update_frame, textvariable=self.ffmpeg_status_var, wraplength=400).grid(row=1, column=1, sticky=tk.W, padx=5)
        update_buttons_frame = ttk.Frame(update_frame); update_buttons_frame.grid(row=2, column=0, columnspan=2, pady=(10,0))
        self.yt_dlp_update_button = ttk.Button(update_buttons_frame, text="Update yt-dlp", command=lambda: asyncio.create_task(self.start_yt_dlp_update())); self.yt_dlp_update_button.pack(side=tk.LEFT, padx=5)
        self.ffmpeg_update_button = ttk.Button(update_buttons_frame, text="Download/Update FFmpeg", command=lambda: asyncio.create_task(self.start_ffmpeg_update())); self.ffmpeg_update_button.pack(side=tk.LEFT, padx=5)

        buttons_frame = ttk.Frame(settings_frame)
        buttons_frame.grid(row=7, column=0, columnspan=2, pady=15, sticky=tk.E)
        ttk.Button(buttons_frame, text="Save", command=self._save_and_close).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT)

    async def check_dependency_versions(self):
        """Asks the controller to fetch dependency versions."""
        self.yt_dlp_version_var.set("Checking...")
        self.ffmpeg_status_var.set("Checking...")
        await self.app_controller.get_dependency_versions()

    def _save_and_close(self):
        """Validates settings, saves them, and closes the window."""
        if self.is_updating_dependency:
            messagebox.showwarning("Busy", "Cannot save settings while updating.", parent=self)
            return

        new_settings_data = {
            'max_concurrent_downloads': self.concurrent_var.get(),
            'filename_template': self.temp_filename_template.get().strip(),
            'log_level': self.log_level_var.get(),
            'check_for_updates_on_startup': self.update_check_var.get()
        }

        success, message = self.app_controller.save_settings(new_settings_data)
        if success:
            messagebox.showinfo("Settings Saved", message, parent=self)
            self.destroy()
        else:
            messagebox.showerror("Validation Error", message, parent=self)

    def _toggle_update_buttons(self, enabled: bool):
        """Enables or disables the dependency update buttons."""
        state = 'normal' if enabled else 'disabled'
        for btn in [self.yt_dlp_update_button, self.ffmpeg_update_button]:
            if btn and btn.winfo_exists(): btn.config(state=state)

    async def start_yt_dlp_update(self):
        """Starts the yt-dlp update process."""
        await self._start_dep_update("yt-dlp", "Download latest yt-dlp?")

    async def start_ffmpeg_update(self):
        """Starts the FFmpeg download/update process."""
        await self._start_dep_update("ffmpeg", "Download latest FFmpeg? (Large file)")

    async def _start_dep_update(self, dep_type: str, message: str):
        """Generic method to start a dependency update."""
        if self.is_updating_dependency: return
        if messagebox.askyesno(f"Confirm Update", message, parent=self):
            self.is_updating_dependency = True
            self._toggle_update_buttons(False)
            
            await self.app_controller.initiate_dependency_download(dep_type)
            
            if self.winfo_exists():
                self.is_updating_dependency = False
                self._toggle_update_buttons(True)
                await self.check_dependency_versions()