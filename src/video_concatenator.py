import json
import os
import logging
import shutil
import subprocess
import tempfile
from typing import List, Dict, Tuple, Optional
import time
from datetime import datetime
from pathlib import Path
from utils.config import Config
import concurrent.futures
from functools import partial, lru_cache
from subtitle_generator import SubtitleGenerator, generate_subtitles_for_video, cleanup_temp_files

# Get module-specific logger
logger = logging.getLogger(__name__)

@lru_cache(maxsize=None)
def is_nvenc_available() -> bool:
    """Check if ffmpeg has h264_nvenc encoder."""
    try:
        result = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True, check=False)
        return 'h264_nvenc' in result.stdout
    except FileNotFoundError:
        logger.error("ffmpeg not found. NVENC check cannot be performed.")
        return False
    except Exception as e:
        logger.error(f"Error checking for NVENC availability: {e}")
        return False

def get_video_creation_time(video_path: str) -> datetime:
    """
    Get video creation time from metadata using ffprobe
    
    Args:
        video_path: Path to the video file
        
    Returns:
        datetime object representing the video's creation time
    """
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', 
            '-show_entries', 'format_tags=creation_time',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            '-i', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout.strip():
            # Parse ISO 8601 format (2025-05-13T01:00:46.000000Z)
            timestamp_str = result.stdout.strip()
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        # Try file modification time as fallback
        file_mtime = os.path.getmtime(video_path)
        return datetime.fromtimestamp(file_mtime)
    except Exception as e:
        logger.error(f"Error getting creation time from video metadata: {str(e)}")
        return None

def parse_video_timestamp(filename: str) -> datetime:
    """
    Get timestamp of video using metadata first, then filename parsing as fallback
    
    Args:
        filename: The video filename or path
        
    Returns:
        datetime object representing the video's timestamp (always timezone-naive)
    """
    try:
        # Try to get creation time from metadata
        creation_time = get_video_creation_time(filename)
        if creation_time:
            # Convert timezone-aware datetime to naive to ensure consistency
            if creation_time.tzinfo is not None:
                creation_time = creation_time.replace(tzinfo=None)
            return creation_time
            
        # Fallback to filename parsing
        logger.info(f"Using filename parsing fallback for {os.path.basename(filename)}")
        basename = os.path.basename(filename)
        
        # Try Counter-strike 2 format
        if "Counter-strike 2" in basename:
            date_time_str = basename.split('Counter-strike 2 ')[1].split('.DVR')[0]
            date_part, time_part = date_time_str.split(' - ')
            
            # Parse date components
            year, month, day = map(int, date_part.split('.'))
            
            # Parse time components (ignoring milliseconds)
            hour, minute, second = map(int, time_part.split('.')[:3])
            
            return datetime(year, month, day, hour, minute, second)
    except Exception as e:
        logger.error(f"Error parsing timestamp from file {os.path.basename(filename)}: {str(e)}")
    
    # Return epoch time as fallback
    logger.warning(f"Using epoch time fallback for {os.path.basename(filename)}")
    return datetime(1970, 1, 1)

def merge_overlapping_highlights(highlights: List[Dict]) -> List[Dict]:
    """
    Merge highlights that overlap or are too close to each other from the same video.
    
    Args:
        highlights: List of highlight dictionaries
        
    Returns:
        List of merged highlights
    """
    if not highlights:
        return []

    # Ensure all highlights are dictionaries
    valid_highlights = []
    for h in highlights:
        if isinstance(h, dict):
            valid_highlights.append(h)
        else:
            logger.warning(f"Skipping invalid highlight format: {type(h)}")
    
    if len(valid_highlights) < len(highlights):
        logger.warning(f"Filtered out {len(highlights) - len(valid_highlights)} invalid highlights")
        
    highlights = valid_highlights

    # Group highlights by source video
    video_groups = {}
    for highlight in highlights:
        # Use dictionary access with fallback
        source = highlight.get('source_video', highlight.get('video_path', None))
        if not source:
            logger.warning(f"Highlight missing source video information: {highlight}")
            continue
        if source not in video_groups:
            video_groups[source] = []
        video_groups[source].append(highlight)

    merged_highlights = []
    for source, video_highlights in video_groups.items():
        # Sort highlights by start time
        video_highlights.sort(key=lambda x: x['timestamp_start_seconds'])
        
        i = 0
        while i < len(video_highlights):
            current = video_highlights[i]
            merged = current.copy()
            j = i + 1
            
            while j < len(video_highlights):
                next_highlight = video_highlights[j]
                
                # Check if highlights overlap or are very close (within 3 seconds)
                if (merged['timestamp_end_seconds'] + 3 >= next_highlight['timestamp_start_seconds'] or
                    abs(merged['timestamp_start_seconds'] - next_highlight['timestamp_start_seconds']) <= 3):
                    # Merge the highlights
                    merged['timestamp_start_seconds'] = min(merged['timestamp_start_seconds'], 
                                                          next_highlight['timestamp_start_seconds'])
                    merged['timestamp_end_seconds'] = max(merged['timestamp_end_seconds'], 
                                                        next_highlight['timestamp_end_seconds'])
                    merged['clip_description'] = f"{merged['clip_description']} + {next_highlight['clip_description']}"
                    j += 1
                else:
                    break
            
            merged_highlights.append(merged)
            i = j

    return merged_highlights

def process_segment(highlight: Dict, idx: int, total: int, temp_dir: str, generate_subtitles: bool = False) -> Tuple[str, bool, float, Optional[str]]:
    """
    Process a single video segment in parallel by re-encoding.
    
    Args:
        highlight: Highlight dict containing segment info
        idx: Segment index
        total: Total number of segments
        temp_dir: Directory to save temporary files
        generate_subtitles: Whether to generate subtitles for this segment
    
    Returns:
        Tuple of (segment_file_path, success, duration, subtitle_path)
    """
    source_video = highlight['source_video']
    start_time = highlight['timestamp_start_seconds']
    # Using the +2 second buffer as per user preference
    end_time = highlight['timestamp_end_seconds'] + 2 
    duration = end_time - start_time
    
    segment_file = os.path.join(temp_dir, f'segment_{idx:03d}.mp4')

    logger.info(f"Processing segment {idx + 1}/{total} from {os.path.basename(source_video)} by re-encoding.")

    video_filters = "setpts=PTS-STARTPTS,fps=60" # Corrected from fps=fps=30
    audio_filters = "asetpts=PTS-STARTPTS"

    ffmpeg_cmd_base = [
        'ffmpeg', '-y', # Overwrite output files without asking
        '-i', source_video,
        '-ss', str(start_time),
        '-t', str(duration),
        '-vf', video_filters,
        '-af', audio_filters,
        '-c:a', 'aac', '-b:a', '192k', # Always encode audio to AAC
        '-vsync', 'cfr', # Constant Frame Rate
        '-avoid_negative_ts', 'make_zero', 
        '-movflags', '+faststart',
        '-map', '0:v:0', '-map', '0:a:0?'
    ]

    use_nvenc = is_nvenc_available()
    if use_nvenc:
        logger.info(f"Using h264_nvenc for segment {idx + 1}")
        ffmpeg_cmd_video = ['-c:v', 'h264_nvenc', '-preset', 'p5', '-tune', 'hq', '-rc', 'vbr', '-cq', '23', '-b:v', '0']
    else:
        logger.info(f"Using libx264 for segment {idx + 1}")
        ffmpeg_cmd_video = ['-c:v', 'libx264', '-crf', '22', '-preset', 'medium']

    cut_cmd_list = ffmpeg_cmd_base + ffmpeg_cmd_video + [segment_file]
    
    logger.debug(f"Re-encode command for segment {idx + 1}: {' '.join(cut_cmd_list)}")
    result = subprocess.run(cut_cmd_list, capture_output=True, text=True, check=False)
    
    if result.returncode != 0:
        logger.warning(f"ffmpeg re-encode failed for segment {idx+1}. Return code: {result.returncode}")
        logger.error(f"FFmpeg stderr: {result.stderr}")
        logger.error(f"FFmpeg stdout: {result.stdout}")
        # No retry logic here as per "as little code as possible" but can be added if necessary
        # For now, if initial fails, we consider the segment failed.

    # Verify segment duration
    try:
        duration_cmd = [
            'ffprobe', '-v', 'error', 
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            segment_file
        ]
        duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, check=False)
        actual_duration_str = duration_result.stdout.strip()
        
        if not actual_duration_str: # Handle empty output from ffprobe
             raise ValueError("ffprobe returned empty duration.")
        actual_duration = float(actual_duration_str)
        
        # Check if file exists and has valid size/duration
        # We expect the duration to be close to the requested 'duration' variable
        # Allowing a slightly larger tolerance due to re-encoding and filter effects.
        if result.returncode == 0 and os.path.exists(segment_file) and os.path.getsize(segment_file) > 0 and abs(actual_duration - duration) < 1.0:
            logger.info(f"Segment {idx+1} re-encoded successfully. Verified duration: {actual_duration:.2f}s (requested: {duration:.2f}s)")
            
            # Generate subtitles if requested
            subtitle_path = None
            if generate_subtitles and os.path.exists(segment_file):
                try:
                    logger.info(f"Generating subtitles for segment {idx+1}")
                    subtitle_path = generate_subtitles_for_video(segment_file, is_short=False)
                    logger.info(f"Subtitles generated for segment {idx+1}: {subtitle_path}")
                except Exception as e:
                    logger.error(f"Failed to generate subtitles for segment {idx+1}: {str(e)}")
            
            return segment_file, True, actual_duration, subtitle_path
        else:
            if result.returncode == 0: # ffmpeg succeeded but validation failed
                 logger.warning(f"Segment {idx+1} validation failed post re-encode. Actual duration {actual_duration:.2f}s vs requested {duration:.2f}s.")
            logger.warning(f"Segment {idx+1} failed processing or validation.")
            return segment_file, False, 0, None
            
    except Exception as e:
        logger.warning(f"Could not verify segment {idx+1} duration or segment failed: {str(e)}")
        if result.stderr: # Log ffmpeg error if verification failed
            logger.error(f"FFmpeg stderr (during failed verification): {result.stderr}")
        return segment_file, False, 0, None

def concatenate_highlights(highlights_json_path: str = 'highlights.json', num_workers: int = 4, generate_subtitles: bool = False) -> None:
    """
    Concatenates video clips specified in highlights.json into a single output video
    using a two-step process to ensure clean concatenation.
    
    Args:
        highlights_json_path: Path to the JSON file containing highlights
        num_workers: Number of worker processes for parallel processing
        generate_subtitles: Whether to generate subtitles for the segments
    """
    # Create necessary directories
    export_dir = 'exported_videos'
    temp_dir = 'temp_segments'
    os.makedirs(export_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    # Track temporary files for cleanup
    temp_files_to_clean = []

    try:
        # Read the highlights.json file
        with open(highlights_json_path, 'r') as f:
            data = json.load(f)
        
        # Handle different JSON formats
        highlights = []
        if isinstance(data, list):
            # Format: [highlight1, highlight2, ...]
            highlights = data
            logger.info("Processing list format highlights")
        elif isinstance(data, dict) and 'highlights' in data:
            # Format: {'highlights': [highlight1, highlight2, ...]}
            highlights = data['highlights']
            logger.info("Processing dictionary format highlights with 'highlights' key")
        elif isinstance(data, dict):
            # Format: {key1: highlight1, key2: highlight2, ...}
            highlights = list(data.values())
            logger.info("Processing dictionary format highlights")
        else:
            logger.error(f"Unexpected JSON format in {highlights_json_path}")
            return

        if not highlights:
            logger.warning("No highlights found in the JSON file")
            return
            
        # Add source_video key if using new format with video_path
        for highlight in highlights:
            if isinstance(highlight, dict):
                if 'source_video' not in highlight and 'video_path' in highlight:
                    highlight['source_video'] = highlight['video_path']

        # Merge overlapping highlights
        highlights = merge_overlapping_highlights(highlights)
        
        # Validate that we have highlights after merging
        if not highlights:
            logger.warning("No valid highlights found after processing")
            return
        
        # Get ordering preference from config
        config = Config()
        clip_order = config.clip_order
        logger.info(f"Ordering clips by: {clip_order}")
        
        # Sort highlights based on video timestamps with respect to ordering preference
        if clip_order == "oldest_first":
            highlights.sort(key=lambda x: parse_video_timestamp(x['source_video']))
            logger.info("Clips will be ordered from oldest to newest")
        elif clip_order == "newest_first":
            highlights.sort(key=lambda x: parse_video_timestamp(x['source_video']), reverse=True)
            logger.info("Clips will be ordered from newest to oldest")
        else:
            logger.warning(f"Unknown clip_order value: {clip_order}, defaulting to oldest_first")
            highlights.sort(key=lambda x: parse_video_timestamp(x['source_video']))
        
        # Step 1: Process segments concurrently using a worker pool
        verified_segments = []
        segment_subtitles = {}
        total_duration = 0
        total_highlights = len(highlights)
        
        logger.info(f"Processing {total_highlights} segments using {num_workers} workers")
        
        # Create a partial function with fixed parameters
        process_fn = partial(process_segment, total=total_highlights, temp_dir=temp_dir, generate_subtitles=generate_subtitles)
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
            # Submit all segment processing tasks
            futures = {executor.submit(process_fn, highlight, idx): idx 
                      for idx, highlight in enumerate(highlights)}
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                try:
                    segment_file, success, duration, subtitle_path = future.result()
                    if success:
                        verified_segments.append(segment_file)
                        total_duration += duration
                        if subtitle_path:
                            segment_subtitles[segment_file] = subtitle_path
                        logger.info(f"Segment {idx+1}/{total_highlights} completed successfully")
                    else:
                        logger.warning(f"Segment {idx+1}/{total_highlights} processing failed")
                except Exception as e:
                    logger.error(f"Error processing segment {idx+1}: {str(e)}")
        
        logger.info(f"Total verified segments: {len(verified_segments)}/{total_highlights}")
        logger.info(f"Expected total duration: {total_duration:.2f} seconds")
        
        # Create a fresh concatenation file list with only verified segments
        concat_list_path = os.path.join(temp_dir, 'concat_list.txt')
        with open(concat_list_path, 'w') as f:
            for segment_file_path in verified_segments:
                f.write(f"file '{os.path.abspath(segment_file_path)}'\n")

        # Step 3: Use concat demuxer for stream copying (no re-encoding)
        output_file = os.path.join(export_dir, f'highlights_{int(time.time())}.mp4')
        
        # Process each segment with subtitles before concatenation if needed
        if generate_subtitles and segment_subtitles:
            logger.info("Preparing segments with subtitles")
            
            # Create temporary directory for subtitled segments
            subtitled_temp_dir = os.path.join(temp_dir, 'subtitled')
            os.makedirs(subtitled_temp_dir, exist_ok=True)
            
            subtitled_segments = []
            subtitle_generator = SubtitleGenerator()
            
            for idx, segment_file in enumerate(verified_segments):
                subtitled_file = os.path.join(subtitled_temp_dir, f'subtitled_segment_{idx:03d}.mp4')
                
                if segment_file in segment_subtitles:
                    srt_path = segment_subtitles[segment_file]
                    
                    # Create an intermediate file without subtitles
                    intermediate_file = os.path.join(subtitled_temp_dir, f'intermediate_segment_{idx:03d}.mp4')
                    
                    # Copy the segment first
                    try:
                        shutil.copy(segment_file, intermediate_file)
                        
                        # Convert to absolute POSIX path for consistency
                        posix_path = Path(srt_path).resolve().as_posix()
                        # Escape the colon for Windows drive letters for FFmpeg filter syntax
                        ffmpeg_filter_path = posix_path.replace(':', '\\:')
                        
                        # Construct the video filter string for subtitles with styling
                        # Note: No extra single quotes around ffmpeg_filter_path for filename value
                        vf_filter = f"subtitles=filename={ffmpeg_filter_path}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF,BackColour=&H00000000,OutlineColour=&H80000000,BorderStyle=1,Outline=1,Shadow=1'"
                        
                        # Now add subtitles as a separate step
                        ffmpeg_cmd = [
                            'ffmpeg', '-y',
                            '-i', intermediate_file,
                            '-vf', vf_filter,
                            '-c:v', 'libx264' if not is_nvenc_available() else 'h264_nvenc',
                            '-preset', 'medium' if not is_nvenc_available() else 'p5',
                            '-crf', '22' if not is_nvenc_available() else '28',
                            '-c:a', 'copy',
                            subtitled_file
                        ]
                        
                        logger.info(f"Adding subtitles to segment {idx+1}")
                        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
                        subtitled_segments.append(subtitled_file)
                        
                        # Clean up intermediate file
                        if os.path.exists(intermediate_file):
                            os.unlink(intermediate_file)
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Error adding subtitles to segment {idx+1}: {e.stderr.decode() if e.stderr else str(e)}")
                        # Fall back to original segment if subtitle addition fails
                        subtitled_segments.append(segment_file)
                    except Exception as e:
                        logger.error(f"Unexpected error processing segment {idx+1}: {str(e)}")
                        subtitled_segments.append(segment_file)
                else:
                    # No subtitles for this segment, use the original
                    subtitled_segments.append(segment_file)
            
            # Update the concat list with subtitled segments
            with open(concat_list_path, 'w') as f:
                for segment_file_path in subtitled_segments:
                    f.write(f"file '{os.path.abspath(segment_file_path)}'\n")
        
        # Use the simple concat demuxer which allows for stream copying
        concat_cmd_list = [
            'ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_list_path,
            '-c', 'copy', '-movflags', '+faststart', output_file
        ]
        
        logger.info(f"Executing concatenation with concat demuxer (verified segments: {len(verified_segments)})")
        logger.debug(f"Concat command: {concat_cmd_list}")
        concat_result = subprocess.run(concat_cmd_list, capture_output=True, text=True)
                    
        # Check if the concatenation was successful
        if concat_result.returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            logger.info(f"Successfully created concatenated video: {output_file}")
            if concat_result.stdout:
                logger.debug(f"FFmpeg stdout (concat): {concat_result.stdout}")
            if concat_result.stderr: # Log stderr even on success for info messages like moov atom
                logger.debug(f"FFmpeg stderr (concat): {concat_result.stderr}")
        else:
            logger.error(f"Concatenation method failed. Return code: {concat_result.returncode}")
            logger.error(f"FFmpeg stderr (concat): {concat_result.stderr}")
            logger.error(f"FFmpeg stdout (concat): {concat_result.stdout}")
            if not os.path.exists(output_file):
                logger.error(f"Output file {output_file} does not exist.")
            elif os.path.getsize(output_file) == 0:
                logger.error(f"Output file {output_file} is empty.")

    except Exception as e:
        logger.error(f"Error during video concatenation: {str(e)}")
        raise
    finally:
        # Clean up temporary directory and files
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info("Cleaned up temporary files")
        
        # Clean up any temporary filter script files that weren't in the temp_dir
        for temp_file in temp_files_to_clean:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up temporary filter script: {temp_file}")
            except Exception as e:
                logger.warning(f"Error cleaning up temporary file: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Concatenate video highlights into a single video")
    parser.add_argument("--highlights", default="highlights.json", help="Path to the highlights JSON file")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker processes for parallel processing")
    parser.add_argument("--subtitles", action="store_true", help="Generate and add subtitles to the video")
    
    args = parser.parse_args()
    
    try:
        concatenate_highlights(
            highlights_json_path=args.highlights,
            num_workers=args.workers,
            generate_subtitles=args.subtitles
        )
    finally:
        # Clean up any temporary files created by the subtitle generator
        cleanup_temp_files() 