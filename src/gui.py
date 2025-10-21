"""The main application class, handling the Tkinter GUI and event loop."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import queue
import sys
import urllib.parse
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from ._version import __version__
from .constants import resource_path
from .controller import AppController
from .jobs import DownloadJob
from .config import Settings
from .gui_components.settings_window import SettingsWindow
from .gui_components.dependency_progress_window import DependencyProgressWindow
from .gui_components.job_context_menu import JobContextMenu


class SegmentedProgressBar(tk.Canvas):
    """A custom progress bar widget that shows individual job statuses as colored segments."""
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.config(height=20, highlightthickness=0)
        self.jobs: List[DownloadJob] = []
        self.color_map = {
            'completed': 'lawn green',
            'active': 'gold',
            'failed': 'tomato',
            'cancelled': 'light grey',
            'queued': 'light sky blue'
        }

    def _get_job_color(self, job_status: str) -> str:
        """Determines the segment color based on the job's status string."""
        status_lower = job_status.lower()
        if 'completed' in status_lower: return self.color_map['completed']
        if any(s in status_lower for s in ['downloading', 'merging', 'extracting', 'embedding', 'fixing', 'writing', 'metadata']): return self.color_map['active']
        if any(s in status_lower for s in ['failed', 'error']): return self.color_map['failed']
        if 'cancelled' in status_lower: return self.color_map['cancelled']
        if 'queued' in status_lower: return self.color_map['queued']
        return 'white'

    def update_progress(self, jobs: List[DownloadJob]):
        """Receives a new list of jobs and triggers a redraw."""
        self.jobs = sorted(jobs, key=lambda j: j.job_id) # Sort for consistent order
        self._draw()

    def _draw(self):
        """Clears the canvas and redraws all job segments."""
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if not self.jobs or width <= 1 or height <= 1: return

        total_jobs = len(self.jobs)
        segment_width = width / total_jobs
        for i, job in enumerate(self.jobs):
            x1, y1, x2, y2 = i * segment_width, 0, (i + 1) * segment_width, height
            color = self._get_job_color(job.status)
            self.create_rectangle(x1, y1, x2, y2, fill=color, outline=color)

    def clear(self):
        """Clears all jobs and the canvas."""
        self.jobs = []
        self._draw()

    def _on_resize(self, event):
        """Redraws the bar when the widget is resized."""
        self._draw()


class YTDlpDownloaderApp:
    """The main application class, handling the Tkinter GUI and event loop."""
    MAX_LOG_LINES = 2000

    def __init__(self, root: tk.Tk, gui_queue: queue.Queue, app_controller: AppController, config: Settings):
        """
        Initializes the main application GUI.

        Args:
            root: The root Tkinter window.
            gui_queue: The queue for cross-thread GUI communication.
            app_controller: The central application controller.
            config: The loaded application settings.
        """
        self.root = root
        self.root.title(f"Multiyt-dlp v{__version__}"); self.root.geometry("850x780")
        self.logger = logging.getLogger(__name__)
        try: self.root.iconbitmap(resource_path('icon.ico'))
        except tk.TclError: self.logger.warning("Could not load 'icon.ico'.")

        self.gui_queue = gui_queue
        self.log_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(name)-25s - %(message)s')
        self.app_controller = app_controller
        self.config = config

        self.settings_win: Optional[SettingsWindow] = None
        self.update_dialog: Optional[tk.Toplevel] = None
        self.is_destroyed = False

        self.yt_dlp_version_var = tk.StringVar(value="Checking...")
        self.ffmpeg_status_var = tk.StringVar(value="Checking...")

        self.create_widgets()
        self.dep_progress_win = DependencyProgressWindow(self.root, self.app_controller.cancel_dependency_download)

        self.process_gui_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.set_status("Ready")

    def on_closing(self):
        """Handles the application window closing event."""
        if self.app_controller.is_downloading and not messagebox.askyesno("Confirm Exit", "Downloads are in progress. Are you sure you want to exit?"):
            return

        ui_settings = {
            'download_type': self.download_type_var.get(),
            'video_resolution': self.video_resolution_var.get(),
            'audio_format': self.audio_format_var.get(),
            'embed_thumbnail': self.embed_thumbnail_var.get(),
            'last_output_path': Path(self.output_path_var.get())
        }
        self.app_controller.on_app_closing(ui_settings)
        self.is_destroyed = True
        self.root.destroy()

    def create_widgets(self):
        """Creates and lays out all the main GUI widgets."""
        main_frame = ttk.Frame(self.root, padding="10"); main_frame.pack(fill=tk.BOTH, expand=True)
        input_frame = ttk.LabelFrame(main_frame, text="Inputs", padding="10"); input_frame.pack(fill=tk.X, pady=5); input_frame.columnconfigure(1, weight=1)
        ttk.Label(input_frame, text="Video/Playlist URLs\n(one per line):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.url_text = tk.Text(input_frame, height=5, width=80); self.url_text.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Label(input_frame, text="Output Folder:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.output_path_var = tk.StringVar(value=str(self.config.last_output_path))
        ttk.Entry(input_frame, textvariable=self.output_path_var, state='readonly').grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        self.browse_button = ttk.Button(input_frame, text="Browse...", command=self.browse_output_path); self.browse_button.grid(row=1, column=2, padx=5, pady=5)

        self.options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10"); self.options_frame.pack(fill=tk.X, pady=5)
        self.download_type_var = tk.StringVar(value=self.config.download_type); self.download_type_var.trace_add("write", self.update_options_ui)
        ttk.Radiobutton(self.options_frame, text="Video", variable=self.download_type_var, value="video").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(self.options_frame, text="Audio", variable=self.download_type_var, value="audio").pack(side=tk.LEFT, padx=10)
        self.dynamic_options_frame = ttk.Frame(self.options_frame); self.dynamic_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20)

        self.embed_thumbnail_var = tk.BooleanVar(value=self.config.embed_thumbnail)
        self.thumbnail_check = ttk.Checkbutton(self.options_frame, text="Embed Thumbnail", variable=self.embed_thumbnail_var)
        self.thumbnail_check.pack(side=tk.LEFT, padx=10)

        self.video_options_frame = ttk.Frame(self.dynamic_options_frame)
        ttk.Label(self.video_options_frame, text="Resolution:").pack(side=tk.LEFT, padx=(0, 5)); self.video_resolution_var = tk.StringVar(value=self.config.video_resolution)
        self.video_resolution_combo = ttk.Combobox(self.video_options_frame, textvariable=self.video_resolution_var, values=["Best", "1080", "720", "480"], state="readonly", width=10); self.video_resolution_combo.pack(side=tk.LEFT)

        self.audio_options_frame = ttk.Frame(self.dynamic_options_frame)
        ttk.Label(self.audio_options_frame, text="Format:").pack(side=tk.LEFT, padx=(0, 5)); self.audio_format_var = tk.StringVar(value=self.config.audio_format)
        self.audio_format_combo = ttk.Combobox(self.audio_options_frame, textvariable=self.audio_format_var, values=["best", "mp3", "m4a", "flac", "wav"], state="readonly", width=10); self.audio_format_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.update_options_ui()

        action_frame = ttk.Frame(main_frame); action_frame.pack(fill=tk.X, pady=10); action_frame.columnconfigure(0, weight=1)
        self.download_button = ttk.Button(action_frame, text="Add URLs to Queue & Download", command=self.queue_downloads); self.download_button.grid(row=0, column=0, sticky=tk.EW)
        self.stop_button = ttk.Button(action_frame, text="Stop All", command=self.stop_downloads, state='disabled'); self.stop_button.grid(row=0, column=1, padx=5)
        self.clear_button = ttk.Button(action_frame, text="Clear Completed", command=self.clear_completed_list); self.clear_button.grid(row=0, column=2, padx=5)
        self.settings_button = ttk.Button(action_frame, text="Settings", command=self.open_settings_window); self.settings_button.grid(row=0, column=3, padx=(5, 0))

        progress_frame = ttk.LabelFrame(main_frame, text="Progress & Log", padding="10"); progress_frame.pack(fill=tk.BOTH, expand=True, pady=5); progress_frame.rowconfigure(1, weight=1); progress_frame.columnconfigure(0, weight=1)
        overall_progress_frame = ttk.Frame(progress_frame); overall_progress_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        self.overall_progress_label = ttk.Label(overall_progress_frame, text="Overall Progress: 0 / 0"); self.overall_progress_label.pack(side=tk.LEFT, padx=5)
        self.overall_progress_bar = SegmentedProgressBar(overall_progress_frame, background='white')
        self.overall_progress_bar.pack(fill=tk.X, expand=True)
        self.overall_progress_bar.bind("<Configure>", self.overall_progress_bar._on_resize)

        tree_frame = ttk.Frame(progress_frame); tree_frame.grid(row=1, column=0, sticky='nsew', pady=5)
        self.downloads_tree = ttk.Treeview(tree_frame, columns=('title', 'url', 'status', 'progress'), show='headings')
        self.downloads_tree.heading('title', text='Title'); self.downloads_tree.heading('url', text='Original URL'); self.downloads_tree.heading('status', text='Status'); self.downloads_tree.heading('progress', text='Progress')
        self.downloads_tree.column('title', width=350); self.downloads_tree.column('url', width=200); self.downloads_tree.column('status', width=100, anchor=tk.CENTER); self.downloads_tree.column('progress', width=100, anchor=tk.CENTER)
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.downloads_tree.yview); self.downloads_tree.configure(yscrollcommand=tree_scrollbar.set); tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y); self.downloads_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.downloads_tree.tag_configure('failed', background='misty rose'); self.downloads_tree.tag_configure('completed', background='pale green'); self.downloads_tree.tag_configure('cancelled', background='light grey')

        self.tree_context_menu = JobContextMenu(self.root, self.downloads_tree, retry_callback=self.retry_failed_download, open_folder_callback=self.open_output_folder)
        self.downloads_tree.bind("<Button-3>", self.tree_context_menu.show)
        if sys.platform == "darwin": self.downloads_tree.bind("<Button-2>", self.tree_context_menu.show); self.downloads_tree.bind("<Control-Button-1>", self.tree_context_menu.show)

        self.log_text = scrolledtext.ScrolledText(progress_frame, wrap=tk.WORD, height=10, state='disabled'); self.log_text.grid(row=2, column=0, sticky='ew', pady=5)
        status_bar_frame = ttk.Frame(self.root, relief=tk.SUNKEN); status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=2)
        self.status_label = ttk.Label(status_bar_frame, text="Ready"); self.status_label.pack(side=tk.LEFT, padx=5)

    def set_status(self, message: str):
        """Updates the text in the status bar."""
        self.status_label.config(text=message)

    def update_options_ui(self, *args):
        """Shows or hides UI elements based on the selected download type."""
        self.video_options_frame.pack_forget(); self.audio_options_frame.pack_forget()
        if self.download_type_var.get() == "video": self.video_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        elif self.download_type_var.get() == "audio": self.audio_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def initiate_dependency_prompt(self, dep_type: str):
        """Asks user to download a missing dependency."""
        if self.dep_progress_win.is_visible: return
        msg_map = {'yt-dlp': "yt-dlp not found.", 'ffmpeg': "FFmpeg is required for some features but not found."}
        if messagebox.askyesno(f"{dep_type.upper()} Not Found", f"{msg_map.get(dep_type, 'Dependency not found.')}\n\nDownload the latest version?"):
            self.app_controller.initiate_dependency_download(dep_type)

    def queue_downloads(self):
        """Validates inputs and passes the download request to the controller."""
        urls_raw = self.url_text.get(1.0, tk.END).strip()
        if not urls_raw: messagebox.showwarning("Input Error", "Please enter at least one URL."); return

        valid_urls = [u for url in urls_raw.splitlines() if (u := url.strip()) and urllib.parse.urlparse(u).scheme]
        if not valid_urls: messagebox.showwarning("Input Error", "No valid URLs provided."); return

        output_path = Path(self.output_path_var.get())
        if not output_path.is_dir():
            if not messagebox.askyesno("Create Directory?", f"Output directory does not exist:\n{output_path}\nCreate it?"): return
            try: output_path.mkdir(parents=True, exist_ok=True)
            except OSError as e: messagebox.showerror("Error", f"Failed to create directory: {e}"); return

        options = {'output_path': output_path, 'filename_template': self.config.filename_template, 'download_type': self.download_type_var.get(), 'video_resolution': self.video_resolution_var.get(), 'audio_format': self.audio_format_var.get(), 'embed_thumbnail': self.embed_thumbnail_var.get()}

        self.url_text.delete(1.0, tk.END)
        self.app_controller.start_downloads(valid_urls, options)

    def stop_downloads(self):
        """Requests the controller to stop all downloads."""
        if messagebox.askyesno("Confirm Stop", "Stop all current and queued downloads?"):
            self.app_controller.stop_all_downloads()

    def clear_completed_list(self):
        """Asks controller to clear all finished jobs."""
        self.app_controller.clear_completed_jobs()

    def process_gui_queue(self):
        """Processes messages from the controller."""
        try:
            while True:
                msg = self.gui_queue.get_nowait()
                if isinstance(msg, logging.LogRecord):
                    self.update_log_display(self.log_formatter.format(msg))
                    continue

                msg_type, value = msg
                if msg_type == 'update_progress_view':
                    self.update_overall_progress(value)
                elif msg_type == 'reset_progress_view':
                    self.downloads_tree.delete(*self.downloads_tree.get_children())
                    self.update_overall_progress({'completed': 0, 'total': 0, 'jobs': []})
                    self.set_status("Ready")
                elif msg_type == 'remove_jobs_from_view':
                    for job_id in value:
                        if self.downloads_tree.exists(job_id): self.downloads_tree.delete(job_id)
                elif msg_type == 'update_download_state':
                    self.update_button_states(value['is_downloading'])
                elif msg_type == 'set_status':
                    self.set_status(value)
                elif msg_type == 'url_processing_done':
                    self.toggle_url_input_state(True)
                elif msg_type == 'initiate_dependency_prompt':
                    self.root.after(100, self.initiate_dependency_prompt, value)
                elif msg_type == 'show_dependency_progress_window':
                    self.toggle_ui_state(False)
                    self.dep_progress_win.show(value)
                elif msg_type == 'close_dependency_progress_window':
                    self.dep_progress_win.close(); self.toggle_ui_state(True)
                elif msg_type == 'dependency_progress':
                    self.dep_progress_win.update_progress(value)
                elif msg_type == 'show_message':
                    handler = getattr(messagebox, f"show{value['type']}", messagebox.showinfo)
                    handler(value['title'], value['message'])
                elif msg_type == 'update_dependency_version' and self.settings_win and self.settings_win.winfo_exists():
                    var = self.yt_dlp_version_var if value['type'] == 'yt-dlp' else self.ffmpeg_status_var
                    var.set(value['version'])
                elif msg_type == 'critical_error':
                    messagebox.showerror("Critical Error", value)
                    self.is_destroyed = True; self.root.after(1, self.root.destroy)
                elif msg_type == 'new_version_available':
                    self._show_update_dialog(value['version'], value['url'])
        except queue.Empty:
            if not self.is_destroyed: self.root.after(100, self.process_gui_queue)

    def update_overall_progress(self, data: Dict[str, Any]):
        """Updates the progress bar, label, and job list from controller data."""
        if self.is_destroyed: return
        completed, total = data.get('completed', 0), data.get('total', 0)
        jobs: List[DownloadJob] = data.get('jobs', [])

        # Update labels and progress bar
        self.overall_progress_label.config(text=f"Overall Progress: {completed} / {total}")
        self.overall_progress_bar.update_progress(jobs)
        if total > 0 and completed < total: self.set_status(f"Downloading... ({completed}/{total})")
        elif total > 0 and completed >= total: self.set_status(f"All downloads complete! ({completed}/{total})")

        # Update Treeview (more efficient than full rebuild)
        current_tree_ids = set(self.downloads_tree.get_children())
        job_data_map = {job.job_id: job for job in jobs}
        job_ids = set(job_data_map.keys())

        to_remove = current_tree_ids - job_ids
        to_add = job_ids - current_tree_ids
        to_update = current_tree_ids.intersection(job_ids)

        for job_id in to_remove: self.downloads_tree.delete(job_id)
        for job_id in to_add:
            job = job_data_map[job_id]
            self.downloads_tree.insert('', 'end', iid=job.job_id, values=(job.title, job.original_url, job.status, job.progress))
        for job_id in to_update:
            job = job_data_map[job_id]
            self.downloads_tree.item(job_id, values=(job.title, job.original_url, job.status, job.progress))
            tags = ('cancelled',) if 'cancelled' in job.status.lower() else \
                   ('completed',) if 'completed' in job.status.lower() else \
                   ('failed',) if any(s in job.status.lower() for s in ['failed', 'error']) else ()
            self.downloads_tree.item(job_id, tags=tags)


    def update_button_states(self, is_downloading: bool):
        """Enables or disables buttons based on download state."""
        state = 'disabled' if is_downloading else 'normal'
        self.settings_button.config(state=state)
        self.stop_button.config(state='normal' if is_downloading else 'disabled')
        if is_downloading:
            self.toggle_url_input_state(False)

    def toggle_ui_state(self, enabled: bool):
        """Enables or disables major UI components."""
        state, combo_state = ('normal' if enabled else 'disabled'), ('readonly' if enabled else 'disabled')
        self.toggle_url_input_state(enabled)
        for child in self.options_frame.winfo_children():
            if isinstance(child, (ttk.Radiobutton, ttk.Checkbutton)): child.config(state=state)
        self.video_resolution_combo.config(state=combo_state); self.audio_format_combo.config(state=combo_state)

    def toggle_url_input_state(self, enabled: bool):
        """Enables or disables the URL input and download button."""
        state = 'normal' if enabled else 'disabled'
        self.url_text.config(state=state); self.browse_button.config(state=state)
        self.download_button.config(state=state)

    def open_settings_window(self):
        """Opens the settings window."""
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return
        self.settings_win = SettingsWindow(
            master=self.root,
            app_controller=self.app_controller,
            config=self.config,
            yt_dlp_var=self.yt_dlp_version_var,
            ffmpeg_var=self.ffmpeg_status_var
        )

    def open_output_folder(self):
        """Asks controller to open the currently configured output folder."""
        self.app_controller.open_folder(self.output_path_var.get())

    def retry_failed_download(self):
        """Asks controller to retry all currently selected failed downloads."""
        items_to_retry_ids = [item for item in self.downloads_tree.selection() if 'failed' in self.downloads_tree.item(item, 'tags')]
        if not items_to_retry_ids: return
        self.app_controller.add_jobs_for_retry(items_to_retry_ids)

    def browse_output_path(self):
        """Opens a dialog to select the output folder."""
        path = filedialog.askdirectory(initialdir=self.output_path_var.get(), title="Select Output Folder")
        if path: self.output_path_var.set(path)

    def update_log_display(self, message: str):
        """Appends a message to the log display text widget."""
        if self.is_destroyed: return
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + '\n')
        num_lines = int(self.log_text.index('end-1c').split('.')[0])
        if num_lines > self.MAX_LOG_LINES:
            self.log_text.delete('1.0', f'{num_lines - self.MAX_LOG_LINES + 1}.0')
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def _show_update_dialog(self, new_version: str, release_url: str):
        """Displays a dialog informing the user of a new application version."""
        if self.update_dialog and self.update_dialog.winfo_exists(): return

        self.update_dialog = tk.Toplevel(self.root); self.update_dialog.title("Update Available"); self.update_dialog.geometry("400x200")
        self.update_dialog.resizable(False, False); self.update_dialog.transient(self.root)

        main_frame = ttk.Frame(self.update_dialog, padding="15"); main_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(main_frame, text="A new version is available!", font=("TkDefaultFont", 10, "bold")).pack(pady=(0, 10))
        ttk.Label(main_frame, text=f"Current version: {__version__}").pack()
        ttk.Label(main_frame, text=f"New version: {new_version}").pack(pady=(0, 15))

        skip_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Don't remind me about this version again", variable=skip_var).pack(pady=5)
        button_frame = ttk.Frame(main_frame); button_frame.pack(fill=tk.X, pady=10)

        def go_to_download():
            self.app_controller.open_link(release_url); dismiss_and_save()
        def dismiss_and_save():
            if not self.update_dialog: return
            if skip_var.get():
                self.app_controller.skip_update_version(new_version)
            self.update_dialog.destroy(); self.update_dialog = None

        download_button = ttk.Button(button_frame, text="Go to Download Page", command=go_to_download); download_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        dismiss_button = ttk.Button(button_frame, text="Dismiss", command=dismiss_and_save); dismiss_button.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5, 0))

        self.update_dialog.protocol("WM_DELETE_WINDOW", dismiss_and_save); self.update_dialog.grab_set(); self.root.wait_window(self.update_dialog)