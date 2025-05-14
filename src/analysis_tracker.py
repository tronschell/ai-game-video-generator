import json
import os
import logging
from typing import List, Set, Dict, Any
from pathlib import Path
import hashlib
from config import Config

# Get module-specific logger
logger = logging.getLogger(__name__)

class AnalysisTracker:
    def __init__(self):
        self.analyzed_clips_file = "analyzed_clips.json"
        self.analyzed_data: Dict[str, Dict[str, Any]] = {}
        self._load_analyzed_clips()

    def _load_analyzed_clips(self) -> None:
        """Load the list of previously analyzed clips and their results from JSON file."""
        if os.path.exists(self.analyzed_clips_file):
            try:
                with open(self.analyzed_clips_file, 'r') as f:
                    self.analyzed_data = json.load(f)
                logger.info(f"Loaded {len(self.analyzed_data)} previously analyzed clips")
            except json.JSONDecodeError:
                logger.error("Error reading analyzed clips file, starting fresh")
                self.analyzed_data = {}
        else:
            logger.info("No previous analyzed clips file found, starting fresh")

    def save_analyzed_clips(self) -> None:
        """Save the current analyzed clips data to JSON file."""
        with open(self.analyzed_clips_file, 'w') as f:
            json.dump(self.analyzed_data, f, indent=4)
        logger.info(f"Saved {len(self.analyzed_data)} analyzed clips to {self.analyzed_clips_file}")

    def get_file_hash(self, file_path: str) -> str:
        """Generate a hash for the file based on path, size, and modification time."""
        file_stat = os.stat(file_path)
        # Create a unique identifier using file path and metadata
        hash_input = f"{file_path}:{file_stat.st_size}:{file_stat.st_mtime}"
        return hashlib.md5(hash_input.encode()).hexdigest()

    def is_clip_analyzed(self, clip_path: str) -> bool:
        """Check if a clip has been analyzed before."""
        try:
            file_hash = self.get_file_hash(clip_path)
            return file_hash in self.analyzed_data
        except Exception as e:
            logger.warning(f"Error checking if clip was analyzed: {str(e)}")
            return False

    def get_clip_results(self, clip_path: str) -> List[Dict[str, Any]]:
        """Get the analysis results for a previously analyzed clip."""
        try:
            file_hash = self.get_file_hash(clip_path)
            if file_hash in self.analyzed_data:
                return self.analyzed_data[file_hash].get("highlights", [])
            return []
        except Exception as e:
            logger.warning(f"Error retrieving clip results: {str(e)}")
            return []

    def filter_unanalyzed_clips(self, clip_paths: List[str]) -> List[str]:
        """Filter out previously analyzed clips."""
        unanalyzed_clips = []
        analyzed_clips = []
        
        for clip in clip_paths:
            if not self.is_clip_analyzed(clip):
                unanalyzed_clips.append(clip)
            else:
                analyzed_clips.append(clip)
        
        if analyzed_clips:
            logger.info(f"Skipping {len(analyzed_clips)} previously analyzed clips")
            
        return unanalyzed_clips

    def mark_clip_as_analyzed(self, clip_path: str, highlights: List[Dict[str, Any]]) -> None:
        """Mark the provided clip as analyzed and save its results."""
        try:
            # Get the model name from config
            config = Config()
            model_name = config.model_name
            
            file_hash = self.get_file_hash(clip_path)
            self.analyzed_data[file_hash] = {
                "path": clip_path,
                "filename": Path(clip_path).name,
                "model_name": model_name,
                "highlights": highlights
            }
            self.save_analyzed_clips()
            logger.info(f"Marked clip {Path(clip_path).name} as analyzed using model {model_name}")
        except Exception as e:
            logger.warning(f"Error marking clip as analyzed: {str(e)}") 