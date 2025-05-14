import json
import os
import logging
import shutil
import subprocess
from typing import List, Dict, Tuple, Optional
import time
from datetime import datetime
from config import Config

# Get module-specific logger
logger = logging.getLogger(__name__)

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

def has_flac_or_alac_audio(video_path: str) -> bool:
    """
    Check if a video file has FLAC or ALAC audio streams.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        True if FLAC or ALAC audio is detected, False otherwise
    """
    try:
        cmd = [
            'ffprobe', '-v', 'error', 
            '-select_streams', 'a:0',
            '-show_entries', 'stream=codec_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            '-i', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        codec = result.stdout.strip().lower()
        return 'flac' in codec or 'alac' in codec
    except Exception as e:
        logger.warning(f"Error checking audio codec: {str(e)}")
        return False

def concatenate_highlights(highlights_json_path: str = 'highlights.json') -> None:
    """
    Concatenates video clips specified in highlights.json into a single output video
    using a two-step process to ensure clean concatenation.
    
    Args:
        highlights_json_path: Path to the JSON file containing highlights
    """
    # Create necessary directories
    export_dir = 'exported_videos'
    temp_dir = 'temp_segments'
    os.makedirs(export_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    cut_segments = []
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
        
        # Step 1: Cut each segment precisely with timestamps and standardize audio to AAC
        for idx, highlight in enumerate(highlights):
            source_video = highlight['source_video']
            start_time = highlight['timestamp_start_seconds']
            # Add 1 second to end time for smooth transitions
            end_time = highlight['timestamp_end_seconds'] + 2
            duration = end_time - start_time
            
            segment_file = os.path.join(temp_dir, f'segment_{idx:03d}.mp4')  # Zero-pad for correct ordering
            
            # Check if source has FLAC/ALAC audio that needs conversion
            needs_audio_conversion = has_flac_or_alac_audio(source_video)
            
            # Standardize the audio to AAC to ensure compatibility
            logger.info(f"Cutting segment {idx + 1}/{len(highlights)} from {os.path.basename(source_video)}")
            
            if needs_audio_conversion:
                # Re-encode video when exotic audio formats are detected using NVIDIA hardware acceleration
                logger.info(f"FLAC/ALAC audio detected, re-encoding segment {idx + 1} with GPU acceleration")
                cut_cmd = (
                    f'ffmpeg -i "{source_video}" -ss {start_time} '
                    f'-t {duration} -c:v h264_nvenc -preset p4 -tune hq -b:v 30M -c:a aac -b:a 192k '
                    f'-avoid_negative_ts make_zero -movflags +faststart '
                    f'-map 0:v:0 -map 0:a:0? "{segment_file}"'
                )
            else:
                # Use accurate two-pass cutting for standard audio formats
                logger.info(f"Using accurate two-pass cutting for segment {idx + 1}")
                cut_cmd = (
                    f'ffmpeg -i "{source_video}" -ss {start_time} '
                    f'-t {duration} -c:v h264_nvenc -preset p4 -tune hq -b:v 30M -c:a aac -b:a 192k '
                    f'-avoid_negative_ts make_zero -movflags +faststart '
                    f'-map 0:v:0 -map 0:a:0? "{segment_file}"'
                )
            
            logger.debug(f"Cut command: {cut_cmd}")
            os.system(cut_cmd)
            
            # Verify segment duration to ensure accurate cutting
            try:
                duration_cmd = [
                    'ffprobe', '-v', 'error', 
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    segment_file
                ]
                result = subprocess.run(duration_cmd, capture_output=True, text=True)
                actual_duration = float(result.stdout.strip())
                expected_duration = duration
                
                # Check if the cut segment is within reasonable bounds
                if abs(actual_duration - expected_duration) > 3:
                    logger.warning(f"Segment {idx+1} duration mismatch: expected {expected_duration:.2f}s, got {actual_duration:.2f}s")
                    # Re-cut using stricter method for problem segments
                    retry_cmd = (
                        f'ffmpeg -i "{source_video}" -ss {start_time} -to {start_time + duration} '
                        f'-c:v h264_nvenc -preset p4 -tune hq -b:v 30M -c:a aac -b:a 192k '
                        f'-avoid_negative_ts make_zero -movflags +faststart '
                        f'-map 0:v:0 -map 0:a:0? -y "{segment_file}"'
                    )
                    logger.info(f"Retrying segment {idx+1} with precise cutting")
                    os.system(retry_cmd)
                else:
                    logger.info(f"Segment {idx+1} duration verified: {actual_duration:.2f}s")
            except Exception as e:
                logger.warning(f"Could not verify segment {idx+1} duration: {str(e)}")
            
            cut_segments.append(segment_file)

        # Step 2: Verify all segments before concatenation
        verified_segments = []
        total_duration = 0
        
        for idx, segment in enumerate(cut_segments):
            # Verify each segment's duration using ffprobe
            try:
                duration_cmd = [
                    'ffprobe', '-v', 'error', 
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    segment
                ]
                result = subprocess.run(duration_cmd, capture_output=True, text=True)
                duration = float(result.stdout.strip())
                logger.info(f"Segment {idx+1} duration: {duration:.2f} seconds")
                
                if duration > 0 and os.path.exists(segment) and os.path.getsize(segment) > 0:
                    verified_segments.append(segment)
                    total_duration += duration
                else:
                    logger.warning(f"Skipping invalid segment {idx+1} (duration: {duration:.2f}s)")
            except Exception as e:
                logger.warning(f"Error verifying segment {idx+1}: {str(e)}")
        
        logger.info(f"Total verified segments: {len(verified_segments)}/{len(cut_segments)}")
        logger.info(f"Expected total duration: {total_duration:.2f} seconds")
        
        # Create a fresh concatenation file list with only verified segments
        concat_list_path = os.path.join(temp_dir, 'concat_list.txt')
        with open(concat_list_path, 'w') as f:
            for segment in verified_segments:
                f.write(f"file '{os.path.abspath(segment)}'\n")

        # Step 3: Use concat demuxer for stream copying (no re-encoding)
        output_file = os.path.join(export_dir, f'highlights_{int(time.time())}.mp4')
        
        # Use the simple concat demuxer which allows for stream copying
        concat_cmd = (
            f'ffmpeg -f concat -safe 0 -i "{concat_list_path}" '
            f'-c copy -movflags +faststart "{output_file}"'
        )
        
        logger.info(f"Executing concatenation with concat demuxer (verified segments: {len(verified_segments)})")
        logger.debug(f"Concat command: {concat_cmd}")
        os.system(concat_cmd)
                    
        # Check if the concatenation was successful
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            logger.info(f"Successfully created concatenated video: {output_file}")
        else:
            logger.error("Concatenation method failed")

    except Exception as e:
        logger.error(f"Error during video concatenation: {str(e)}")
        raise
    finally:
        # Clean up temporary directory and files
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info("Cleaned up temporary files")

if __name__ == "__main__":
    concatenate_highlights() 