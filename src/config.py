import os
import json
import shutil
import time
import re
import logging

class ConfigManager:
    """Handles loading, saving, and validating the application configuration."""
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        self.defaults = {
            'download_type': 'video', 'video_resolution': '1080', 'audio_format': 'mp3',
            'embed_thumbnail': True, 'filename_template': '%(title).100s [%(id)s].%(ext)s',
            'max_concurrent_downloads': 4, 'last_output_path': os.path.expanduser("~"),
            'log_level': 'INFO'
        }
        # Ensure the configuration directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

    def load(self):
        """Loads config, merges with defaults, validates, and returns it."""
        if not os.path.exists(self.config_path):
            return self.defaults.copy()
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # Merge with defaults to ensure all keys exist
            for key, value in self.defaults.items():
                config.setdefault(key, value)
            self.validate(config)
            return config
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Error loading config.json: {e}. Backing up and using defaults.")
            try:
                if os.path.exists(self.config_path):
                    shutil.move(self.config_path, f"{self.config_path}.{int(time.time())}.bak")
            except IOError:
                pass
            return self.defaults.copy()

    def save(self, settings_dict):
        """Saves the provided settings dictionary to the config file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=4)
        except IOError as e:
            self.logger.error(f"Error saving config file: {e}")

    def validate(self, config):
        """Validates configuration values and reverts invalid ones to defaults."""
        if not isinstance(config.get('max_concurrent_downloads'), int) or not (1 <= config['max_concurrent_downloads'] <= 20):
            self.logger.warning(f"Invalid max_concurrent_downloads '{config.get('max_concurrent_downloads')}'. Reverting to default.")
            config['max_concurrent_downloads'] = self.defaults['max_concurrent_downloads']

        log_level = config.get('log_level', '').upper()
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if log_level not in allowed_levels:
            self.logger.warning(f"Invalid log_level '{config.get('log_level')}'. Reverting to default 'INFO'.")
            config['log_level'] = self.defaults['log_level']
        else:
            config['log_level'] = log_level  # Ensure it's stored in uppercase

        template = config.get('filename_template', '')
        is_invalid = (
            not template or
            not re.search(r'%\((title|id)', template) or
            '/' in template or '\\' in template or '..' in template or
            os.path.isabs(template)
        )
        if is_invalid:
            self.logger.warning(f"Invalid filename_template '{template}'. Reverting to default.")
            config['filename_template'] = self.defaults['filename_template']
        
        if not os.path.isdir(config.get('last_output_path', '')):
            config['last_output_path'] = self.defaults['last_output_path']