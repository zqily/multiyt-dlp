# Multiyt-dlp: A Robust GUI for yt-dlp

A user-friendly graphical interface for the powerful command-line tool `yt-dlp`. It's designed to simplify the process of downloading multiple videos or entire playlists in parallel, with extensive format options, powerful customization, and automatic dependency handling.

<img width="852" height="782" alt="A screenshot of Multiyt-dlp" src="https://github.com/zqily/multiyt-dlp/raw/main/assets/multiyt-dlp-screenshot.png" />

## ✨ Key Features

-   **Standalone Windows Executable**: No need to install Python on Windows. Just download `Multiyt-dlp.exe` and run it!
-   **Automatic Dependency Management**: If `yt-dlp` or `FFmpeg` are missing, the app will offer to download the correct versions for your OS on the first run.
-   **In-App Updates**: Easily update `yt-dlp` and `FFmpeg` to their latest versions directly from the Settings menu.

### Advanced Download Control

-   **Batch & Concurrent Downloading**: Paste multiple video/playlist URLs and download them simultaneously. The number of concurrent downloads is configurable.
-   **Efficient Playlist Expansion**: Automatically detects and queues all individual videos from a playlist or channel URL, handling even very large playlists without freezing.
-   **Flexible Video Formats**: Choose your preferred video resolution (Best, 1080p, 720p, 480p) for MP4 downloads.
-   **Rich Audio Formats**: Extract audio directly to various formats, including `mp3` (192k), `m4a`, `flac`, `wav`, or the best available quality.
-   **Embed Thumbnails**: Automatically embed the video's thumbnail as cover art for audio downloads.

### User-Friendly Interface

-   **Real-time Progress Tracking**: An overall progress bar and a detailed list view show the status (`Downloading`, `Completed`, `Failed`) and progress of each individual download.
-   **Detailed Log Viewer**: See live, color-coded output from the application and `yt-dlp` for diagnostics and detailed status information.
-   **Queue Management**: Right-click a download to **Retry Failed Items** or **Open the Output Folder**. You can also **Clear Completed** items to tidy up the view.
-   **Graceful Stop**: A "Stop All" button safely terminates all active downloads and cleans up temporary files.

### Powerful Customization & Stability

-   **Custom Filename Templates**: Define your own file naming structure using `yt-dlp`'s output template variables (e.g., `%(uploader)s - %(title)s.%(ext)s`).
-   **Persistent Configuration**: Remembers your output folder, preferred formats, filename template, and concurrency settings between sessions via a `config.json` file stored in your user profile.
-   **Robust Error Handling**: The application is designed to handle network issues and invalid URLs gracefully.
-   **Cross-Platform Script**: While the executable is for Windows, the underlying Python script is fully compatible with macOS and Linux.

## 🚀 Getting Started

### For Windows Users (Recommended)

1.  Go to the [**Latest Releases Page**](https://github.com/zqily/multiyt-dlp/releases/latest).
2.  Download the `Multiyt-dlp.exe` file.
3.  Run the application by double-clicking the `.exe` file.
4.  **First Run**: The app will check for `yt-dlp` and `FFmpeg`. If not found, it will prompt you to download them automatically. This is the recommended approach.
5.  You're ready to go! Paste your URLs, choose a folder and format, and start downloading.

### For macOS & Linux Users

As I only build for Windows, macOS and Linux users will need to run the application from the source code.

1.  **Ensure you have Python 3.8+ installed.**
2.  Follow the instructions in the **[Running from Source](#%EF%B8%8F-running-from-source-advanced-users)** section below.

## ⚙️ Settings & Customization

Click the **"Settings"** button to open the configuration window where you can:

-   **Set Max Concurrent Downloads**: Adjust how many videos are downloaded in parallel (default is 4).
-   **Define Filename Template**: Customize how your downloaded files are named. The default is `%(title).100s [%(id)s].%(ext)s`.
-   **Set File Log Level**: Change the verbosity of the log file (`latest.log`) for debugging purposes. (Requires restart).
-   **Update Dependencies**: Check your version of `yt-dlp` and manually trigger an update for both `yt-dlp` and `FFmpeg` to ensure you have the latest features and fixes.

## 👨‍💻 Running from Source (Advanced Users)

If you prefer to run the script directly using Python:

### Requirements

-   [Python 3.x](https://www.python.org/downloads/)
-   The `requests` library: `pip install requests`
-   Tkinter (Usually included with Python. On some Linux distributions, you may need to install it separately, e.g., `sudo apt-get install python3-tk`).

### Instructions

1.  Clone this repository: `git clone https://github.com/zqily/multiyt-dlp.git`
2.  Navigate to the cloned directory: `cd multiyt-dlp`
3.  Run the script from the project's root directory:
    ```bash
    python src/main.py
    ```
4.  As with the executable, the script will check for `yt-dlp` and `FFmpeg` and offer to download them if they are not found in your system's PATH or the script's directory.

## 🛠️ How It Works

-   When you add URLs, the script uses `yt-dlp` with `--flat-playlist --print-json` to efficiently expand playlists into a full list of individual video URLs without fetching metadata for every single one upfront.
-   These jobs are added to a central queue.
-   A pool of worker threads (the number of which is configured in Settings) pulls jobs from the queue and executes the `yt-dlp` download command for each one.
-   The GUI is updated in real-time by processing messages from the worker threads via a thread-safe queue, ensuring the interface remains responsive even under heavy load.

## 📄 License

This project is licensed under the MIT License.