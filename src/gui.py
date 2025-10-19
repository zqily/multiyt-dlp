import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import queue
import os
import sys
import re
import urllib.parse
import threading
import logging
import logging.handlers

from ._version import __version__
from .config import ConfigManager
from .constants import CONFIG_FILE, resource_path
from .dependencies import DependencyManager
from .downloads import DownloadManager


class YTDlpDownloaderApp:
    """The main application class, handling the Tkinter GUI and event loop."""
    MAX_LOG_LINES = 2000

    def __init__(self, root, gui_queue, config_manager, config):
        self.root = root
        self.root.title(f"Multiyt-dlp v{__version__}"); self.root.geometry("850x780")
        self.logger = logging.getLogger(__name__)
        try: self.root.iconbitmap(resource_path('icon.ico'))
        except tk.TclError: self.logger.warning("Could not load 'icon.ico'.")
        
        self.gui_queue = gui_queue
        self.log_formatter = logging.Formatter('%(asctime)s - %(levelname)-8s - %(name)-25s - %(message)s')
        
        # Use pre-loaded config manager and settings
        self.config_manager = config_manager
        self.config = config
        
        self.max_concurrent_downloads = self.config.get('max_concurrent_downloads')
        self.filename_template = tk.StringVar(value=self.config.get('filename_template'))
        self.dependency_progress_win, self.settings_win = None, None
        self.is_downloading, self.is_updating_dependency, self.is_destroyed = False, False, False
        self.pending_download_task = None
        self.yt_dlp_version_var = tk.StringVar(value="Checking...")
        self.ffmpeg_status_var = tk.StringVar(value="Checking...")
        
        self.dep_manager = DependencyManager(self.gui_queue)
        self.download_manager = DownloadManager(self.gui_queue)
        
        self.create_widgets()
        self.logger.info(f"Config path: {CONFIG_FILE}")
        self.logger.info(f"Found yt-dlp: {self.dep_manager.yt_dlp_path or 'Not Found'}")
        self.logger.info(f"Found FFmpeg: {self.dep_manager.ffmpeg_path or 'Not Found'}")
        
        if not self.dep_manager.yt_dlp_path:
            self.root.after(100, lambda: self.initiate_dependency_download('yt-dlp'))
        
        self.process_gui_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.set_status("Ready")

    def on_closing(self):
        if self.is_downloading and not messagebox.askyesno("Confirm Exit", "Downloads are in progress. Are you sure you want to exit?"):
            return
        
        self.logger.info("Application closing.")
        if self.is_downloading:
            self.download_manager.stop_all_downloads()
        else:
            self.download_manager.cleanup_temporary_files(self.output_path_var.get())

        self.config.update({
            'download_type': self.download_type_var.get(), 'video_resolution': self.video_resolution_var.get(),
            'audio_format': self.audio_format_var.get(), 'embed_thumbnail': self.embed_thumbnail_var.get(),
            'filename_template': self.filename_template.get(), 'max_concurrent_downloads': self.max_concurrent_downloads,
            'last_output_path': self.output_path_var.get()
        })
        self.config_manager.save(self.config)
        self.is_destroyed = True
        self.root.destroy()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10"); main_frame.pack(fill=tk.BOTH, expand=True)
        input_frame = ttk.LabelFrame(main_frame, text="Inputs", padding="10"); input_frame.pack(fill=tk.X, pady=5); input_frame.columnconfigure(1, weight=1)
        ttk.Label(input_frame, text="Video/Playlist URLs\n(one per line):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.url_text = tk.Text(input_frame, height=5, width=80); self.url_text.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Label(input_frame, text="Output Folder:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.output_path_var = tk.StringVar(value=self.config.get('last_output_path'))
        ttk.Entry(input_frame, textvariable=self.output_path_var, state='readonly').grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        self.browse_button = ttk.Button(input_frame, text="Browse...", command=self.browse_output_path); self.browse_button.grid(row=1, column=2, padx=5, pady=5)
        
        self.options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10"); self.options_frame.pack(fill=tk.X, pady=5)
        self.download_type_var = tk.StringVar(value=self.config.get('download_type')); self.download_type_var.trace_add("write", self.update_options_ui)
        ttk.Radiobutton(self.options_frame, text="Video", variable=self.download_type_var, value="video").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(self.options_frame, text="Audio", variable=self.download_type_var, value="audio").pack(side=tk.LEFT, padx=10)
        self.dynamic_options_frame = ttk.Frame(self.options_frame); self.dynamic_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20)
        
        self.video_options_frame = ttk.Frame(self.dynamic_options_frame)
        ttk.Label(self.video_options_frame, text="Resolution:").pack(side=tk.LEFT, padx=(0, 5)); self.video_resolution_var = tk.StringVar(value=self.config.get('video_resolution'))
        self.video_resolution_combo = ttk.Combobox(self.video_options_frame, textvariable=self.video_resolution_var, values=["Best", "1080", "720", "480"], state="readonly", width=10); self.video_resolution_combo.pack(side=tk.LEFT)
        
        self.audio_options_frame = ttk.Frame(self.dynamic_options_frame)
        ttk.Label(self.audio_options_frame, text="Format:").pack(side=tk.LEFT, padx=(0, 5)); self.audio_format_var = tk.StringVar(value=self.config.get('audio_format'))
        self.audio_format_combo = ttk.Combobox(self.audio_options_frame, textvariable=self.audio_format_var, values=["best", "mp3", "m4a", "flac", "wav"], state="readonly", width=10); self.audio_format_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.embed_thumbnail_var = tk.BooleanVar(value=self.config.get('embed_thumbnail')); self.thumbnail_check = ttk.Checkbutton(self.audio_options_frame, text="Embed Thumbnail", variable=self.embed_thumbnail_var); self.thumbnail_check.pack(side=tk.LEFT)
        self.update_options_ui()

        action_frame = ttk.Frame(main_frame); action_frame.pack(fill=tk.X, pady=10); action_frame.columnconfigure(0, weight=1)
        self.download_button = ttk.Button(action_frame, text="Add URLs to Queue & Download", command=self.queue_downloads); self.download_button.grid(row=0, column=0, sticky=tk.EW)
        self.stop_button = ttk.Button(action_frame, text="Stop All", command=self.stop_downloads, state='disabled'); self.stop_button.grid(row=0, column=1, padx=5)
        self.clear_button = ttk.Button(action_frame, text="Clear Completed", command=self.clear_completed_list); self.clear_button.grid(row=0, column=2, padx=5)
        self.settings_button = ttk.Button(action_frame, text="Settings", command=self.open_settings_window); self.settings_button.grid(row=0, column=3, padx=(5, 0))

        progress_frame = ttk.LabelFrame(main_frame, text="Progress & Log", padding="10"); progress_frame.pack(fill=tk.BOTH, expand=True, pady=5); progress_frame.rowconfigure(1, weight=1); progress_frame.columnconfigure(0, weight=1)
        overall_progress_frame = ttk.Frame(progress_frame); overall_progress_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        self.overall_progress_label = ttk.Label(overall_progress_frame, text="Overall Progress: 0 / 0"); self.overall_progress_label.pack(side=tk.LEFT, padx=5)
        self.overall_progress_bar = ttk.Progressbar(overall_progress_frame, orient='horizontal', mode='determinate'); self.overall_progress_bar.pack(fill=tk.X, expand=True)

        tree_frame = ttk.Frame(progress_frame); tree_frame.grid(row=1, column=0, sticky='nsew', pady=5)
        self.downloads_tree = ttk.Treeview(tree_frame, columns=('url', 'status', 'progress'), show='headings'); self.downloads_tree.heading('url', text='URL'); self.downloads_tree.heading('status', text='Status'); self.downloads_tree.heading('progress', text='Progress'); self.downloads_tree.column('url', width=450); self.downloads_tree.column('status', width=100, anchor=tk.CENTER); self.downloads_tree.column('progress', width=100, anchor=tk.CENTER)
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.downloads_tree.yview); self.downloads_tree.configure(yscrollcommand=tree_scrollbar.set); tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y); self.downloads_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.downloads_tree.tag_configure('failed', background='misty rose'); self.downloads_tree.tag_configure('completed', background='pale green'); self.downloads_tree.tag_configure('cancelled', background='light grey')
        self.tree_context_menu = tk.Menu(self.root, tearoff=0); self.tree_context_menu.add_command(label="Open Output Folder", command=self.open_output_folder); self.tree_context_menu.add_command(label="Retry Failed Download(s)", command=self.retry_failed_download)
        self.downloads_tree.bind("<Button-3>", self.show_context_menu) # Right-click
        if sys.platform == "darwin": self.downloads_tree.bind("<Button-2>", self.show_context_menu); self.downloads_tree.bind("<Control-Button-1>", self.show_context_menu)
        
        self.log_text = scrolledtext.ScrolledText(progress_frame, wrap=tk.WORD, height=10, state='disabled'); self.log_text.grid(row=2, column=0, sticky='ew', pady=5)

        status_bar_frame = ttk.Frame(self.root, relief=tk.SUNKEN); status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=2)
        self.status_label = ttk.Label(status_bar_frame, text="Ready"); self.status_label.pack(side=tk.LEFT, padx=5)

    def set_status(self, message): self.status_label.config(text=message)
    def update_options_ui(self, *args):
        self.video_options_frame.pack_forget(); self.audio_options_frame.pack_forget()
        if self.download_type_var.get() == "video": self.video_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        elif self.download_type_var.get() == "audio": self.audio_options_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def initiate_dependency_download(self, dep_type):
        if self.is_updating_dependency: return
        msg_map = {'yt-dlp': "yt-dlp not found.", 'ffmpeg': "FFmpeg is required for audio conversion but not found."}
        if messagebox.askyesno(f"{dep_type.upper()} Not Found", f"{msg_map[dep_type]}\n\nDownload the latest version?"):
            self.is_updating_dependency = True; self.toggle_ui_state(False); self.show_dependency_progress_window(f"Downloading {dep_type.upper()}")
            if dep_type == 'yt-dlp': self.dep_manager.install_or_update_yt_dlp()
            else: self.dep_manager.download_ffmpeg()
        elif dep_type == 'yt-dlp':
            messagebox.showerror("Critical Error", "yt-dlp is required. Exiting."); self.is_destroyed = True; self.root.after(1, self.root.destroy)

    def queue_downloads(self):
        if self.is_downloading or not self.dep_manager.yt_dlp_path: return
        
        urls_raw = self.url_text.get(1.0, tk.END).strip()
        if not urls_raw:
            messagebox.showwarning("Input Error", "Please enter at least one URL.")
            return

        valid_urls = [u for url in urls_raw.splitlines() if (u := url.strip()) and urllib.parse.urlparse(u).scheme]
        if not valid_urls:
            messagebox.showwarning("Input Error", "No valid URLs provided.")
            return
        
        output_path = self.output_path_var.get()
        if not os.path.isdir(output_path):
            if not messagebox.askyesno("Create Directory?", f"Output directory does not exist:\n{output_path}\nCreate it?"): return
            try: os.makedirs(output_path, exist_ok=True)
            except OSError as e: messagebox.showerror("Error", f"Failed to create directory: {e}"); return
        try:
            with open(os.path.join(output_path, f".writetest_{os.getpid()}"), 'w') as f: f.write('test')
            os.remove(os.path.join(output_path, f".writetest_{os.getpid()}"))
        except (IOError, OSError) as e: messagebox.showerror("Permission Error", f"Cannot write to directory:\n{e}"); return
        
        options = {'output_path': output_path, 'filename_template': self.filename_template.get(), 'download_type': self.download_type_var.get(), 'video_resolution': self.video_resolution_var.get(), 'audio_format': self.audio_format_var.get(), 'embed_thumbnail': self.embed_thumbnail_var.get()}
        
        if self.download_type_var.get() == 'audio' and not self.dep_manager.ffmpeg_path:
            self.pending_download_task = (valid_urls, options)
            self.url_text.delete(1.0, tk.END)
            self.logger.info("FFmpeg is required. Attempting to download it now...")
            self.logger.info("Your downloads will begin automatically after installation.")
            self.initiate_dependency_download('ffmpeg')
            return
        
        self.update_button_states(is_downloading=True); self.set_status("Processing URLs..."); self.toggle_url_input_state(False)
        self.url_text.delete(1.0, tk.END)
        self.logger.info("--- Queuing new URLs ---")
        self.download_manager.set_config(self.max_concurrent_downloads, self.dep_manager.yt_dlp_path, self.dep_manager.ffmpeg_path)
        self.download_manager.start_downloads(valid_urls, options)

    def stop_downloads(self):
        if not self.is_downloading: return
        if messagebox.askyesno("Confirm Stop", "Stop all current and queued downloads?"):
            self.set_status("Stopping all downloads..."); self.download_manager.stop_all_downloads(); self.update_button_states(is_downloading=False)

    def clear_completed_list(self):
        to_remove = [item for item in self.downloads_tree.get_children() if any(tag in self.downloads_tree.item(item, 'tags') for tag in ['completed', 'failed', 'cancelled'])]
        for item in to_remove: self.downloads_tree.delete(item)
        self.logger.info("Cleared finished items from the list.")

    def process_gui_queue(self):
        try:
            while True:
                msg = self.gui_queue.get_nowait()
                if isinstance(msg, logging.LogRecord):
                    self.update_log_display(self.log_formatter.format(msg))
                else:
                    msg_type, value = msg
                    if msg_type == 'add_job':
                        job_id, url, status, progress = value
                        self.downloads_tree.insert('', 'end', iid=job_id, values=(url, status, progress)); self.update_overall_progress()
                    elif msg_type == 'update_job' and self.downloads_tree.exists(value[0]): self.downloads_tree.set(value[0], value[1], value[2])
                    elif msg_type == 'done' and self.downloads_tree.exists(value[0]):
                        job_id, status = value
                        tags = ('cancelled',) if status == 'Cancelled' else ('completed',) if status == 'Completed' else ('failed',)
                        if status == 'Completed': self.downloads_tree.set(job_id, 'progress', '100.0%')
                        self.downloads_tree.item(job_id, tags=tags); self.downloads_tree.set(job_id, 'status', status); self.update_overall_progress()
                    elif msg_type == 'reset_progress': self.update_overall_progress(reset=True)
                    elif msg_type == 'dependency_progress': self.update_dependency_progress(value)
                    elif msg_type == 'dependency_done': self.handle_dependency_result(value)
                    elif msg_type == 'set_yt_dlp_version': self.yt_dlp_version_var.set(value)
                    elif msg_type == 'set_ffmpeg_status': self.ffmpeg_status_var.set(value)
                    elif msg_type == 'url_processing_done': self.toggle_url_input_state(True)
        except queue.Empty:
            if not self.is_destroyed: self.root.after(100, self.process_gui_queue)

    def handle_dependency_result(self, result):
        self.close_dependency_progress_window(); self.toggle_ui_state(True)
        dep_type = result.get('type')
        if result.get('success'): messagebox.showinfo("Success", f"{dep_type.upper()} downloaded successfully.")
        else: messagebox.showerror(f"Download Failed", f"An error occurred: {result.get('error')}")
        
        if dep_type == 'yt-dlp':
            if not self.dep_manager.find_yt_dlp(): self.is_destroyed = True; self.root.destroy()
            else: self.check_yt_dlp_version()
        elif dep_type == 'ffmpeg':
            self.check_ffmpeg_status()

        if dep_type == 'ffmpeg' and result.get('success') and self.pending_download_task:
            self.logger.info("FFmpeg installed. Resuming queued downloads...")
            urls, options = self.pending_download_task
            self.pending_download_task = None
            self.update_button_states(is_downloading=True)
            self.toggle_url_input_state(False)
            self.download_manager.set_config(self.max_concurrent_downloads, self.dep_manager.yt_dlp_path, self.dep_manager.ffmpeg_path)
            self.download_manager.start_downloads(urls, options)
            
        if self.is_updating_dependency:
            self.is_updating_dependency = False; self.toggle_update_buttons(True)

    def update_overall_progress(self, reset=False):
        if reset:
            self.overall_progress_label.config(text="Overall Progress: 0 / 0")
            self.overall_progress_bar['value'] = 0
            self.set_status("Ready")
            return

        completed, total = self.download_manager.get_stats()
        self.overall_progress_label.config(text=f"Overall Progress: {completed} / {total}")
        if total > 0:
            self.overall_progress_bar['value'] = (completed / total) * 100
            if completed < total: self.set_status(f"Downloading... ({completed}/{total})")
            else: self.set_status(f"All downloads complete! ({completed}/{total})")
        
        if total > 0 and completed >= total and self.is_downloading:
            self.logger.info("--- All queued downloads are complete! ---"); self.update_button_states(is_downloading=False)

    def update_button_states(self, is_downloading):
        self.is_downloading = is_downloading
        state = 'disabled' if is_downloading else 'normal'
        self.download_button.config(state=state); self.settings_button.config(state=state); self.stop_button.config(state='normal' if is_downloading else 'disabled')

    def toggle_ui_state(self, enabled):
        state, combo_state = ('normal' if enabled else 'disabled'), ('readonly' if enabled else 'disabled')
        self.toggle_url_input_state(enabled)
        for child in self.options_frame.winfo_children():
            if isinstance(child, (ttk.Radiobutton, ttk.Checkbutton)): child.config(state=state)
        self.video_resolution_combo.config(state=combo_state); self.audio_format_combo.config(state=combo_state)

    def toggle_url_input_state(self, enabled):
        state = 'normal' if enabled else 'disabled'
        self.url_text.config(state=state); self.browse_button.config(state=state); self.download_button.config(state=state)

    def show_dependency_progress_window(self, title):
            if self.dependency_progress_win and self.dependency_progress_win.winfo_exists(): return
            self.dependency_progress_win = tk.Toplevel(self.root)
            self.dependency_progress_win.title(title)
            self.dependency_progress_win.geometry("400x150")
            self.dependency_progress_win.resizable(False, False)
            self.dependency_progress_win.transient(self.root)

            def cancel_and_close():
                if self.dependency_progress_win and messagebox.askyesno("Confirm Cancel", "Are you sure you want to cancel the download?", parent=self.dependency_progress_win):
                    self.dep_manager.cancel_download()
            
            self.dependency_progress_win.protocol("WM_DELETE_WINDOW", cancel_and_close)
            
            self.dep_progress_label = ttk.Label(self.dependency_progress_win, text="Initializing...")
            self.dep_progress_label.pack(fill=tk.X, padx=10, pady=10)
            self.dep_progress_bar = ttk.Progressbar(self.dependency_progress_win, orient='horizontal', length=380)
            self.dep_progress_bar.pack(pady=10)
            
            cancel_button = ttk.Button(self.dependency_progress_win, text="Cancel", command=cancel_and_close)
            cancel_button.pack(pady=5)

    def update_dependency_progress(self, data):
        if not self.dependency_progress_win or not self.dependency_progress_win.winfo_exists(): self.show_dependency_progress_window(f"Downloading {data.get('type')}")
        if self.dependency_progress_win:
            self.dep_progress_label.config(text=data.get('text', ''))
            if data.get('status') == 'indeterminate': self.dep_progress_bar.config(mode='indeterminate'); self.dep_progress_bar.start(10)
            else: self.dep_progress_bar.stop(); self.dep_progress_bar.config(mode='determinate'); self.dep_progress_bar['value'] = data.get('value', 0)

    def close_dependency_progress_window(self):
        if self.dependency_progress_win:
            self.dep_progress_bar.stop()
            self.dependency_progress_win.destroy()
            self.dependency_progress_win = None

    def open_settings_window(self):
        if self.settings_win and self.settings_win.winfo_exists(): self.settings_win.lift(); return
        self.settings_win = tk.Toplevel(self.root); self.settings_win.title("Settings"); self.settings_win.geometry("600x450"); self.settings_win.resizable(False, False); self.settings_win.transient(self.root)
        try: self.settings_win.iconbitmap(resource_path('icon.ico'))
        except tk.TclError: pass
        settings_frame = ttk.Frame(self.settings_win, padding="10"); settings_frame.pack(fill=tk.BOTH, expand=True)
        concurrent_var, temp_filename_template = tk.IntVar(value=self.max_concurrent_downloads), tk.StringVar(value=self.filename_template.get())
        ttk.Label(settings_frame, text="Max Concurrent Downloads:").grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)
        ttk.Spinbox(settings_frame, from_=1, to=20, textvariable=concurrent_var, width=5).grid(row=0, column=1, padx=5, pady=10, sticky=tk.W)
        ttk.Label(settings_frame, text="Filename Template:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(settings_frame, textvariable=temp_filename_template, width=50).grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        help_text = "Must include %(title)s or %(id)s. Cannot contain / \\ .. or be an absolute path."
        ttk.Label(settings_frame, text=help_text, font=("TkDefaultFont", 8, "italic")).grid(row=2, column=1, sticky=tk.W, padx=5)

        log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        self.log_level_var = tk.StringVar(value=self.config.get('log_level', 'INFO'))
        ttk.Label(settings_frame, text="File Log Level:").grid(row=3, column=0, padx=5, pady=10, sticky=tk.W)
        log_level_combo = ttk.Combobox(settings_frame, textvariable=self.log_level_var, values=log_levels, state="readonly", width=15)
        log_level_combo.grid(row=3, column=1, padx=5, pady=10, sticky=tk.W)
        log_level_help = "Sets verbosity of latest.log. Requires restart to take effect."
        ttk.Label(settings_frame, text=log_level_help, font=("TkDefaultFont", 8, "italic")).grid(row=4, column=1, sticky=tk.W, padx=5)
        
        update_frame = ttk.LabelFrame(settings_frame, text="Dependencies", padding=10); update_frame.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=15); update_frame.columnconfigure(1, weight=1)
        ttk.Label(update_frame, text="yt-dlp:").grid(row=0, column=0, sticky=tk.W, padx=5); ttk.Label(update_frame, textvariable=self.yt_dlp_version_var).grid(row=0, column=1, sticky=tk.W, padx=5); self.check_yt_dlp_version()
        ttk.Label(update_frame, text="FFmpeg:").grid(row=1, column=0, sticky=tk.W, padx=5); ttk.Label(update_frame, textvariable=self.ffmpeg_status_var, wraplength=400).grid(row=1, column=1, sticky=tk.W, padx=5); self.check_ffmpeg_status()
        update_buttons_frame = ttk.Frame(update_frame); update_buttons_frame.grid(row=2, column=0, columnspan=2, pady=(10,0))
        self.yt_dlp_update_button = ttk.Button(update_buttons_frame, text="Update yt-dlp", command=self.start_yt_dlp_update); self.yt_dlp_update_button.pack(side=tk.LEFT, padx=5)
        self.ffmpeg_update_button = ttk.Button(update_buttons_frame, text="Download/Update FFmpeg", command=self.start_ffmpeg_update); self.ffmpeg_update_button.pack(side=tk.LEFT, padx=5)
        
        def save_and_close():
            if not self.settings_win: return

            if self.is_updating_dependency: 
                messagebox.showwarning("Busy", "Cannot close settings while updating.", parent=self.settings_win)
                return
            
            new_concurrent_val = concurrent_var.get()
            new_template = temp_filename_template.get().strip()
            
            if not (1 <= new_concurrent_val <= 20): 
                messagebox.showwarning("Invalid Value", "Concurrent downloads must be between 1 and 20.", parent=self.settings_win)
                return
            if not new_template or not re.search(r'%\((title|id)', new_template): 
                messagebox.showwarning("Invalid Template", "Template must include %(title)s or %(id)s.", parent=self.settings_win)
                return
            if any(c in new_template for c in '/\\') or '..' in new_template or os.path.isabs(new_template): 
                messagebox.showerror("Invalid Template", "Template cannot contain path separators ('/', '\\'), '..', or be absolute.", parent=self.settings_win)
                return
            
            self.max_concurrent_downloads = new_concurrent_val
            self.filename_template.set(new_template)
            self.config['max_concurrent_downloads'] = self.max_concurrent_downloads
            self.config['filename_template'] = self.filename_template.get()
            self.config['log_level'] = self.log_level_var.get()
            self.config_manager.save(self.config)
            self.settings_win.destroy()

        def cancel_and_close():
            if self.settings_win:
                self.settings_win.destroy()
        
        buttons_frame = ttk.Frame(settings_frame)
        buttons_frame.grid(row=6, column=0, columnspan=2, pady=15, sticky=tk.E)
        ttk.Button(buttons_frame, text="Save", command=save_and_close).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Cancel", command=cancel_and_close).pack(side=tk.LEFT)
        self.settings_win.protocol("WM_DELETE_WINDOW", cancel_and_close)

    def check_yt_dlp_version(self):
        self.yt_dlp_version_var.set("Checking...")
        threading.Thread(target=lambda: self.gui_queue.put(('set_yt_dlp_version', self.dep_manager.get_version(self.dep_manager.yt_dlp_path))), daemon=True, name="yt-dlp-Version-Check").start()
    
    def check_ffmpeg_status(self):
        self.ffmpeg_status_var.set("Checking...")
        threading.Thread(target=lambda: self.gui_queue.put(('set_ffmpeg_status', self.dep_manager.get_version(self.dep_manager.ffmpeg_path))), daemon=True, name="FFmpeg-Version-Check").start()

    def toggle_update_buttons(self, enabled):
        state = 'normal' if enabled else 'disabled'
        for btn in [getattr(self, 'yt_dlp_update_button', None), getattr(self, 'ffmpeg_update_button', None)]:
            if btn and btn.winfo_exists(): btn.config(state=state)

    def start_yt_dlp_update(self): self._start_dep_update("yt-dlp", "Download latest yt-dlp?")
    def start_ffmpeg_update(self): self._start_dep_update("ffmpeg", "Download latest FFmpeg? (Large file)")
    def _start_dep_update(self, dep_type, message):
        if self.is_updating_dependency: return
        parent_win = self.settings_win if self.settings_win and self.settings_win.winfo_exists() else self.root
        if messagebox.askyesno(f"Confirm Update", message, parent=parent_win):
            self.is_updating_dependency = True; self.toggle_update_buttons(False); self.show_dependency_progress_window(f"Updating {dep_type}"); getattr(self.dep_manager, f'{"install_or_update" if dep_type == "yt-dlp" else "download"}_{dep_type.replace("-", "_")}')()

    def show_context_menu(self, event):
        selection = self.downloads_tree.selection()
        if not selection:
            item_id = self.downloads_tree.identify_row(event.y)
            if not item_id: return
            self.downloads_tree.selection_set(item_id)
            selection = (item_id,)
        
        is_failed = any('failed' in self.downloads_tree.item(s_item_id, 'tags') for s_item_id in selection)
        self.tree_context_menu.entryconfig("Retry Failed Download(s)", state='normal' if is_failed else 'disabled')
        self.tree_context_menu.post(event.x_root, event.y_root)

    def open_output_folder(self):
        import subprocess
        path = self.output_path_var.get()
        if not os.path.isdir(path): messagebox.showerror("Error", f"Folder does not exist:\n{path}"); return
        try:
            if sys.platform == 'win32': os.startfile(path)
            elif sys.platform == 'darwin': subprocess.run(['open', path], check=True)
            else: subprocess.run(['xdg-open', path], check=True)
        except Exception as e: messagebox.showerror("Error", f"Failed to open folder:\n{e}")

    def retry_failed_download(self):
        to_retry = [(self.downloads_tree.item(item, 'values')[0], item) for item in self.downloads_tree.selection() if 'failed' in self.downloads_tree.item(item, 'tags')]
        if not to_retry: return
        for _, item_id in to_retry: self.downloads_tree.delete(item_id)
        options = {'output_path': self.output_path_var.get(), 'filename_template': self.filename_template.get(), 'download_type': self.download_type_var.get(), 'video_resolution': self.video_resolution_var.get(), 'audio_format': self.audio_format_var.get(), 'embed_thumbnail': self.embed_thumbnail_var.get()}
        self.update_button_states(is_downloading=True); self.download_manager.add_jobs([url for url, _ in to_retry], options)

    def browse_output_path(self):
        path = filedialog.askdirectory(initialdir=self.output_path_var.get(), title="Select Output Folder")
        if path: self.output_path_var.set(path)

    def update_log_display(self, message):
        if self.is_destroyed: return
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + '\n')
        num_lines = int(self.log_text.index('end-1c').split('.')[0])
        if num_lines > self.MAX_LOG_LINES:
            self.log_text.delete('1.0', f'{num_lines - self.MAX_LOG_LINES + 1}.0')
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')