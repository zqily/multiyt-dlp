"""
Defines custom exceptions used throughout the application.

These exceptions allow for more specific error handling than built-in exceptions.
"""

class DownloadCancelledError(Exception):
    """Custom exception for cancelled downloads."""
    pass

class URLExtractionError(Exception):
    """Custom exception for URL processing failures."""
    pass