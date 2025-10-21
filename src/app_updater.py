"""Manages checking for new application versions on GitHub."""
import logging
import threading
import json
from typing import Callable, Tuple, Any

import requests
from packaging.version import parse, InvalidVersion

from .constants import GITHUB_API_URL, REQUEST_HEADERS, REQUEST_TIMEOUTS
from ._version import __version__
from .config import Settings


class AppUpdater:
    """Checks for new application versions on GitHub."""

    def __init__(self, event_callback: Callable[[Tuple[str, Any]], None], config: Settings):
        """
        Initializes the AppUpdater.

        Args:
            event_callback: The function to call with manager events.
            config: The application's configuration settings object.
        """
        self.event_callback = event_callback
        self.config = config
        self.logger = logging.getLogger(__name__)

    def check_for_updates(self):
        """Starts the update check in a background thread."""
        thread = threading.Thread(target=self._perform_check, daemon=True, name="App-Update-Checker")
        thread.start()

    def _perform_check(self):
        """

        Fetches the latest release info from GitHub and compares versions.

        Communicates with the GUI via the event_callback if a new version is found.
        Handles network errors, parsing errors, and unexpected API responses gracefully.
        """
        self.logger.info("Checking for application updates...")
        latest_version_str = ""  # Initialize to prevent potential unbound error
        try:
            response = requests.get(GITHUB_API_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUTS)
            response.raise_for_status()

            data = response.json()
            if not isinstance(data, dict):
                self.logger.warning(f"Unexpected API response type: {type(data)}")
                return

            latest_version_str = data.get('tag_name')
            release_url = data.get('html_url')

            if not latest_version_str or not release_url:
                self.logger.warning("Could not find version tag or URL in API response.")
                return

            # Strip a leading 'v' if it exists, for cleaner parsing
            if latest_version_str.startswith('v'):
                latest_version_str = latest_version_str[1:]

            if latest_version_str == self.config.skipped_update_version:
                self.logger.info(f"Update for version {latest_version_str} has been skipped by the user.")
                return

            current_version = parse(__version__)
            latest_version = parse(latest_version_str)

            self.logger.info(f"Current version: {current_version}, Latest version found: {latest_version}")

            if latest_version > current_version:
                self.logger.info(f"New version available: {latest_version}")
                self.event_callback(('new_version_available', {
                    'version': str(latest_version),
                    'url': release_url
                }))

        except requests.exceptions.RequestException as e:
            status_code = f" (Status: {e.response.status_code})" if hasattr(e, 'response') and e.response is not None else ""
            self.logger.warning(f"Failed to check for updates (network error): {e}{status_code}")
        except (InvalidVersion, KeyError, TypeError, json.JSONDecodeError) as e:
            self.logger.warning(f"Could not parse API response from GitHub: {e}")
            if latest_version_str:
                self.logger.warning(f"Version string was: '{latest_version_str}'")
        except Exception:
            self.logger.exception("An unexpected error occurred during update check.")