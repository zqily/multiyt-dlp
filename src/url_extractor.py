"""
Provides methods to extract information from URLs using yt-dlp.
"""

import subprocess
import sys
import logging
import threading
from pathlib import Path
from typing import List, Tuple

from .exceptions import URLExtractionError, DownloadCancelledError
from .constants import SUBPROCESS_CREATION_FLAGS


class URLInfoExtractor:
    """
    Provides methods to extract information from URLs using yt-dlp.

    This class uses fast, non-JSON-based commands for performance.
    """
    def __init__(self, yt_dlp_path: Path, stop_event: threading.Event):
        """
        Initializes the URLInfoExtractor.

        Args:
            yt_dlp_path: The path to the yt-dlp executable.
            stop_event: A threading.Event to signal cancellation.
        """
        self.yt_dlp_path = yt_dlp_path
        self.stop_event = stop_event
        self.logger = logging.getLogger(__name__)

    def _parse_yt_dlp_error(self, stderr: str) -> str:
        """
        Parses stderr from yt-dlp to find a concise error message.

        Args:
            stderr: The standard error string from the yt-dlp process.

        Returns:
            A concise error message, or the last line of stderr as a fallback.
        """
        if not stderr:
            return "yt-dlp returned an error with no output."

        for line in stderr.strip().splitlines():
            if line.lower().startswith('error:'):
                error_msg = line[6:].strip()
                return error_msg[:200] + "..." if len(error_msg) > 200 else error_msg

        return stderr.strip().splitlines()[-1]

    def _run_command(self, command: List[str], timeout: int) -> Tuple[str, str]:
        """
        A robust wrapper for running a yt-dlp command.

        Args:
            command: The command and its arguments as a list of strings.
            timeout: The timeout in seconds for the command.

        Returns:
            A tuple of (stdout, stderr) on success.

        Raises:
            URLExtractionError: On any failure (e.g., timeout, non-zero exit code).
        """
        kwargs = {'text': True, 'encoding': 'utf-8', 'errors': 'replace'}
        if sys.platform == 'win32':
            kwargs['creationflags'] = SUBPROCESS_CREATION_FLAGS

        process = None
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
            stdout, stderr = process.communicate(timeout=timeout)
        except FileNotFoundError:
            self.logger.error(f"yt-dlp executable not found at: {self.yt_dlp_path}")
            raise URLExtractionError("yt-dlp executable not found.")
        except subprocess.TimeoutExpired:
            if process:
                process.kill()
            self.logger.error(f"yt-dlp command timed out: {' '.join(command)}")
            raise URLExtractionError("URL processing command timed out.")
        except OSError as e:
            self.logger.error(f"OS error running yt-dlp: {e}")
            raise URLExtractionError(f"OS error: {e}")

        # If we get here, process must have been created and completed.
        if process.returncode != 0:
            error_msg = self._parse_yt_dlp_error(stderr)
            self.logger.error(f"yt-dlp command failed for '{command[-1]}'. Stderr: {stderr.strip()}")
            raise URLExtractionError(error_msg)

        return stdout, stderr

    def get_video_count(self, url: str) -> int:
        """
        Efficiently counts the number of videos in a URL (single or playlist).

        Args:
            url: The URL to check.

        Returns:
            The number of videos found in the URL.

        Raises:
            DownloadCancelledError: If the stop_event is set.
            URLExtractionError: If the yt-dlp command fails.
        """
        if self.stop_event.is_set():
            raise DownloadCancelledError("URL processing cancelled.")

        command = [str(self.yt_dlp_path), '--flat-playlist', '--print', 'id', '--no-warnings', url]

        stdout, _ = self._run_command(command, timeout=60)

        count = len([line for line in stdout.splitlines() if line.strip()])
        return count

    def get_single_video_title(self, url: str) -> str:
        """
        Quickly retrieves the title for a single video URL.

        Args:
            url: The URL of the single video.

        Returns:
            The title of the video.

        Raises:
            DownloadCancelledError: If the stop_event is set.
            URLExtractionError: If the yt-dlp command fails.
        """
        if self.stop_event.is_set():
            raise DownloadCancelledError("URL processing cancelled.")

        command = [str(self.yt_dlp_path), '--get-title', '--no-warnings', url]
        stdout, _ = self._run_command(command, timeout=30)

        title = stdout.strip()
        return title if title else "Title not found"