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

def download_yt_dlp(window):
    """Downloads the appropriate yt-dlp binary for the current OS."""
    platform = sys.platform
    if platform not in YT_DLP_URLS:
        messagebox.showerror("Unsupported OS", f"Your OS ({platform}) is not supported for automatic download.")
        return None

    url = YT_DLP_URLS[platform]
    filename = os.path.basename(url)
    
    if platform == 'darwin' and filename == 'yt-dlp_macos':
        save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'yt-dlp')
    else:
        save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

    permission = messagebox.askyesno(
        "yt-dlp Not Found",
        "yt-dlp executable not found in your system PATH or script directory.\n\n"
        "Do you want to download the latest version automatically?"
    )

    if not permission:
        return None

    try:
        progress_win = tk.Toplevel(window)
        progress_win.title("Downloading yt-dlp")
        progress_win.geometry("300x80")
        progress_win.resizable(False, False)
        tk.Label(progress_win, text="Downloading yt-dlp...", pady=10).pack()
        progress_bar = ttk.Progressbar(progress_win, orient='horizontal', length=280, mode='indeterminate')
        progress_bar.pack()
        progress_bar.start(10)
        window.update_idletasks()

        response = urllib.request.urlopen(url)
        with open(save_path, 'wb') as f:
            f.write(response.read())

        progress_bar.stop()
        progress_win.destroy()

        if platform in ['linux', 'darwin']:
            os.chmod(save_path, 0o755)

        messagebox.showinfo("Success", f"yt-dlp downloaded successfully to:\n{save_path}")
        return save_path

    except Exception as e:
        messagebox.showerror("Download Failed", f"Failed to download yt-dlp: {e}")
        return None

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

def download_ffmpeg(window):
    """Downloads and extracts the appropriate FFmpeg binary for the current OS."""
    platform = sys.platform
    if platform not in FFMPEG_URLS:
        messagebox.showerror("Unsupported OS", f"Your OS ({platform}) is not supported for automatic FFmpeg download.")
        return None

    permission = messagebox.askyesno(
        "FFmpeg Not Found",
        "FFmpeg is required for the selected download format (e.g., merging video/audio or audio conversion) but was not found.\n\n"
        "Do you want to download it automatically? (This may be a large download)"
    )
    if not permission:
        return None

    url = FFMPEG_URLS[platform]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    archive_filename = os.path.basename(url)
    archive_path = os.path.join(script_dir, archive_filename)
    extract_dir = os.path.join(script_dir, "ffmpeg_temp")
    
    final_ffmpeg_name = 'ffmpeg.exe' if platform == 'win32' else 'ffmpeg'
    final_ffmpeg_path = os.path.join(script_dir, final_ffmpeg_name)

    progress_win = tk.Toplevel(window)
    progress_win.title("Downloading FFmpeg")
    progress_win.geometry("350x100")
    progress_win.resizable(False, False)
    label = tk.Label(progress_win, text="Downloading FFmpeg archive...", pady=10)
    label.pack()
    progress_bar = ttk.Progressbar(progress_win, orient='horizontal', length=320, mode='indeterminate')
    progress_bar.pack()
    progress_bar.start(10)
    window.update_idletasks()

    try:
        # 1. Download
        with urllib.request.urlopen(url) as response, open(archive_path, 'wb') as f_out:
            shutil.copyfileobj(response, f_out)
        
        # 2. Extract
        label.config(text="Extracting FFmpeg...")
        window.update_idletasks()
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir)

        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        elif archive_path.endswith('.tar.xz'):
            with tarfile.open(archive_path, 'r:xz') as tar_ref:
                tar_ref.extractall(path=extract_dir)
        
        # 3. Find and Move the ffmpeg executable
        label.config(text="Locating executable...")
        window.update_idletasks()
        
        ffmpeg_executable_path = None
        for root, _, files in os.walk(extract_dir):
            if final_ffmpeg_name in files:
                ffmpeg_executable_path = os.path.join(root, final_ffmpeg_name)
                break
        
        if not ffmpeg_executable_path:
            raise FileNotFoundError(f"Could not find '{final_ffmpeg_name}' in the extracted archive.")

        shutil.move(ffmpeg_executable_path, final_ffmpeg_path)

        # 4. Set permissions for Linux/macOS
        if platform in ['linux', 'darwin']:
            os.chmod(final_ffmpeg_path, 0o755)

        messagebox.showinfo("Success", f"FFmpeg downloaded successfully to:\n{final_ffmpeg_path}")
        return final_ffmpeg_path

    except Exception as e:
        messagebox.showerror("FFmpeg Download Failed", f"An error occurred: {e}")
        return None
    finally:
        # 5. Cleanup
        progress_bar.stop()
        progress_win.destroy()
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
        
        self.yt_dlp_path = find_yt_dlp()
        if not self.yt_dlp_path:
            self.yt_dlp_path = download_yt_dlp(self.root)
        
        if not self.yt_dlp_path:
            messagebox.showerror("Critical Error", "yt-dlp is required to run this application. Exiting.")
            self.root.destroy()
            return

        # Concurrency and state management
        self.job_queue = queue.Queue()
        self.gui_queue = queue.Queue()
        self.workers = []
        self.job_counter = 0
        self.completed_jobs = 0
        self.total_jobs = 0
        self.stats_lock = threading.Lock()

        self.create_widgets()
        self.process_gui_queue()
        
        # Save settings on exit
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """Handle saving the configuration and closing the application."""
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
        browse_btn = ttk.Button(input_frame, text="Browse...", command=self.browse_output_path)
        browse_btn.grid(row=1, column=2, padx=5, pady=5)

        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.pack(fill=tk.X, pady=5)
        
        self.format_var = tk.StringVar(value=self.config.get('preferred_format', 'video'))
        ttk.Radiobutton(options_frame, text="Video (Best Quality)", variable=self.format_var, value="video").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(options_frame, text="Audio Only (Best Quality)", variable=self.format_var, value="audio_best").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(options_frame, text="Audio Only (MP3, 192k)", variable=self.format_var, value="audio_mp3").pack(side=tk.LEFT, padx=10)
        
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
        urls_raw = self.url_text.get(1.0, tk.END).strip()
        if not urls_raw:
            messagebox.showwarning("Input Error", "Please enter at least one URL.")
            return
        
        # Check for FFmpeg if the selected format requires it
        download_format = self.format_var.get()
        if download_format in ['video', 'audio_best', 'audio_mp3']:
            ffmpeg_path = find_ffmpeg()
            if not ffmpeg_path:
                ffmpeg_path = download_ffmpeg(self.root)
            
            if not ffmpeg_path:
                messagebox.showerror("Dependency Error", "FFmpeg is required for the selected format but is not available. Aborting.")
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
                # --- FIX 1: Changed command to get canonical URLs instead of direct stream URLs ---
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
                job_id, url, output_path, download_format = self.job_queue.get(timeout=1) # Add timeout to allow thread to exit gracefully if needed
                self.gui_queue.put(('update_job', (job_id, 'status', 'Downloading')))
                self.run_download_process(job_id, url, output_path, download_format)
                self.job_queue.task_done()
            except queue.Empty:
                # If the queue is empty, the worker can exit. This is a simple exit strategy.
                break

    def run_download_process(self, job_id, url, output_path, download_format):
        try:
            command = [
                self.yt_dlp_path, '--progress', '--no-mtime',
                # --- FIX 2: Added .100s to truncate title and prevent overly long filenames ---
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
                progress_match = re.search(r'\[download\]\s+(\d+\.?\d+)%', line)
                if progress_match:
                    percentage = float(progress_match.group(1))
                    self.gui_queue.put(('update_job', (job_id, 'progress', f"{percentage:.1f}%")))
            
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