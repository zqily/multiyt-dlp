import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sys
import os
import shutil
import re
import threading
import queue
import subprocess
import urllib.request
import zipfile
import tarfile
import json

# --- Constants ---
# URLs for the latest yt-dlp releases from GitHub
YT_DLP_URLS = {
    'win32': 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe',
    'linux': 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp',
    'darwin': 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos'
}

# URLs for the latest FFmpeg releases from BtbN
FFMPEG_URLS = {
    'win32': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
    'linux': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz',
    'darwin': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-macos64-gpl.zip'
}

# Configuration file name
CONFIG_FILE = 'config.json'

# --- Configuration Management ---

def load_config():
    """Loads settings from config.json, returning defaults if it doesn't exist."""
    defaults = {
        'preferred_format': 'video',
        'max_concurrent_downloads': 4,
        'last_output_path': os.getcwd()
    }
    if not os.path.exists(CONFIG_FILE):
        return defaults
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Ensure all keys are present, falling back to defaults if not
            for key, value in defaults.items():
                config.setdefault(key, value)
            return config
    except (json.JSONDecodeError, IOError):
        return defaults

def save_config(config_data):
    """Saves the provided dictionary to config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
    except IOError as e:
        print(f"Error saving config file: {e}")


# --- Dependency Management ---

def find_yt_dlp():
    """Finds yt-dlp in PATH or in the script's directory."""
    path = shutil.which('yt-dlp')
    if path:
        return path

    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(script_dir, 'yt-dlp.exe' if sys.platform == 'win32' else 'yt-dlp')
    if os.path.exists(local_path):
        return local_path
        
    return None

def _download_yt_dlp_thread(gui_queue):
    """Worker thread for downloading yt-dlp."""
    platform = sys.platform
    if platform not in YT_DLP_URLS:
        gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': f"Unsupported OS: {platform}"}))
        return

    try:
        gui_queue.put(('dependency_progress', {'type': 'yt-dlp', 'status': 'indeterminate', 'text': 'Downloading yt-dlp...'}))
        
        url = YT_DLP_URLS[platform]
        filename = os.path.basename(url)
        
        if platform == 'darwin' and filename == 'yt-dlp_macos':
            save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'yt-dlp')
        else:
            save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

        with urllib.request.urlopen(url) as response:
            with open(save_path, 'wb') as f:
                f.write(response.read())

        if platform in ['linux', 'darwin']:
            os.chmod(save_path, 0o755)

        gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': True, 'path': save_path}))

    except Exception as e:
        gui_queue.put(('dependency_done', {'type': 'yt-dlp', 'success': False, 'error': str(e)}))

def find_ffmpeg():
    """Finds ffmpeg in PATH or in the script's directory."""
    path = shutil.which('ffmpeg')
    if path:
        return path

    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(script_dir, 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg')
    if os.path.exists(local_path):
        return local_path
        
    return None

def _download_ffmpeg_thread(gui_queue):
    """Worker thread for downloading and extracting FFmpeg."""
    platform = sys.platform
    if platform not in FFMPEG_URLS:
        gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': f"Unsupported OS for FFmpeg: {platform}"}))
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    url = FFMPEG_URLS[platform]
    archive_filename = os.path.basename(url)
    archive_path = os.path.join(script_dir, archive_filename)
    extract_dir = os.path.join(script_dir, "ffmpeg_temp")
    final_ffmpeg_name = 'ffmpeg.exe' if platform == 'win32' else 'ffmpeg'
    final_ffmpeg_path = os.path.join(script_dir, final_ffmpeg_name)

    try:
        # 1. Download with progress
        gui_queue.put(('dependency_progress', {'type': 'ffmpeg', 'status': 'determinate', 'text': 'Preparing download...', 'value': 0}))
        with urllib.request.urlopen(url) as response:
            total_size = int(response.getheader('Content-Length', 0))
            chunk_size = 8192
            bytes_downloaded = 0
            with open(archive_path, 'wb') as f_out:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    bytes_downloaded += len(chunk)
                    if total_size > 0:
                        progress_percent = (bytes_downloaded / total_size) * 100
                        gui_queue.put(('dependency_progress', {
                            'type': 'ffmpeg', 
                            'status': 'determinate', 
                            'text': f'Downloading... {bytes_downloaded/1024/1024:.1f}/{total_size/1024/1024:.1f} MB', 
                            'value': progress_percent
                        }))

        # 2. Extract
        gui_queue.put(('dependency_progress', {'type': 'ffmpeg', 'status': 'indeterminate', 'text': 'Extracting FFmpeg...'}))
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir)

        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        elif archive_path.endswith('.tar.xz'):
            with tarfile.open(archive_path, 'r:xz') as tar_ref:
                tar_ref.extractall(path=extract_dir)
        
        # 3. Find and Move
        gui_queue.put(('dependency_progress', {'type': 'ffmpeg', 'status': 'indeterminate', 'text': 'Locating executable...'}))
        ffmpeg_executable_path = None
        for root, _, files in os.walk(extract_dir):
            if final_ffmpeg_name in files:
                ffmpeg_executable_path = os.path.join(root, final_ffmpeg_name)
                break
        
        if not ffmpeg_executable_path:
            raise FileNotFoundError(f"Could not find '{final_ffmpeg_name}' in the extracted archive.")

        shutil.move(ffmpeg_executable_path, final_ffmpeg_path)

        if platform in ['linux', 'darwin']:
            os.chmod(final_ffmpeg_path, 0o755)

        gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': True, 'path': final_ffmpeg_path}))

    except Exception as e:
        gui_queue.put(('dependency_done', {'type': 'ffmpeg', 'success': False, 'error': str(e)}))
    finally:
        # 4. Cleanup
        if os.path.exists(archive_path):
            os.remove(archive_path)
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)

# --- Main Application Class ---

class YTDlpDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Robust yt-dlp Downloader")
        self.root.geometry("800x700")

        # Load configuration
        self.config = load_config()
        self.max_concurrent_downloads = self.config.get('max_concurrent_downloads', 4)
        
        # Concurrency and state management
        self.job_queue = queue.Queue()
        self.gui_queue = queue.Queue()
        self.workers = []
        self.job_counter = 0
        self.completed_jobs = 0
        self.total_jobs = 0
        self.stats_lock = threading.Lock()
        self.dependency_progress_win = None
        self.ffmpeg_path = None
        self.yt_dlp_path = None

        self.create_widgets()

        self.yt_dlp_path = find_yt_dlp()
        if not self.yt_dlp_path:
            self.initiate_dependency_download('yt-dlp')
        
        self.ffmpeg_path = find_ffmpeg()

        self.process_gui_queue()
        
        # Save settings on exit
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """Handle saving the configuration and closing the application gracefully."""
        # Check if there are any active or queued jobs
        if self.total_jobs > self.completed_jobs:
            # If so, ask for user confirmation
            if not messagebox.askyesno(
                "Confirm Exit",
                "Downloads are in progress. Are you sure you want to exit?\n\n"
                "Active downloads will be stopped and any remaining queued items will be lost."
            ):
                return  # User clicked "No", so we abort the closing process

        # If no jobs are running, or if the user confirmed the exit, proceed to shut down
        self.config['preferred_format'] = self.format_var.get()
        self.config['max_concurrent_downloads'] = self.max_concurrent_downloads
        self.config['last_output_path'] = self.output_path_var.get()
        save_config(self.config)
        self.root.destroy()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.LabelFrame(main_frame, text="Inputs", padding="10")
        input_frame.pack(fill=tk.X, pady=5)
        input_frame.columnconfigure(1, weight=1)

        ttk.Label(input_frame, text="Video/Playlist URLs\n(one per line):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.url_text = tk.Text(input_frame, height=5, width=80)
        self.url_text.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)

        ttk.Label(input_frame, text="Output Folder:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.output_path_var = tk.StringVar(value=self.config.get('last_output_path', os.getcwd()))
        output_entry = ttk.Entry(input_frame, textvariable=self.output_path_var, state='readonly')
        output_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        self.browse_button = ttk.Button(input_frame, text="Browse...", command=self.browse_output_path)
        self.browse_button.grid(row=1, column=2, padx=5, pady=5)

        self.options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        self.options_frame.pack(fill=tk.X, pady=5)
        
        self.format_var = tk.StringVar(value=self.config.get('preferred_format', 'video'))
        ttk.Radiobutton(self.options_frame, text="Video (Best Quality)", variable=self.format_var, value="video").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(self.options_frame, text="Audio Only (Best Quality)", variable=self.format_var, value="audio_best").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(self.options_frame, text="Audio Only (MP3, 192k)", variable=self.format_var, value="audio_mp3").pack(side=tk.LEFT, padx=10)
        
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=10)
        action_frame.columnconfigure(0, weight=1)

        self.download_button = ttk.Button(action_frame, text="Add URLs to Queue & Download", command=self.queue_downloads)
        self.download_button.grid(row=0, column=0, sticky=tk.EW)
        
        settings_button = ttk.Button(action_frame, text="Settings", command=self.open_settings_window)
        settings_button.grid(row=0, column=1, padx=(10, 0))

        progress_frame = ttk.LabelFrame(main_frame, text="Progress & Log", padding="10")
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        overall_progress_frame = ttk.Frame(progress_frame)
        overall_progress_frame.pack(fill=tk.X, pady=(0, 10))
        self.overall_progress_label = ttk.Label(overall_progress_frame, text="Overall Progress: 0 / 0")
        self.overall_progress_label.pack(side=tk.LEFT, padx=5)
        self.overall_progress_bar = ttk.Progressbar(overall_progress_frame, orient='horizontal', mode='determinate')
        self.overall_progress_bar.pack(fill=tk.X, expand=True)

        tree_frame = ttk.Frame(progress_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.downloads_tree = ttk.Treeview(tree_frame, columns=('url', 'status', 'progress'), show='headings')
        self.downloads_tree.heading('url', text='URL')
        self.downloads_tree.heading('status', text='Status')
        self.downloads_tree.heading('progress', text='Progress')
        self.downloads_tree.column('url', width=400)
        self.downloads_tree.column('status', width=100, anchor=tk.CENTER)
        self.downloads_tree.column('progress', width=100, anchor=tk.CENTER)
        
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.downloads_tree.yview)
        self.downloads_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.downloads_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.downloads_tree.tag_configure('failed', background='misty rose')
        self.downloads_tree.tag_configure('completed', background='pale green')

        self.log_text = scrolledtext.ScrolledText(progress_frame, wrap=tk.WORD, height=10, state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        ttk.Label(main_frame, text="Note: FFmpeg must be installed and in your PATH for best results (especially for audio conversion).", font=("TkDefaultFont", 8)).pack(pady=5)

    def initiate_dependency_download(self, dep_type):
        if dep_type == 'yt-dlp':
            permission = messagebox.askyesno(
                "yt-dlp Not Found",
                "yt-dlp executable not found in your system PATH or script directory.\n\n"
                "Do you want to download the latest version automatically?"
            )
            if not permission:
                messagebox.showerror("Critical Error", "yt-dlp is required to run this application. Exiting.")
                self.root.destroy()
                return
            
            self.toggle_ui_state(False)
            self.show_dependency_progress_window("Downloading yt-dlp")
            threading.Thread(target=_download_yt_dlp_thread, args=(self.gui_queue,), daemon=True).start()
        
        elif dep_type == 'ffmpeg':
            permission = messagebox.askyesno(
                "FFmpeg Not Found",
                "FFmpeg is required for the selected download format but was not found.\n\n"
                "Do you want to download it automatically? (This may be a large download)"
            )
            if not permission:
                return
            
            self.toggle_ui_state(False)
            self.show_dependency_progress_window("Downloading FFmpeg")
            threading.Thread(target=_download_ffmpeg_thread, args=(self.gui_queue,), daemon=True).start()

    def toggle_ui_state(self, enabled):
        state = 'normal' if enabled else 'disabled'
        self.url_text.config(state=state)
        self.browse_button.config(state=state)
        self.download_button.config(state=state)
        for child in self.options_frame.winfo_children():
            if isinstance(child, ttk.Radiobutton):
                child.config(state=state)

    def show_dependency_progress_window(self, title):
        if self.dependency_progress_win and self.dependency_progress_win.winfo_exists():
            return
        
        self.dependency_progress_win = tk.Toplevel(self.root)
        self.dependency_progress_win.title(title)
        self.dependency_progress_win.geometry("400x120")
        self.dependency_progress_win.resizable(False, False)
        self.dependency_progress_win.transient(self.root)
        self.dependency_progress_win.protocol("WM_DELETE_WINDOW", lambda: None) # Prevent closing

        self.dep_progress_label = tk.Label(self.dependency_progress_win, text="Initializing...", pady=10)
        self.dep_progress_label.pack(fill=tk.X, padx=10)
        self.dep_progress_bar = ttk.Progressbar(self.dependency_progress_win, orient='horizontal', length=380)
        self.dep_progress_bar.pack(pady=10)
    
    def update_dependency_progress(self, data):
        if not self.dependency_progress_win or not self.dependency_progress_win.winfo_exists():
            self.show_dependency_progress_window(f"Downloading {data.get('type')}")

        self.dep_progress_label.config(text=data.get('text', ''))
        
        if data.get('status') == 'indeterminate':
            self.dep_progress_bar.config(mode='indeterminate')
            self.dep_progress_bar.start(10)
        elif data.get('status') == 'determinate':
            self.dep_progress_bar.stop()
            self.dep_progress_bar.config(mode='determinate')
            self.dep_progress_bar['value'] = data.get('value', 0)
    
    def close_dependency_progress_window(self):
        if self.dependency_progress_win:
            self.dep_progress_bar.stop()
            self.dependency_progress_win.destroy()
            self.dependency_progress_win = None

    def open_settings_window(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Settings")
        settings_win.geometry("350x120")
        settings_win.resizable(False, False)
        settings_win.transient(self.root) # Keep on top of main window

        settings_frame = ttk.Frame(settings_win, padding="10")
        settings_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(settings_frame, text="Max Concurrent Downloads:").grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)
        
        concurrent_var = tk.IntVar(value=self.max_concurrent_downloads)
        
        spinbox = ttk.Spinbox(settings_frame, from_=1, to=20, textvariable=concurrent_var, width=5)
        spinbox.grid(row=0, column=1, padx=5, pady=10)

        def apply_and_close():
            try:
                new_value = concurrent_var.get()
                if 1 <= new_value <= 20:
                    self.max_concurrent_downloads = new_value
                    self.log(f"Settings updated: Max concurrent downloads set to {self.max_concurrent_downloads}")
                    settings_win.destroy()
                else:
                    messagebox.showwarning("Invalid Value", "Please enter a number between 1 and 20.", parent=settings_win)
            except tk.TclError:
                 messagebox.showwarning("Invalid Value", "Please enter a valid integer.", parent=settings_win)

        close_button = ttk.Button(settings_frame, text="Save and Close", command=apply_and_close)
        close_button.grid(row=1, column=0, columnspan=2, pady=10)
        
        settings_win.protocol("WM_DELETE_WINDOW", apply_and_close)

    def browse_output_path(self):
        path = filedialog.askdirectory(initialdir=self.output_path_var.get())
        if path:
            self.output_path_var.set(path)
            
    def log(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + '\n')
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def queue_downloads(self):
        if self.download_button['state'] == 'disabled' or not self.yt_dlp_path:
            return

        urls_raw = self.url_text.get(1.0, tk.END).strip()
        if not urls_raw:
            messagebox.showwarning("Input Error", "Please enter at least one URL.")
            return
        
        download_format = self.format_var.get()
        if download_format in ['video', 'audio_best', 'audio_mp3']:
            if not self.ffmpeg_path:
                self.ffmpeg_path = find_ffmpeg()
            if not self.ffmpeg_path:
                self.initiate_dependency_download('ffmpeg')
                return

        urls = [url for url in urls_raw.split('\n') if url.strip()]
        self.url_text.delete(1.0, tk.END)
        
        self.log("--- Queuing new URLs ---")
        
        feeder_thread = threading.Thread(target=self.process_urls_and_feed_queue, args=(urls,), daemon=True)
        feeder_thread.start()

    def process_urls_and_feed_queue(self, urls):
        download_format = self.format_var.get()
        output_path = self.output_path_var.get()

        for url in urls:
            self.gui_queue.put(('log', f"Processing URL: {url}"))
            try:
                command = [self.yt_dlp_path, '--flat-playlist', '--print', '%(webpage_url)s', url]
                
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                stdout, stderr = process.communicate()

                if process.returncode != 0:
                    self.gui_queue.put(('log', f"Error processing URL {url}: {stderr.strip()}"))
                    continue

                video_urls = [line for line in stdout.splitlines() if line.strip()]
                if not video_urls:
                     self.gui_queue.put(('log', f"Warning: No videos found for URL {url}"))
                     continue

                self.gui_queue.put(('log', f"Found {len(video_urls)} video(s) for {url}."))
                
                with self.stats_lock:
                    self.total_jobs += len(video_urls)
                
                for video_url in video_urls:
                    with self.stats_lock:
                        job_id = f"job_{self.job_counter}"
                        self.job_counter += 1
                    
                    self.gui_queue.put(('add_job', (job_id, video_url, "Queued", "0%")))
                    self.job_queue.put((job_id, video_url, output_path, download_format))

            except Exception as e:
                self.gui_queue.put(('log', f"An unexpected error occurred while processing {url}: {e}"))

        self.start_workers()

    def start_workers(self):
        self.workers = [w for w in self.workers if w.is_alive()]
        num_to_start = self.max_concurrent_downloads - len(self.workers)
        for _ in range(num_to_start):
            worker = threading.Thread(target=self.worker_thread, daemon=True)
            self.workers.append(worker)
            worker.start()

    def worker_thread(self):
        while True:
            try:
                job_id, url, output_path, download_format = self.job_queue.get(timeout=1)
                self.gui_queue.put(('update_job', (job_id, 'status', 'Downloading')))
                self.run_download_process(job_id, url, output_path, download_format)
                self.job_queue.task_done()
            except queue.Empty:
                break

    def run_download_process(self, job_id, url, output_path, download_format):
        try:
            # Define a robust, machine-readable progress template
            progress_template = 'PROGRESS::%(progress.percentage)s'
            
            command = [
                self.yt_dlp_path,
                '--no-progress',  # Suppress the default visual progress bar
                '--progress-template', progress_template,  # Use our custom template
                '--no-mtime',
                '-o', f'{output_path}/%(title).100s [%(id)s].%(ext)s'
            ]

            if download_format == 'video':
                command.extend(['-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'])
            elif download_format == 'audio_best':
                command.extend(['-f', 'bestaudio/best', '-x'])
            elif download_format == 'audio_mp3':
                command.extend(['-f', 'bestaudio/best', '-x', '--audio-format', 'mp3', '--audio-quality', '192K'])

            command.append(url)
            
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding='utf-8', errors='replace', bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )

            for line in iter(process.stdout.readline, ''):
                clean_line = line.strip()
                self.gui_queue.put(('log', f"[{job_id}] {clean_line}"))
                
                # Parse the custom progress template instead of using regex
                if clean_line.startswith('PROGRESS::'):
                    try:
                        # Extract percentage from "PROGRESS:: 45.6"
                        percentage_str = clean_line.split('::', 1)[1].strip()
                        percentage = float(percentage_str)
                        self.gui_queue.put(('update_job', (job_id, 'progress', f"{percentage:.1f}%")))
                    except (IndexError, ValueError) as e:
                        self.gui_queue.put(('log', f"[{job_id}] Could not parse progress line: '{clean_line}', error: {e}"))

            process.stdout.close()
            return_code = process.wait()

            with self.stats_lock:
                self.completed_jobs += 1
            
            if return_code == 0:
                self.gui_queue.put(('done', (job_id, 'Completed')))
            else:
                self.gui_queue.put(('done', (job_id, 'Failed')))

        except Exception as e:
            with self.stats_lock:
                self.completed_jobs += 1
            self.gui_queue.put(('done', (job_id, f"Error")))
            self.gui_queue.put(('log', f"[{job_id}] Exception: {e}"))

    def process_gui_queue(self):
        try:
            while True:
                message_type, value = self.gui_queue.get_nowait()
                
                if message_type == 'log':
                    self.log(value)
                
                elif message_type == 'add_job':
                    job_id, url, status, progress = value
                    self.downloads_tree.insert('', 'end', iid=job_id, values=(url, status, progress))
                    self.update_overall_progress()

                elif message_type == 'update_job':
                    job_id, column, new_value = value
                    if self.downloads_tree.exists(job_id):
                        self.downloads_tree.set(job_id, column, new_value)

                elif message_type == 'done':
                    job_id, status = value
                    if self.downloads_tree.exists(job_id):
                        if status == 'Completed':
                           self.downloads_tree.set(job_id, 'progress', '100.0%')
                           self.downloads_tree.item(job_id, tags=('completed',))
                        else:
                            self.downloads_tree.item(job_id, tags=('failed',))
                        self.downloads_tree.set(job_id, 'status', status)
                    self.update_overall_progress()

                elif message_type == 'dependency_progress':
                    self.update_dependency_progress(value)

                elif message_type == 'dependency_done':
                    self.close_dependency_progress_window()
                    self.toggle_ui_state(True)
                    
                    dep_type = value.get('type')
                    if value.get('success'):
                        path = value.get('path')
                        if dep_type == 'yt-dlp':
                            self.yt_dlp_path = path
                        elif dep_type == 'ffmpeg':
                            self.ffmpeg_path = path
                        messagebox.showinfo("Success", f"{dep_type.upper()} downloaded successfully to:\n{path}")
                    else:
                        error_msg = value.get('error')
                        messagebox.showerror(f"{dep_type.upper()} Download Failed", f"An error occurred: {error_msg}")
                        if dep_type == 'yt-dlp':
                            self.root.destroy()
        
        except queue.Empty:
            self.root.after(100, self.process_gui_queue)

    def update_overall_progress(self):
        with self.stats_lock:
            label_text = f"Overall Progress: {self.completed_jobs} / {self.total_jobs}"
            self.overall_progress_label.config(text=label_text)
            
            if self.total_jobs > 0:
                progress_percent = (self.completed_jobs / self.total_jobs) * 100
                self.overall_progress_bar['value'] = progress_percent
            else:
                self.overall_progress_bar['value'] = 0

            if self.total_jobs > 0 and self.completed_jobs == self.total_jobs:
                 self.gui_queue.put(('log', "\n--- All queued downloads are complete! ---"))


if __name__ == "__main__":
    root = tk.Tk()
    app = YTDlpDownloaderApp(root)
    root.mainloop()
