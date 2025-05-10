import os
import sys
from pathlib import Path
from video_analysis import analyze_videos_sync
from video_concatenator import concatenate_highlights
from config import Config
from clip_tracker import ClipTracker
from logging_config import setup_logging
import logging

# Get module-specific logger
logger = logging.getLogger(__name__)

# Initialize logging at startup
setup_logging()

def delete_highlights_file(highlights_json_path: str = "highlights.json") -> None:
    """
    Delete the highlights.json file.

    Args:
        highlights_json_path: Path to the JSON file containing highlight information
    """
    if os.path.exists(highlights_json_path):
        os.remove(highlights_json_path)

def process_recent_clips(directory_path: str, output_file: str = "highlights.json", batch_size: int = 10) -> None:
    """
    Process video clips in the specified directory, sorted by creation date and filtered for unused clips.

    Args:
        directory_path: Path to the directory containing video clips
        output_file: Path to the JSON file where highlights will be saved
        batch_size: Number of videos to process concurrently (default: 10)
    """
    try:
        # Convert to Path object for easier handling
        dir_path = Path(directory_path)
        if not dir_path.exists() or not dir_path.is_dir():
            raise ValueError(f"Invalid directory path: {directory_path}")

        # Get all video files (common video extensions)
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.wmv')
        video_files = []

        for ext in video_extensions:
            video_files.extend(dir_path.glob(f"*{ext}"))

        if not video_files:
            logger.warning(f"No video files found in {directory_path}")
            return

        # Sort files by creation time (newest first)
        video_files.sort(key=lambda x: x.stat().st_ctime, reverse=True)

        # Convert Path objects to strings
        video_paths = [str(f) for f in video_files]

        # Filter out previously used clips
        clip_tracker = ClipTracker(allow_clip_reuse=False)  # Always set to False as per requirement
        video_paths = clip_tracker.filter_unused_clips(video_paths)

        # Get the configured number of clips after filtering
        config = Config()
        
        # Apply skip_videos configuration
        if config.skip_videos > 0:
            if config.skip_videos >= len(video_paths):
                logger.warning(f"Skipping all {len(video_paths)} videos as skip_videos ({config.skip_videos}) >= available videos")
                return
            video_paths = video_paths[config.skip_videos:]
            logger.info(f"Skipped {config.skip_videos} videos as per configuration")

        if len(video_paths) > config.max_clips:
            video_paths = video_paths[:config.max_clips]
            logger.info(f"Using {config.max_clips} most recent unused clips")
        else:
            logger.info(f"Using all {len(video_paths)} available unused clips")

        if not video_paths:
            logger.warning("No unused clips available for processing")
            return

        # Process videos in batches
        results = analyze_videos_sync(video_paths, output_file, batch_size)

        # Log summary of processing
        successful = sum(1 for _, highlights in results if highlights)
        logger.info(f"Successfully processed {successful} out of {len(video_paths)} videos")

        # After analysis is complete and files are deleted from API, generate the final video
        if successful > 0:
            generate_highlight_video(output_file)
            # Mark the successfully processed clips as used
            successful_clips = [path for path, highlights in results if highlights]
            clip_tracker.mark_clips_as_used(successful_clips)

    except Exception as e:
        logger.error(f"Error processing clips: {str(e)}")
        raise

def generate_highlight_video(highlights_json_path: str = "highlights.json") -> None:
    """
    Generate the final highlight video after analysis is complete.

    Args:
        highlights_json_path: Path to the JSON file containing highlight information
    """
    try:
        if not os.path.exists(highlights_json_path):
            logger.error(f"Highlights file not found: {highlights_json_path}")
            return

        logger.info("Starting video concatenation process...")
        concatenate_highlights(highlights_json_path)
        logger.info("Video concatenation completed successfully")

    except Exception as e:
        logger.error(f"Error generating highlight video: {str(e)}")
        raise

if __name__ == "__main__":
    delete_highlights_file()

    if len(sys.argv) != 2:
        print("Usage: python main.py <directory_path>")
        sys.exit(1)
    
    process_recent_clips(sys.argv[1])
