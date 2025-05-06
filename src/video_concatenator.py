import json
import os
import logging
import shutil
from typing import List, Dict
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def parse_video_timestamp(filename: str) -> datetime:
    """
    Parse timestamp from video filename format: 'Counter-strike 2 YYYY.MM.DD - HH.MM.SS.ms.DVR'
    
    Args:
        filename: The video filename containing the timestamp
        
    Returns:
        datetime object representing the video's timestamp
    """
    try:
        # Extract the date-time portion from the filename
        date_time_str = filename.split('Counter-strike 2 ')[1].split('.DVR')[0]
        date_part, time_part = date_time_str.split(' - ')
        
        # Parse date components
        year, month, day = map(int, date_part.split('.'))
        
        # Parse time components (ignoring milliseconds)
        hour, minute, second = map(int, time_part.split('.')[:3])
        
        return datetime(year, month, day, hour, minute, second)
    except Exception as e:
        logging.error(f"Error parsing timestamp from filename {filename}: {str(e)}")
        # Return epoch time as fallback
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

    # Group highlights by source video
    video_groups = {}
    for highlight in highlights:
        source = highlight['source_video']
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
            highlights = data.get('highlights', [])

        if not highlights:
            logging.warning("No highlights found in the JSON file")
            return

        # Merge overlapping highlights
        highlights = merge_overlapping_highlights(highlights)
        
        # Sort highlights based on video timestamps
        highlights.sort(key=lambda x: parse_video_timestamp(os.path.basename(x['source_video'])))
        
        # First step: Cut each segment precisely with timestamps and add 1-second buffer
        for idx, highlight in enumerate(highlights):
            source_video = highlight['source_video']
            start_time = highlight['timestamp_start_seconds']
            # Add 1 second to end time for smooth transitions
            end_time = highlight['timestamp_end_seconds'] + 2
            duration = end_time - start_time
            
            segment_file = os.path.join(temp_dir, f'segment_{idx:03d}.mp4')  # Zero-pad for correct ordering
            # Cut segment using precise seeking and avoid timestamp issues
            cut_cmd = (
                f'ffmpeg -ss {start_time} -i "{source_video}" '
                f'-t {duration} -c:v copy -c:a copy '
                f'-avoid_negative_ts make_zero -fflags +genpts '
                f'-map 0:v:0 -map 0:a:0? "{segment_file}"'
            )
            logging.info(f"Cutting segment {idx + 1}/{len(highlights)} from {os.path.basename(source_video)}")
            logging.debug(f"Cut command: {cut_cmd}")
            os.system(cut_cmd)
            cut_segments.append(segment_file)

        # Create concat list with only the clean cut segments
        concat_list_path = os.path.join(temp_dir, 'concat_list.txt')
        with open(concat_list_path, 'w') as f:
            for segment in cut_segments:
                f.write(f"file '{os.path.basename(segment)}'\n")

        # First, check the number of audio streams in the first segment
        probe_cmd = f'ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "{cut_segments[0]}"'
        audio_streams = os.popen(probe_cmd).read().strip().split('\n')
        num_audio_streams = len([s for s in audio_streams if s])  # Filter out empty lines
        
        # Concatenate the clean segments with appropriate audio handling
        output_file = os.path.join(export_dir, f'highlights_{int(time.time())}.mp4')
        
        if num_audio_streams > 1:
            # If we have multiple audio streams, merge them
            concat_cmd = (
                f'ffmpeg -f concat -safe 0 -i "{concat_list_path}" '
                f'-filter_complex "[0:a:0][0:a:1]amerge=inputs=2,pan=stereo|c0<c0+c2|c1<c1+c3[aout]" '
                f'-map 0:v:0 -map "[aout]" '
                f'-c:v copy -c:a aac -b:a 192k '
                f'-movflags +faststart "{output_file}"'
            )
        else:
            # If we only have one audio stream, just copy it
            concat_cmd = (
                f'ffmpeg -f concat -safe 0 -i "{concat_list_path}" '
                f'-c:v copy -c:a aac -b:a 192k '
                f'-movflags +faststart "{output_file}"'
            )
        
        logging.info(f"Executing final concatenation with {'merged' if num_audio_streams > 1 else 'single'} audio track")
        logging.debug(f"Concat command: {concat_cmd}")
        os.system(concat_cmd)
        logging.info(f"Successfully created concatenated video: {output_file}")

    except Exception as e:
        logging.error(f"Error during video concatenation: {str(e)}")
        raise
    finally:
        # Clean up temporary directory and files
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logging.info("Cleaned up temporary files")

if __name__ == "__main__":
    concatenate_highlights() 