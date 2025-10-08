# Multiyt-dlp: A Robust GUI for yt-dlp

A user-friendly graphical interface for the powerful command-line tool `yt-dlp`. It's designed to simplify the process of downloading multiple videos or entire playlists in parallel, with extensive format options, powerful customization, and automatic dependency handling.

<img width="852" height="782" alt="A screenshot of Multiyt-dlp" src="https://github.com/user-attachments/assets/5a150afe-7b9f-49a9-916b-05225259504e" />

## ✨ Key Features

-   **Standalone Executables**: No need to install Python. Just download the application for your operating system and run it!
-   **Automatic Dependency Management**: If `yt-dlp` or `FFmpeg` are missing, the app will offer to download the correct versions for your OS on the first run.
-   **In-App Updates**: Easily update `yt-dlp` and `FFmpeg` to their latest versions directly from the Settings menu.

### Advanced Download Control

-   **Batch & Concurrent Downloading**: Paste multiple video/playlist URLs and download them simultaneously. The number of concurrent downloads is configurable.
-   **Playlist Expansion**: Automatically detects and queues all individual videos from a playlist or channel URL, handling even very large playlists efficiently.
-   **Flexible Video Formats**: Choose your preferred video resolution (Best, 1080p, 720p, 480p) for MP4 downloads.
-   **Rich Audio Formats**: Extract audio directly to various formats, including `mp3` (192k), `m4a`, `flac`, `wav`, or the best available quality.
-   **Embed Thumbnails**: Automatically embed the video's thumbnail as cover art for audio downloads.

### User-Friendly Interface

-   **Real-time Progress Tracking**: An overall progress bar and a detailed list view show the status (`Downloading`, `Completed`, `Failed`) and progress of each individual download.
-   **Detailed Log Viewer**: See the live output from `yt-dlp` for diagnostics and detailed status information.
-   **Queue Management**: Right-click a download to **Retry Failed Items** or **Open the Output Folder**. You can also **Clear Completed** items to tidy up the view.
-   **Graceful Stop**: A "Stop All" button safely terminates all active downloads and cleans up temporary files.

### Powerful Customization

-   **Custom Filename Templates**: Define your own file naming structure using `yt-dlp`'s output template variables (e.g., `%(uploader)s - %(title)s.%(ext)s`).
-   **Persistent Configuration**: Remembers your output folder, preferred formats, filename template, and concurrency settings between sessions via a `config.json` file.
-   **Cross-Platform**: Natively supports Windows, macOS, and Linux.

## 🚀 Getting Started (Recommended Method)

For most users, downloading the pre-built application is the quickest way to get started.

1.  Go to the [**Latest Releases Page**](https://github.com/zqily/multiyt-dlp/releases/latest).
2.  Download the appropriate file for your operating system.
3.  Run the application:
    -   **Windows**: Double-click the `.exe` file.
    -   **macOS**: Double-click the extracted application. You may need to right-click the app icon and select "Open" the first time to bypass security warnings.
    -   **Linux**: Make the file executable with `chmod +x multiyt-dlp-linux`, then run it with `./multiyt-dlp-linux`.
4.  **First Run**: The app will check for `yt-dlp` and `FFmpeg`. If not found, it will prompt you to download them automatically. This is the recommended approach.
5.  You're ready to go! Paste your URLs, choose a folder and format, and start downloading.

## ⚙️ Settings & Customization

Click the **"Settings"** button to open the configuration window where you can:

-   **Set Max Concurrent Downloads**: Adjust how many videos are downloaded in parallel (default is 4).
-   **Define Filename Template**: Customize how your downloaded files are named. The default is `%(title).100s [%(id)s].%(ext)s`.
-   **Update Dependencies**: Check your version of `yt-dlp` and manually trigger an update for both `yt-dlp` and `FFmpeg` to ensure you have the latest features and fixes.

## 👨‍💻 Running from Source (Advanced Users)

If you prefer to run the script directly using Python, or want to modify the code:

### Requirements

-   [Python 3.x](https://www.python.org/downloads/)
-   Tkinter (Usually included with Python. On some Linux distributions, you may need to install it separately, e.g., `sudo apt-get install python3-tk`).

### Instructions

1.  Clone this repository or download the `multiyt-dlp.py` file.
2.  Open a terminal and navigate to the directory where you saved the file.
3.  Run the script:
    ```bash
    python multiyt-dlp.py
    ```
4.  As with the executable, the script will check for `yt-dlp` and `FFmpeg` and offer to download them if they are not found in your system's PATH or the script's directory.

## 🛠️ How It Works

-   When you add URLs, the script uses `yt-dlp` with `--flat-playlist` to efficiently expand playlists into a full list of individual video URLs without fetching metadata for every single one upfront.
-   These jobs are added to a central queue.
-   A pool of worker threads (the number of which is configured in Settings) pulls jobs from the queue and executes the `yt-dlp` download command for each one.
-   The GUI is updated in real-time by processing messages from the worker threads via a thread-safe queue, ensuring the interface remains responsive even under heavy load.

## 📄 License

This project is licensed under the MIT License.