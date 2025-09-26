# MultiYT-DLP: A Robust GUI for yt-dlp

A user-friendly graphical interface for the powerful command-line tool `yt-dlp`. It's designed to simplify the process of downloading multiple videos or entire playlists in parallel, with easy-to-select format options and automatic dependency handling.

<img width="1189" height="1081" alt="image" src="https://github.com/user-attachments/assets/70fbc989-ff35-44a6-be63-5c600b5d193f" />


## ✨ Key Features

-   **Automatic Dependency Management**: No `yt-dlp` or `FFmpeg`? The app will offer to download the correct versions for your OS (Windows, macOS, Linux) on the first run.
-   **Batch & Concurrent Downloading**: Paste multiple video/playlist URLs and download them simultaneously. The number of concurrent downloads is configurable in the settings.
-   **Playlist Expansion**: Automatically detects and queues all individual videos from a playlist URL.
-   **Simple Format Selection**: Easily choose between:
    -   Best Quality Video (MP4)
    -   Best Quality Audio (opus/webm, converted to best available)
    -   High-Quality MP3 Audio (192k)
-   **Real-time Progress Tracking**: An overall progress bar and a detailed list view show the status and progress of each individual download.
-   **Persistent Configuration**: Remembers your last used output folder, preferred format, and concurrency settings between sessions via a `config.json` file.
-   **Cross-Platform**: Designed to work on Windows, macOS, and Linux.

## 📋 Requirements

-   [Python 3.x](https://www.python.org/downloads/)
-   Tkinter (This is usually included with Python. On some Linux distributions, you may need to install it separately, e.g., `sudo apt-get install python3-tk`).

## 🚀 How to Use

1.  Clone this repository or download the `multiyt-dlp.py` file to your computer.
2.  Open a terminal or command prompt and navigate to the directory where you saved the file.
3.  Run the script:
    ```bash
    python multiyt-dlp.py
    ```
4.  **First Run:** The script will check for `yt-dlp` and `FFmpeg`. If they are not found in your system's PATH or the script's directory, it will prompt you to download them automatically. This is the recommended approach.
5.  Paste your video or playlist URLs into the text box (one URL per line).
6.  Click "Browse..." to select your desired output folder.
7.  Choose your preferred download format.
8.  Click the **"Add URLs to Queue & Download"** button to start.

## ⚙️ How It Works

-   When you add URLs, the script first uses `yt-dlp` to resolve them, expanding any playlists into a full list of individual video URLs.
-   These jobs are added to a queue.
-   A pool of worker threads (the size of which you can set in "Settings") pulls jobs from the queue and executes the `yt-dlp` download command for each one.
-   The GUI is updated in real-time with the progress and log output from the download processes.

## 📄 License

This project is licensed under the MIT License.
