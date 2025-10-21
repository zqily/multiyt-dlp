"""
Defines the data class for a download job.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class DownloadJob:
    """
    Represents a single download task.

    Attributes:
        job_id: A unique identifier for the job.
        original_url: The URL provided by the user (can be a playlist).
        options: A dictionary of download settings for this job.
        playlist_index: The index if the item is from a playlist.
        title: The video title, fetched from yt-dlp.
        status: The current status of the download (e.g., "Queued", "Downloading").
        progress: A string representing the download progress (e.g., "50%").
    """
    job_id: str
    original_url: str
    options: Dict[str, Any] = field(default_factory=dict)
    playlist_index: Optional[int] = None
    title: str = "Waiting for title..."
    status: str = "Queued"
    progress: str = "0%"