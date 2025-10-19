import subprocess
import json
import sys
import logging
import threading

from .exceptions import URLExtractionError, DownloadCancelledError
from .constants import SUBPROCESS_CREATION_FLAGS

class URLInfoExtractor:
    """
    Extracts video information from URLs using yt-dlp.
    Implements a two-stage process: a quick probe for single videos/errors,
    and a more robust stream-based expansion for playlists.
    """
    def __init__(self, yt_dlp_path: str, stop_event: threading.Event):
        self.yt_dlp_path = yt_dlp_path
        self.stop_event = stop_event
        self.logger = logging.getLogger(__name__)

    def _parse_yt_dlp_error(self, stderr: str) -> str:
        """Parses stderr from yt-dlp to find a concise error message."""
        if not stderr:
            return "yt-dlp returned an error with no output."
        
        for line in stderr.strip().splitlines():
            if line.lower().startswith('error:'):
                error_msg = line[6:].strip()
                if len(error_msg) > 200:
                    return error_msg[:200] + "..."
                return error_msg
        
        return stderr.strip().splitlines()[-1]

    def extract_videos(self, url: str) -> tuple[list[dict], bool]:
        """
        Orchestrates the extraction process for a given URL.
        Returns a tuple: (list_of_video_dicts, was_partial_or_failed).
        Raises URLExtractionError on critical failure or DownloadCancelledError.
        """
        if self.stop_event.is_set():
            raise DownloadCancelledError("URL processing cancelled before start.")
            
        try:
            probe_data = self._probe_url(url)
            entry_type = probe_data.get('_type', 'video')

            if entry_type in ('playlist', 'multi_video'):
                self.logger.info(f"'{url}' identified as a playlist. Expanding...")
                return self._expand_playlist(url)
            else:
                self.logger.info(f"'{url}' identified as a single video.")
                video_url = probe_data.get('webpage_url') or url
                return ([{'url': video_url, 'title': probe_data.get('title', 'N/A')}], False)
        except (URLExtractionError, DownloadCancelledError):
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error extracting info for '{url}'")
            raise URLExtractionError(f"An unexpected error occurred: {e}")

    def _probe_url(self, url: str) -> dict:
        """
        Performs a quick, lightweight check on a URL using --dump-single-json.
        This efficiently handles single videos and detects most errors early.
        """
        command = [self.yt_dlp_path, '--dump-single-json', '--no-warnings', url]
        kwargs = {'text': True, 'encoding': 'utf-8', 'errors': 'replace'}
        if sys.platform == 'win32':
            kwargs['creationflags'] = SUBPROCESS_CREATION_FLAGS

        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        except FileNotFoundError:
            self.logger.error(f"yt-dlp executable not found at: {self.yt_dlp_path}")
            raise URLExtractionError("yt-dlp executable not found.")

        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            self.logger.error(f"Probe timed out for URL: {url}")
            raise URLExtractionError("URL probe timed out.")

        if process.returncode != 0:
            error_msg = self._parse_yt_dlp_error(stderr)
            self.logger.error(f"Probe failed for '{url}'. Stderr: {stderr.strip()}")
            raise URLExtractionError(error_msg)

        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to decode JSON from probe for '{url}'. Output: {stdout[:500]}")
            raise URLExtractionError("Could not parse yt-dlp output.")

    def _expand_playlist(self, url: str) -> tuple[list[dict], bool]:
        """
        Expands a playlist URL by reading its entries line by line.
        Returns a tuple: (list_of_videos, was_partial_or_failed).
        """
        command = [self.yt_dlp_path, '--flat-playlist', '--print-json', '--no-warnings', url]
        kwargs = {'text': True, 'encoding': 'utf-8', 'errors': 'replace'}
        if sys.platform == 'win32':
            kwargs['creationflags'] = SUBPROCESS_CREATION_FLAGS

        videos = []
        was_partial = False
        
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        
        stderr_output = []
        def read_pipe(pipe, output_list):
            if not pipe: return
            with pipe:
                for line in iter(pipe.readline, ''):
                    output_list.append(line)
        
        stderr_thread = threading.Thread(target=read_pipe, args=(process.stderr, stderr_output), daemon=True, name="stderr-reader")
        stderr_thread.start()

        try:
            if process.stdout:
                with process.stdout:
                    for line in iter(process.stdout.readline, ''):
                        if self.stop_event.is_set():
                            process.terminate()
                            raise DownloadCancelledError("Playlist expansion cancelled.")
                        try:
                            video_info = json.loads(line)
                            video_url = video_info.get('webpage_url') or video_info.get('url')
                            if video_url:
                                videos.append({'url': video_url, 'title': video_info.get('title', 'N/A')})
                        except json.JSONDecodeError:
                            self.logger.warning(f"Could not parse JSON line from playlist expansion: {line.strip()}")
            
            process.wait(timeout=60)
            
            if process.returncode != 0:
                stderr_thread.join(timeout=5)
                full_stderr = "".join(stderr_output)
                self.logger.error(f"Error during playlist expansion for '{url}': {full_stderr.strip()}")
                was_partial = True
                if not videos:
                    raise URLExtractionError(self._parse_yt_dlp_error(full_stderr))
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Playlist expansion timed out for URL: {url}")
            process.kill()
            was_partial = True
            if not videos:
                raise URLExtractionError("Playlist expansion timed out.")
        finally:
            if stderr_thread.is_alive():
                stderr_thread.join(timeout=1)
        
        return videos, was_partial