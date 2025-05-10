import json
import os
import logging
from typing import List, Set
from pathlib import Path

# Get module-specific logger
logger = logging.getLogger(__name__)

class ClipTracker:
    def __init__(self, allow_clip_reuse: bool = False):
        self.allow_clip_reuse = allow_clip_reuse
        self.used_clips_file = "used_clips.json"
        self.used_clips: Set[str] = set()
        self._load_used_clips()

    def _load_used_clips(self) -> None:
        """Load the list of previously used clips from JSON file."""
        if os.path.exists(self.used_clips_file):
            try:
                with open(self.used_clips_file, 'r') as f:
                    self.used_clips = set(json.load(f))
                logger.info(f"Loaded {len(self.used_clips)} previously used clips")
            except json.JSONDecodeError:
                logger.error("Error reading used clips file, starting fresh")
                self.used_clips = set()
        else:
            logger.info("No previous clips file found, starting fresh")

    def save_used_clips(self) -> None:
        """Save the current list of used clips to JSON file."""
        with open(self.used_clips_file, 'w') as f:
            json.dump(list(self.used_clips), f, indent=4)
        logger.info(f"Saved {len(self.used_clips)} used clips to {self.used_clips_file}")

    def filter_unused_clips(self, clip_paths: List[str]) -> List[str]:
        """Filter out previously used clips unless reuse is allowed."""
        if self.allow_clip_reuse:
            logger.info("Clip reuse is allowed, using all clips")
            return clip_paths

        unused_clips = [
            clip for clip in clip_paths 
            if Path(clip).name not in self.used_clips
        ]
        
        filtered_count = len(clip_paths) - len(unused_clips)
        if filtered_count > 0:
            logger.info(f"Filtered out {filtered_count} previously used clips")
        
        return unused_clips

    def mark_clips_as_used(self, clip_paths: List[str]) -> None:
        """Mark the provided clips as used and save to file."""
        new_clips = {Path(clip).name for clip in clip_paths}
        self.used_clips.update(new_clips)
        self.save_used_clips()
        logger.info(f"Marked {len(new_clips)} new clips as used") 