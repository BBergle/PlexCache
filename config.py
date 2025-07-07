"""
Configuration management for PlexCache.
Handles loading, validation, and management of application settings.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class NotificationConfig:
    """Configuration for notification settings."""
    notification_type: str = "system"  # "Unraid", "Webhook", "Both", or "System"
    unraid_level: str = "summary"
    webhook_level: str = ""
    webhook_url: str = ""
    webhook_headers: Optional[Dict[str, str]] = None

    def __post_init__(self):
        if self.webhook_headers is None:
            self.webhook_headers = {}


@dataclass
class PathConfig:
    """Configuration for file paths and directories."""
    script_folder: str = "/mnt/user/system/plexcache/"
    logs_folder: str = "/mnt/user/system/plexcache/"
    plex_source: str = ""
    real_source: str = ""
    cache_dir: str = ""
    nas_library_folders: Optional[List[str]] = None
    plex_library_folders: Optional[List[str]] = None

    def __post_init__(self):
        if self.nas_library_folders is None:
            self.nas_library_folders = []
        if self.plex_library_folders is None:
            self.plex_library_folders = []


@dataclass
class PlexConfig:
    """Configuration for Plex server settings."""
    plex_url: str = ""
    plex_token: str = ""
    valid_sections: Optional[List[int]] = None
    number_episodes: int = 10
    days_to_monitor: int = 183
    users_toggle: bool = True
    skip_ondeck: Optional[List[str]] = None
    skip_watchlist: Optional[List[str]] = None

    def __post_init__(self):
        if self.valid_sections is None:
            self.valid_sections = []
        if self.skip_ondeck is None:
            self.skip_ondeck = []
        if self.skip_watchlist is None:
            self.skip_watchlist = []


@dataclass
class CacheConfig:
    """Configuration for caching behavior."""
    watchlist_toggle: bool = True
    watchlist_episodes: int = 5
    watchlist_cache_expiry: int = 48
    watched_cache_expiry: int = 48
    watched_move: bool = True


@dataclass
class PerformanceConfig:
    """Configuration for performance settings."""
    max_concurrent_moves_array: int = 2
    max_concurrent_moves_cache: int = 5
    retry_limit: int = 3
    delay: int = 5
    permissions: int = 0o777


class ConfigManager:
    """Manages application configuration loading and validation."""
    
    def __init__(self, config_file: str):
        self.config_file = Path(config_file)
        self.settings_data: Dict[str, Any] = {}
        self.notification = NotificationConfig()
        self.paths = PathConfig()
        self.plex = PlexConfig()
        self.cache = CacheConfig()
        self.performance = PerformanceConfig()
        self.debug = False
        self.exit_if_active_session = False
        
    def load_config(self) -> None:
        """Load configuration from file and validate."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Settings file not found: {self.config_file}")
        
        try:
            with open(self.config_file, 'r') as f:
                self.settings_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in settings file: {e}")
        
        self._process_first_start()
        self._load_all_configs()
        self._validate_config()
        self._save_updated_config()
    
    def _process_first_start(self) -> None:
        """Handle first start configuration."""
        firststart = self.settings_data.get('firststart')
        if firststart:
            self.debug = True
            logging.warning("First start is set to true, setting debug mode temporarily to true.")
            del self.settings_data['firststart']
        else:
            self.debug = self.settings_data.get('debug', False)
            if firststart is not None:
                del self.settings_data['firststart']
    
    def _load_all_configs(self) -> None:
        """Load all configuration sections."""
        self._load_plex_config()
        self._load_cache_config()
        self._load_path_config()
        self._load_performance_config()
        self._load_misc_config()
    
    def _load_plex_config(self) -> None:
        """Load Plex-related configuration."""
        self.plex.plex_url = self.settings_data['PLEX_URL']
        self.plex.plex_token = self.settings_data['PLEX_TOKEN']
        self.plex.number_episodes = self.settings_data['number_episodes']
        self.plex.valid_sections = self.settings_data['valid_sections']
        self.plex.days_to_monitor = self.settings_data['days_to_monitor']
        self.plex.users_toggle = self.settings_data['users_toggle']
        
        # Handle skip settings
        skip_users = self.settings_data.get('skip_users')
        if skip_users is not None:
            self.plex.skip_ondeck = self.settings_data.get('skip_ondeck', skip_users)
            self.plex.skip_watchlist = self.settings_data.get('skip_watchlist', skip_users)
            del self.settings_data['skip_users']
        else:
            self.plex.skip_ondeck = self.settings_data.get('skip_ondeck', [])
            self.plex.skip_watchlist = self.settings_data.get('skip_watchlist', [])
    
    def _load_cache_config(self) -> None:
        """Load cache-related configuration."""
        self.cache.watchlist_toggle = self.settings_data['watchlist_toggle']
        self.cache.watchlist_episodes = self.settings_data['watchlist_episodes']
        self.cache.watchlist_cache_expiry = self.settings_data['watchlist_cache_expiry']
        self.cache.watched_cache_expiry = self.settings_data['watched_cache_expiry']
        self.cache.watched_move = self.settings_data['watched_move']
    
    def _load_path_config(self) -> None:
        """Load path-related configuration."""
        self.paths.plex_source = self._add_trailing_slashes(self.settings_data['plex_source'])
        self.paths.real_source = self._add_trailing_slashes(self.settings_data['real_source'])
        self.paths.cache_dir = self._add_trailing_slashes(self.settings_data['cache_dir'])
        self.paths.nas_library_folders = self._remove_all_slashes(self.settings_data['nas_library_folders'])
        self.paths.plex_library_folders = self._remove_all_slashes(self.settings_data['plex_library_folders'])
    
    def _load_performance_config(self) -> None:
        """Load performance-related configuration."""
        self.performance.max_concurrent_moves_array = self.settings_data['max_concurrent_moves_array']
        self.performance.max_concurrent_moves_cache = self.settings_data['max_concurrent_moves_cache']
    
    def _load_misc_config(self) -> None:
        """Load miscellaneous configuration."""
        self.exit_if_active_session = self.settings_data.get('exit_if_active_session')
        if self.exit_if_active_session is None:
            self.exit_if_active_session = not self.settings_data.get('skip', False)
            if 'skip' in self.settings_data:
                del self.settings_data['skip']
        
        # Remove deprecated settings
        if 'unraid' in self.settings_data:
            del self.settings_data['unraid']
    
    def _validate_config(self) -> None:
        """Validate the loaded configuration."""
        required_fields = [
            'PLEX_URL', 'PLEX_TOKEN', 'number_episodes', 'valid_sections',
            'days_to_monitor', 'users_toggle', 'watchlist_toggle',
            'watchlist_episodes', 'watchlist_cache_expiry', 'watched_cache_expiry',
            'watched_move', 'plex_source', 'cache_dir', 'real_source',
            'nas_library_folders', 'plex_library_folders',
            'max_concurrent_moves_array', 'max_concurrent_moves_cache'
        ]
        
        missing_fields = [field for field in required_fields if field not in self.settings_data]
        if missing_fields:
            raise ValueError(f"Missing required fields in settings: {missing_fields}")
    
    def _save_updated_config(self) -> None:
        """Save updated configuration back to file."""
        try:
            self.settings_data.update({
                'cache_dir': self.paths.cache_dir,
                'real_source': self.paths.real_source,
                'plex_source': self.paths.plex_source,
                'nas_library_folders': self.paths.nas_library_folders,
                'plex_library_folders': self.paths.plex_library_folders,
                'skip_ondeck': self.plex.skip_ondeck,
                'skip_watchlist': self.plex.skip_watchlist,
                'exit_if_active_session': self.exit_if_active_session,
            })
            
            with open(self.config_file, 'w') as f:
                json.dump(self.settings_data, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
            raise
    
    @staticmethod
    def _add_trailing_slashes(value: str) -> str:
        """Add trailing slashes to a path."""
        if ':' not in value:  # Not a Windows path
            if not value.startswith("/"):
                value = "/" + value
            if not value.endswith("/"):
                value = value + "/"
        return value
    
    @staticmethod
    def _remove_all_slashes(value_list: List[str]) -> List[str]:
        """Remove all slashes from a list of paths."""
        return [value.strip('/\\') for value in value_list]
    
    def get_cache_files(self) -> Tuple[Path, Path, Path]:
        """Get cache file paths."""
        script_folder = Path(self.paths.script_folder)
        return (
            script_folder / "plexcache_watchlist_cache.json",
            script_folder / "plexcache_watched_cache.json",
            script_folder / "plexcache_mover_files_to_exclude.txt"
        ) 