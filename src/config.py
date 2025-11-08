"""
Manages loading, saving, and validating the application configuration using Pydantic.

This module defines the configuration schema as a Pydantic model (`Settings`)
and provides a manager class (`ConfigManager`) to handle persistence to a JSON file.
"""

import json
import time
import re
import logging
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field, validator, ValidationError


class Settings(BaseModel):
    """
    Defines the application's configuration schema using Pydantic.

    This class provides type hints, default values, and validation logic for all
    configuration settings.
    """
    download_type: str = 'video'
    video_resolution: str = '1080'
    audio_format: str = 'mp3'
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    filename_template: str = '%(title).100s [%(id)s].%(ext)s'
    max_concurrent_downloads: int = Field(default=4, ge=1, le=20)
    last_output_path: Path = Field(default_factory=Path.home)
    log_level: str = 'INFO'
    check_for_updates_on_startup: bool = True
    skipped_update_version: str = ''

    @validator('log_level')
    def validate_log_level(cls, value: str) -> str:
        """Ensures log_level is a valid logging level string."""
        upper_value = value.upper()
        allowed_levels: List[str] = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if upper_value not in allowed_levels:
            raise ValueError(f"'{value}' is not a valid log level. Must be one of {allowed_levels}.")
        return upper_value

    @validator('filename_template')
    def validate_filename_template(cls, value: str) -> str:
        """
        Validates the yt-dlp filename template.

        Raises:
            ValueError: If the template is invalid.
        """
        is_invalid = (
            not value or
            not re.search(r'%\((?:title|id)\)', value) or
            '/' in value or '\\' in value or '..' in value or
            Path(value).is_absolute()
        )
        if is_invalid:
            raise ValueError("Filename template is invalid. It must include %(title)s or %(id)s and cannot contain path separators.")
        return value

    @validator('last_output_path', pre=True, always=True)
    def validate_last_output_path(cls, value: str) -> Path:
        """Ensures the last output path exists and is a directory."""
        path = Path(value)
        if not path.is_dir():
            return Path.home()
        return path

    class Config:
        # Pydantic configuration to allow Path objects
        json_encoders = {Path: str}


class ConfigManager:
    """Handles loading and saving the application configuration file."""
    def __init__(self, config_path: Path):
        """
        Initializes the ConfigManager.

        Args:
            config_path: The path to the configuration file.
        """
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        # Ensure the configuration directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Settings:
        """
        Loads config from file, merges with defaults, validates, and returns it.

        If the file doesn't exist, is invalid, or an error occurs, a default
        configuration is returned. Invalid files are backed up.

        Returns:
            A validated Settings object.
        """
        if not self.config_path.exists():
            self.logger.info("Config file not found. Creating with default settings.")
            default_settings = Settings()
            self.save(default_settings)
            return default_settings

        try:
            config_data = json.loads(self.config_path.read_text(encoding='utf-8'))
            return Settings.model_validate(config_data)
        except (ValidationError, json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Error loading {self.config_path}: {e}. Backing up and using defaults.")
            try:
                backup_path = self.config_path.with_suffix(f".{int(time.time())}.bak")
                self.config_path.rename(backup_path)
                self.logger.info(f"Backed up corrupted config to {backup_path}")
            except IOError as backup_e:
                self.logger.error(f"Could not back up corrupted config file: {backup_e}")
            return Settings()

    def save(self, settings: Settings):
        """
        Saves the provided settings object to the config file.

        Args:
            settings: The Settings object to save.
        """
        try:
            # Use settings.model_dump_json() for Pydantic V2 compatibility and correct serialization.
            self.config_path.write_text(settings.model_dump_json(indent=4), encoding='utf-8')
        except IOError as e:
            self.logger.error(f"Error saving config file to {self.config_path}: {e}")