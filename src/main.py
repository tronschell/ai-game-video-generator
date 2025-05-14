import os
import sys
from pathlib import Path
from video_analysis import analyze_videos_sync
from video_concatenator import concatenate_highlights
from config import Config
from clip_tracker import ClipTracker
from analysis_tracker import AnalysisTracker
from logging_config import setup_logging
import logging
import json
from typing import Dict, List, Any

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

        # Sort files by most recent timestamp (combining creation and modification times)
        # This ensures we get the absolute newest files regardless of whether
        # creation or modification time is more recent
        video_files.sort(key=lambda x: max(x.stat().st_ctime, x.stat().st_mtime), reverse=True)

        # Convert Path objects to strings
        video_paths = [str(f) for f in video_files]

        # Get config settings
        config = Config()
        allow_reuse = config.allow_clip_reuse
        logger.info(f"Clip reuse setting: allow_clip_reuse = {allow_reuse}")

        # Filter out previously used clips based on configuration
        clip_tracker = ClipTracker(allow_clip_reuse=allow_reuse)
        video_paths = clip_tracker.filter_unused_clips(video_paths)
        
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
            
        # Initialize analysis tracker to avoid reanalyzing clips
        analysis_tracker = AnalysisTracker()
        
        # Get already analyzed clips and their results
        already_analyzed_paths = []
        previously_analyzed_results = []
        
        for path in video_paths[:]:
            if analysis_tracker.is_clip_analyzed(path):
                already_analyzed_paths.append(path)
                previously_analyzed_results.append((path, analysis_tracker.get_clip_results(path)))
                video_paths.remove(path)
                
        if already_analyzed_paths:
            logger.info(f"Found {len(already_analyzed_paths)} previously analyzed clips, skipping reanalysis")
            
        # Process videos that haven't been analyzed yet
        results = []
        if video_paths:
            logger.info(f"Analyzing {len(video_paths)} new clips")
            results = analyze_videos_sync(video_paths, output_file, batch_size)
            
            # Mark newly processed clips as analyzed
            for path, highlights in results:
                if highlights:  # Only mark as analyzed if we got results
                    analysis_tracker.mark_clip_as_analyzed(path, highlights)
        
        # Combine new results with previously analyzed results
        combined_results = results + previously_analyzed_results
        
        # Check if we have any highlights to process
        if not combined_results:
            logger.warning("No video analysis results available")
            return
            
        # Write combined results to output file
        if previously_analyzed_results:
            write_combined_highlights(combined_results, output_file)

        # Log summary of processing
        successful = sum(1 for _, highlights in combined_results if highlights)
        logger.info(f"Successfully processed {successful} out of {len(combined_results)} videos (including {len(previously_analyzed_results)} previously analyzed)")

        # After analysis is complete, generate the final video
        if successful > 0:
            generate_highlight_video(output_file)
            # Mark the successfully processed clips as used
            successful_clips = [path for path, highlights in results if highlights]
            clip_tracker.mark_clips_as_used(successful_clips)

    except Exception as e:
        logger.error(f"Error processing clips: {str(e)}")
        raise

def write_combined_highlights(results: List, output_file: str) -> None:
    """
    Write combined highlights (new and previously analyzed) to the output file.
    
    Args:
        results: List of tuples containing (video_path, highlights)
        output_file: Path to the JSON file where highlights will be saved
    """
    # Combine all highlights with video path information
    all_highlights = []
    for video_path, highlights in results:
        if not highlights:
            continue
            
        # Handle both list and dict formats
        if isinstance(highlights, list):
            for highlight in highlights:
                if not isinstance(highlight, dict):
                    logger.warning(f"Skipping invalid highlight format: {type(highlight)}")
                    continue
                    
                # Add the video path to each highlight
                highlight_with_source = highlight.copy()
                if 'video_path' not in highlight_with_source and 'source_video' not in highlight_with_source:
                    highlight_with_source["video_path"] = video_path
                all_highlights.append(highlight_with_source)
        elif isinstance(highlights, dict):
            # Add the entire dict as a single highlight with video path
            highlight_with_source = highlights.copy()
            if 'video_path' not in highlight_with_source and 'source_video' not in highlight_with_source:
                highlight_with_source["video_path"] = video_path
            all_highlights.append(highlight_with_source)
        else:
            logger.warning(f"Unexpected highlights format for {video_path}: {type(highlights)}")
    
    # Write to output file
    if all_highlights:
        with open(output_file, 'w') as f:
            json.dump(all_highlights, f, indent=4)
        logger.info(f"Wrote {len(all_highlights)} highlights to {output_file}")
    else:
        logger.warning(f"No valid highlights to write to {output_file}")
        # Write an empty list to ensure the file exists and is valid JSON
        with open(output_file, 'w') as f:
            json.dump([], f)

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
