import json
import os
import logging
from typing import Dict, Any, Literal

logger = logging.getLogger(__name__)

# Define valid game types for typing
GameType = Literal["cs2", "overwatch2", "the_finals", "league_of_legends", "custom"]

class Config:
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
        try:
            with open(config_path, 'r') as f:
                self._config = json.load(f)
            logger.info("Successfully loaded configuration from config.json")
        except FileNotFoundError:
            logger.warning("config.json not found, using default values")
            self._config = {
                "batch_size": 25,
                "model_name": "gemini-2.5-flash-preview-04-17",
                "max_retries": 10,
                "retry_delay_seconds": 2,
                "min_highlight_duration_seconds": 10,
                "username": "i have no enemies",
                "max_clips": 25,
                "allow_clip_reuse": False,
                "temperature": 1.0,
                "use_caching": False,
                "cache_ttl_seconds": 3600,
                "skip_videos": 0,
                "use_low_resolution": False,
                "clip_order": "oldest_first",
                "game_type": "cs2"
            }
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing config.json: {e}")
            raise

    @property
    def batch_size(self) -> int:
        return self._config.get("batch_size", 25)

    @property
    def model_name(self) -> str:
        return self._config.get("model_name", "gemini-2.5-flash-preview-04-17")

    @property
    def max_retries(self) -> int:
        return self._config.get("max_retries", 10)

    @property
    def retry_delay_seconds(self) -> int:
        return self._config.get("retry_delay_seconds", 2)

    @property
    def min_highlight_duration_seconds(self) -> int:
        return self._config.get("min_highlight_duration_seconds", 10)

    @property
    def username(self) -> str:
        return self._config.get("username", "i have no enemies")

    @property
    def max_clips(self) -> int:
        return self._config.get("max_clips", 25)

    @property
    def allow_clip_reuse(self) -> bool:
        return self._config.get("allow_clip_reuse", False) 
        
    @property
    def temperature(self) -> float:
        return self._config.get("temperature", 1.0)

    @property
    def use_caching(self) -> bool:
        return self._config.get("use_caching", True)

    @property
    def cache_ttl_seconds(self) -> int:
        return self._config.get("cache_ttl_seconds", 3600)

    @property
    def skip_videos(self) -> int:
        return self._config.get("skip_videos", 0)

    @property
    def use_low_resolution(self) -> bool:
        return self._config.get("use_low_resolution", False)
    
    @property
    def clip_order(self) -> str:
        return self._config.get("clip_order", "oldest_first")
    
    @property
    def game_type(self) -> GameType:
        """
        Get the game type for prompt selection.
        
        Returns:
            The game type as a string (cs2, overwatch2, the_finals, league_of_legends, custom)
        """
        return self._config.get("game_type", "cs2")