import os
import sys
import logging
from pathlib import Path
from video_analysis import analyze_videos_sync
from video_concatenator import concatenate_highlights
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def delete_highlights_file(highlights_json_path: str = "highlights.json") -> None:
    """
    Delete the highlights.json file.
    
    Args:
        highlights_json_path: Path to the JSON file containing highlight information
    """
    if os.path.exists(highlights_json_path):
        os.remove(highlights_json_path)

def process_recent_clips(directory_path: str, output_file: str = "highlights.json", batch_size: int = 5) -> None:
    """
    Process the 25 most recently created video clips in the specified directory.
    
    Args:
        directory_path: Path to the directory containing video clips
        output_file: Path to the JSON file where highlights will be saved
        batch_size: Number of videos to process concurrently (default: 5)
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
        
        # Get the configured number of clips
        config = Config()
        recent_files = video_files[:config.max_clips]
        logger.info(f"Found {len(recent_files)} recent video files to process")

        # Convert Path objects to strings
        video_paths = [str(f) for f in recent_files]
        
        # Process videos in batches
        results = analyze_videos_sync(video_paths, output_file, batch_size)
        
        # Log summary of processing
        successful = sum(1 for _, highlights in results if highlights)
        logger.info(f"Successfully processed {successful} out of {len(recent_files)} videos")

        # After analysis is complete and files are deleted from API, generate the final video
        generate_highlight_video(output_file)

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
