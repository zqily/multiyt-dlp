# Multiyt-dlp: A Robust GUI for yt-dlp

A user-friendly graphical interface for the powerful command-line tool `yt-dlp`. It's designed to simplify the process of downloading multiple videos or entire playlists in parallel, with easy-to-select format options and automatic dependency handling.

<img width="852" height="782" alt="image" src="https://github.com/user-attachments/assets/ecf71263-0b31-49d4-9bb8-f861b59a9df3" />

## ✨ Key Features

-   **Standalone Executables**: No need to install Python or any dependencies. Just download the application for your operating system and run it!
-   **Automatic Dependency Management**: If `yt-dlp` or `FFmpeg` are missing, the app will offer to download the correct versions for your OS (Windows, macOS, Linux) on the first run.
-   **Batch & Concurrent Downloading**: Paste multiple video/playlist URLs and download them simultaneously. The number of concurrent downloads is configurable in the settings.
-   **Playlist Expansion**: Automatically detects and queues all individual videos from a playlist URL.
-   **Simple Format Selection**: Easily choose between:
    -   Best Quality Video (MP4)
    -   Best Quality Audio (opus/webm, converted to best available)
    -   High-Quality MP3 Audio (192k)
-   **Real-time Progress Tracking**: An overall progress bar and a detailed list view show the status and progress of each individual download.
-   **Persistent Configuration**: Remembers your last used output folder, preferred format, and concurrency settings between sessions via a `config.json` file.
-   **Cross-Platform**: Natively supports Windows, macOS, and Linux.

## 🚀 Getting Started (Recommended Method)

For most users, downloading the pre-built application is the quickest and easiest way to get started.

1.  Go to the [**Latest Releases Page**](https://github.com/zqily/multiyt-dlp/releases/latest).
2.  Download `Multiyt-dlp.exe`
3.  Run the application:
    -   **Windows**: Double-click the `.exe` file.
    -   **macOS**: Double-click the extracted application. You may need to right-click the app icon and select "Open" the first time to bypass security warnings.
    -   **Linux**: First, make the file executable by running `chmod +x multiyt-dlp-linux` in your terminal, then run it with `./multiyt-dlp-linux`.
4.  **First Run**: The app will check for `yt-dlp` and `FFmpeg`. If they are not found, it will prompt you to download them automatically. This is the recommended approach.
5.  You're ready to go! Paste your URLs, choose a folder and format, and start downloading.

## 👨‍💻 Running from Source (Advanced Users)

If you prefer to run the script directly using Python, or want to modify the code, follow these steps.

### Requirements

-   [Python 3.x](https://www.python.org/downloads/)
-   Tkinter (This is usually included with Python. On some Linux distributions, you may need to install it separately, e.g., `sudo apt-get install python3-tk`).

### Instructions

1.  Clone this repository or download the `multiyt-dlp.py` file to your computer.
2.  Open a terminal or command prompt and navigate to the directory where you saved the file.
3.  Run the script:
    ```bash
    python multiyt-dlp.py
    ```
4.  As with the executable, the script will check for `yt-dlp` and `FFmpeg` on first run and offer to download them for you if they are not found in your system's PATH or the script's directory.

## ⚙️ How It Works

-   When you add URLs, the script first uses `yt-dlp` to resolve them, expanding any playlists into a full list of individual video URLs.
-   These jobs are added to a central queue.
-   A pool of worker threads (the number of which you can set in "Settings") pulls jobs from the queue and executes the `yt-dlp` download command for each one.
-   The GUI is updated in real-time with the progress and log output from the download processes, ensuring the interface remains responsive.

## 📄 License

This project is licensed under the MIT License.
