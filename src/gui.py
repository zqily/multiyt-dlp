"""The main application class, handling the Tkinter GUI and event loop."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import queue
import sys
import urllib.parse
import logging
import asyncio
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

    def __init__(self, root: tk.Tk, gui_queue: queue.Queue, app_controller: AppController, config: Settings, loop: asyncio.AbstractEventLoop):
        """
        Initializes the main application GUI.

        Args:
            root: The root Tkinter window.
            gui_queue: The queue for cross-thread GUI communication (for logging).
            app_controller: The central application controller.
            config: The loaded application settings.
            loop: The asyncio event loop.
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
        self.loop = loop
        self.app_controller.set_gui(self)

        self.settings_win: Optional[SettingsWindow] = None
        self.update_dialog: Optional[tk.Toplevel] = None
        self.is_destroyed = False

        self.yt_dlp_version_var = tk.StringVar(value="Checking...")
        self.ffmpeg_status_var = tk.StringVar(value="Checking...")

        self.create_widgets()
        self.dep_progress_win = DependencyProgressWindow(self.root, self.app_controller.cancel_dependency_download, self.loop)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        # Run startup checks once the loop is running
        self.loop.create_task(self.app_controller.run_startup_checks())
        # Set initial status and start the async loop driver
        self.loop.create_task(self.set_status("Ready"))
        self.root.after(50, self._run_async_loop)

    def on_closing(self):
        """Synchronous wrapper for the async closing logic."""
        self.loop.create_task(self.handle_closing_async())

    def _run_async_loop(self):
        """
        Drives the asyncio event loop and reschedules itself.
        This function is called periodically by the Tkinter main loop.
        """
        if self.is_destroyed:
            return
        self.loop.call_soon(self.loop.stop)
        self.loop.run_forever()
        self.process_log_queue()
        self.root.after(50, self._run_async_loop)

    async def handle_closing_async(self):
        """Handles the application window closing event."""
        should_close = True
        if self.app_controller.is_downloading:
            should_close = await asyncio.to_thread(
                messagebox.askyesno,
                "Confirm Exit",
                "Downloads are in progress. Are you sure you want to exit?"
            )
        if not should_close:
            return

        ui_settings = {
            'download_type': self.download_type_var.get(),
            'video_resolution': self.video_resolution_var.get(),
            'audio_format': self.audio_format_var.get(),
            'embed_thumbnail': self.embed_thumbnail_var.get(),
            'embed_metadata': self.embed_metadata_var.get(),
            'last_output_path': Path(self.output_path_var.get()) if self.output_path_var.get() else self.config.last_output_path
        }
        await self.app_controller.on_app_closing(ui_settings)
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

        self.embed_metadata_var = tk.BooleanVar(value=self.config.embed_metadata)
        self.metadata_check = ttk.Checkbutton(self.options_frame, text="Embed Metadata", variable=self.embed_metadata_var)
        self.metadata_check.pack(side=tk.LEFT, padx=10)

        self.video_options_frame = ttk.Frame(self.dynamic_options_frame)
        ttk.Label(self.video_options_frame, text="Resolution:").pack(side=tk.LEFT, padx=(0, 5)); self.video_resolution_var = tk.StringVar(value=self.config.video_resolution)
        self.video_resolution_combo = ttk.Combobox(self.video_options_frame, textvariable=self.video_resolution_var, values=["Best", "1080", "720", "480"], state="readonly", width=10); self.video_resolution_combo.pack(side=tk.LEFT)

        self.audio_options_frame = ttk.Frame(self.dynamic_options_frame)
        ttk.Label(self.audio_options_frame, text="Format:").pack(side=tk.LEFT, padx=(0, 5)); self.audio_format_var = tk.StringVar(value=self.config.audio_format)
        self.audio_format_combo = ttk.Combobox(self.audio_options_frame, textvariable=self.audio_format_var, values=["best", "mp3", "m4a", "flac", "wav"], state="readonly", width=10); self.audio_format_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.update_options_ui()

        action_frame = ttk.Frame(main_frame); action_frame.pack(fill=tk.X, pady=10); action_frame.columnconfigure(0, weight=1)
        self.download_button = ttk.Button(action_frame, text="Add URLs to Queue & Download", command=lambda: self.loop.create_task(self.queue_downloads())); self.download_button.grid(row=0, column=0, sticky=tk.EW)
        self.stop_button = ttk.Button(action_frame, text="Stop All", command=lambda: self.loop.create_task(self.stop_downloads()), state='disabled'); self.stop_button.grid(row=0, column=1, padx=5)
        self.clear_button = ttk.Button(action_frame, text="Clear Completed", command=lambda: self.loop.create_task(self.clear_completed_list())); self.clear_button.grid(row=0, column=2, padx=5)
        self.settings_button = ttk.Button(action_frame, text="Settings", command=lambda: self.loop.create_task(self.open_settings_window())); self.settings_button.grid(row=0, column=3, padx=(5, 0))

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

        def retry_cb():
            """Schedules the retry action in the asyncio loop."""
            self.loop.create_task(self.retry_failed_download())

        def open_folder_cb():
            """Schedules the open folder action in the asyncio loop."""
            self.loop.create_task(self.open_output_folder())

        self.tree_context_menu = JobContextMenu(self.root, self.downloads_tree, retry_callback=retry_cb, open_folder_callback=open_folder_cb)
        self.downloads_tree.bind("<Button-3>", self.tree_context_menu.show)
        if sys.platform == "darwin": self.downloads_tree.bind("<Button-2>", self.tree_context_menu.show); self.downloads_tree.bind("<Control-Button-1>", self.tree_context_menu.show)

        self.log_text = scrolledtext.ScrolledText(progress_frame, wrap=tk.WORD, height=10, state='disabled'); self.log_text.grid(row=2, column=0, sticky='ew', pady=5)
        status_bar_frame = ttk.Frame(self.root, relief=tk.SUNKEN); status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=2)
        self.status_label = ttk.Label(status_bar_frame, text="Ready"); self.status_label.pack(side=tk.LEFT, padx=5)

    async def set_status(self, message: str):
        self.status_label.config(text=message)

    def update_options_ui(self, *args):
        self.video_options_frame.pack_forget(); self.audio_options_frame.pack_forget()
        if self.download_type_var.get() == "video": self.video_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        elif self.download_type_var.get() == "audio": self.audio_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

    async def initiate_dependency_prompt(self, dep_type: str):
        if self.dep_progress_win.is_visible: return
        msg_map = {'yt-dlp': "yt-dlp not found.", 'ffmpeg': "FFmpeg is required for some features but not found."}
        should_download = await asyncio.to_thread(
            messagebox.askyesno,
            f"{dep_type.upper()} Not Found",
            f"{msg_map.get(dep_type, 'Dependency not found.')}\n\nDownload the latest version?"
        )
        if should_download:
            await self.app_controller.initiate_dependency_download(dep_type)

    async def queue_downloads(self):
        urls_raw = self.url_text.get(1.0, tk.END).strip()
        if not urls_raw:
            await asyncio.to_thread(messagebox.showwarning, "Input Error", "Please enter at least one URL.")
            return
        valid_urls = [u for url in urls_raw.splitlines() if (u := url.strip()) and urllib.parse.urlparse(u).scheme]
        if not valid_urls:
            await asyncio.to_thread(messagebox.showwarning, "Input Error", "No valid URLs provided.")
            return

        output_path = Path(self.output_path_var.get())
        if not await asyncio.to_thread(output_path.is_dir):
            create_dir = await asyncio.to_thread(
                messagebox.askyesno,
                "Create Directory?",
                f"Output directory does not exist:\n{output_path}\nCreate it?"
            )
            if not create_dir:
                return
            try:
                await asyncio.to_thread(output_path.mkdir, parents=True, exist_ok=True)
            except OSError as e:
                await asyncio.to_thread(messagebox.showerror, "Error", f"Failed to create directory: {e}")
                return

        options = {'output_path': output_path, 'filename_template': self.config.filename_template, 'download_type': self.download_type_var.get(), 'video_resolution': self.video_resolution_var.get(), 'audio_format': self.audio_format_var.get(), 'embed_thumbnail': self.embed_thumbnail_var.get(), 'embed_metadata': self.embed_metadata_var.get()}

        self.url_text.delete(1.0, tk.END)
        await self.app_controller.start_downloads(valid_urls, options)

    async def stop_downloads(self):
        should_stop = await asyncio.to_thread(
            messagebox.askyesno,
            "Confirm Stop",
            "Stop all current and queued downloads?"
        )
        if should_stop:
            await self.app_controller.stop_all_downloads()

    async def clear_completed_list(self):
        await self.app_controller.clear_completed_jobs()

    def process_log_queue(self):
        """Processes log messages from the queue."""
        try:
            while True:
                record = self.gui_queue.get_nowait()
                self.update_log_display(self.log_formatter.format(record))
        except queue.Empty:
            pass

    async def update_progress_view(self, data: Dict[str, Any]):
        if self.is_destroyed: return
        completed, total = data.get('completed', 0), data.get('total', 0)
        jobs: List[DownloadJob] = data.get('jobs', [])

        self.overall_progress_label.config(text=f"Overall Progress: {completed} / {total}")
        self.overall_progress_bar.update_progress(jobs)
        if total > 0 and completed < total: await self.set_status(f"Downloading... ({completed}/{total})")
        elif total > 0 and completed >= total: await self.set_status(f"All downloads complete! ({completed}/{total})")

        current_tree_ids, job_data_map = set(self.downloads_tree.get_children()), {job.job_id: job for job in jobs}
        job_ids = set(job_data_map.keys())
        to_remove, to_add, to_update = current_tree_ids - job_ids, job_ids - current_tree_ids, current_tree_ids.intersection(job_ids)

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

    async def reset_progress_view(self):
        self.downloads_tree.delete(*self.downloads_tree.get_children())
        self.overall_progress_bar.clear()
        await self.update_progress_view({'completed': 0, 'total': 0, 'jobs': []})
        await self.set_status("Ready")

    async def remove_jobs_from_view(self, job_ids: List[str]):
        for job_id in job_ids:
            if self.downloads_tree.exists(job_id): self.downloads_tree.delete(job_id)

    async def update_button_states(self, is_downloading: bool):
        state = 'disabled' if is_downloading else 'normal'
        self.settings_button.config(state=state)
        self.stop_button.config(state='normal' if is_downloading else 'disabled')
        if is_downloading: await self.toggle_url_input_state(False)

    async def toggle_url_input_state(self, enabled: bool):
        state = 'normal' if enabled else 'disabled'
        self.url_text.config(state=state); self.browse_button.config(state=state)
        self.download_button.config(state=state)

    async def show_dependency_progress_window(self, title: str):
        self.dep_progress_win.show(title)
    
    async def update_dependency_progress(self, data: Dict[str, Any]):
        self.dep_progress_win.update_progress(data)

    async def close_dependency_progress_window(self):
        self.dep_progress_win.close()

    async def show_message(self, data: Dict[str, str]):
        handler = getattr(messagebox, f"show{data['type']}", messagebox.showinfo)
        await asyncio.to_thread(handler, data['title'], data['message'])

    async def update_dependency_version(self, data: Dict[str, str]):
        var = self.yt_dlp_version_var if data['type'] == 'yt-dlp' else self.ffmpeg_status_var
        var.set(data['version'])

    async def show_critical_error(self, message: str):
        await asyncio.to_thread(messagebox.showerror, "Critical Error", message)
        self.is_destroyed = True
        self.root.destroy()

    async def show_update_dialog(self, new_version: str, release_url: str):
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

        def dismiss_and_save():
            if not self.update_dialog: return
            if skip_var.get(): self.app_controller.skip_update_version(new_version)
            self.update_dialog.destroy(); self.update_dialog = None
        
        async def go_to_download_async():
            await self.app_controller.open_link(release_url)
            dismiss_and_save()

        ttk.Button(button_frame, text="Go to Download Page", command=lambda: self.loop.create_task(go_to_download_async())).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        ttk.Button(button_frame, text="Dismiss", command=dismiss_and_save).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5, 0))
        self.update_dialog.protocol("WM_DELETE_WINDOW", dismiss_and_save); self.update_dialog.grab_set()

    async def open_settings_window(self):
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift(); return
        self.settings_win = SettingsWindow(master=self.root, app_controller=self.app_controller, config=self.config, yt_dlp_var=self.yt_dlp_version_var, ffmpeg_var=self.ffmpeg_status_var, loop=self.loop)

    async def open_output_folder(self):
        await self.app_controller.open_folder(self.output_path_var.get())

    async def retry_failed_download(self):
        items_to_retry_ids = [item for item in self.downloads_tree.selection() if 'failed' in self.downloads_tree.item(item, 'tags')]
        if not items_to_retry_ids: return
        await self.app_controller.add_jobs_for_retry(items_to_retry_ids)

    def browse_output_path(self):
        """Runs the blocking file dialog in a separate thread and schedules the result handler."""

        def _run_dialog_in_thread():
            """Blocking function to be executed in the thread pool."""
            path = filedialog.askdirectory(
                initialdir=self.output_path_var.get(),
                title="Select Output Folder"
            )
            if path:
                # Safely schedule the GUI update on the main event loop's thread
                self.loop.call_soon_threadsafe(self.output_path_var.set, path)

        # Run the blocking dialog in the default thread pool executor
        self.loop.run_in_executor(None, _run_dialog_in_thread)

    def update_log_display(self, message: str):
        if self.is_destroyed: return
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + '\n')
        num_lines = int(self.log_text.index('end-1c').split('.')[0])
        if num_lines > self.MAX_LOG_LINES: self.log_text.delete('1.0', f'{num_lines - self.MAX_LOG_LINES + 1}.0')
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')