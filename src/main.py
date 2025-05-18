import os
import sys
import random
import json
import subprocess
from pathlib import Path
from video_analysis import analyze_videos_sync
from video_concatenator import concatenate_highlights
from utils.config import Config
from utils.clip_tracker import ClipTracker
from utils.analysis_tracker import AnalysisTracker
from utils.logging_config import setup_logging
import logging
from typing import Dict, List, Any, Tuple
import argparse

# Get module-specific logger
logger = logging.getLogger(__name__)

# Initialize logging at startup
setup_logging()

def get_video_duration(video_path: str) -> float:
    """
    Get the duration of a video file in seconds using ffprobe.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Duration of the video in seconds or 0 if the video cannot be read
    """
    try:
        # Run ffprobe command to get duration
        result = subprocess.run([
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            video_path
        ], capture_output=True, text=True, check=True)
        
        # Parse the JSON output
        output = json.loads(result.stdout)
        duration = float(output['format']['duration'])
        return duration
    except (subprocess.SubprocessError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"Error getting video duration for {video_path}: {str(e)}")
        return 0

def filter_videos_by_duration(video_paths: List[str], max_duration_seconds: int) -> List[str]:
    """
    Filter videos that are longer than the specified duration.
    
    Args:
        video_paths: List of paths to video files
        max_duration_seconds: Maximum duration in seconds
        
    Returns:
        List of video paths that are under the specified duration
    """
    filtered_paths = []
    for path in video_paths:
        duration = get_video_duration(path)
        if duration <= max_duration_seconds:
            filtered_paths.append(path)
        else:
            logger.warning(f"Skipping video longer than {max_duration_seconds} seconds: {path} (duration: {duration:.1f}s)")
    
    return filtered_paths

def delete_highlights_file(highlights_json_path: str = "exported_metadata/highlights.json") -> None:
    """
    Delete the highlights.json file.

    Args:
        highlights_json_path: Path to the JSON file containing highlight information
    """
    if os.path.exists(highlights_json_path):
        os.remove(highlights_json_path)

def process_recent_clips(directory_path: str, output_file: str = "exported_metadata/highlights.json", batch_size: int = 10) -> None:
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

        # Get config settings
        config = Config()

        # Sort files based on clip_order configuration
        if config.clip_order == "random":
            # Shuffle the video files randomly
            random.shuffle(video_files)
            logger.info(f"Videos shuffled randomly as per clip_order configuration")
            
            # Convert Path objects to strings
            all_video_paths = [str(f) for f in video_files]
            
            # Process videos one by one until we have enough under 5 minutes
            video_paths = []
            for path in all_video_paths:
                # First check if we have enough videos
                if len(video_paths) >= config.max_clips:
                    break
                    
                # Check duration only for videos we might use
                duration = get_video_duration(path)
                if duration <= 300:  # 5 minutes = 300 seconds
                    video_paths.append(path)
                    logger.debug(f"Added video under 5 minutes: {os.path.basename(path)} ({duration:.1f}s)")
                else:
                    logger.debug(f"Skipping video over 5 minutes: {os.path.basename(path)} ({duration:.1f}s)")
            
            if not video_paths:
                logger.warning("No videos under 5 minutes found for random mode")
                return
                
            logger.info(f"Selected {len(video_paths)} videos under 5 minutes for random mode")
        else:
            # Sort files by timestamp
            reverse = config.clip_order != "oldest_first"  # Reverse if not oldest_first
            video_files.sort(key=lambda x: max(x.stat().st_ctime, x.stat().st_mtime), reverse=reverse)
            sort_direction = "newest first" if reverse else "oldest first"
            logger.info(f"Videos sorted by timestamp ({sort_direction}) as per clip_order configuration")
            
            # Convert Path objects to strings
            video_paths = [str(f) for f in video_files]

        # Get clip reuse setting
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
            generate_highlight_video(output_file, generate_subtitles=config.generate_subtitles)
            # Mark the successfully processed clips as used
            successful_clips = [path for path, highlights in results if highlights]
            clip_tracker.mark_clips_as_used(successful_clips)

    except Exception as e:
        logger.error(f"Error processing clips: {str(e)}")
        raise

def write_combined_highlights(results: List[Tuple[str, List[Dict[str, Any]]]], output_file: str = "exported_metadata/highlights.json") -> None:
    """
    Write combined highlights from all processed videos to a single JSON file.
    
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

def generate_highlight_video(highlights_json_path: str = "exported_metadata/highlights.json", generate_subtitles: bool = False) -> None:
    """
    Generate a highlight video from a JSON file containing highlight information.

    Args:
        highlights_json_path: Path to the JSON file containing highlight information
        generate_subtitles: Whether to generate subtitles for the highlights
    """
    try:
        if not os.path.exists(highlights_json_path):
            logger.error(f"Highlights file not found: {highlights_json_path}")
            return

        logger.info("Starting video concatenation process...")
        concatenate_highlights(highlights_json_path, generate_subtitles=generate_subtitles)
        logger.info("Video concatenation completed successfully")

    except Exception as e:
        logger.error(f"Error generating highlight video: {str(e)}")
        raise

if __name__ == "__main__":
    delete_highlights_file()

    parser = argparse.ArgumentParser(description="Process video clips to generate highlights")
    parser.add_argument("directory_path", help="Path to the directory containing video clips")
    parser.add_argument("--subtitles", action="store_true", help="Generate and add subtitles to the video")
    
    args = parser.parse_args()
    
    # Update config to use subtitle generation from command line
    if args.subtitles:
        config = Config()
        config._config["generate_subtitles"] = True
        logger.info("Subtitle generation enabled via command line flag")
    
    process_recent_clips(args.directory_path)
