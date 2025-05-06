import json
import os
import logging
import shutil
from typing import List, Dict
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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

        # First step: Cut each segment precisely with timestamps and add 1-second buffer
        for idx, highlight in enumerate(highlights):
            source_video = highlight['source_video']
            start_time = highlight['timestamp_start_seconds']
            # Add 1 second to end time for smooth transitions
            end_time = highlight['timestamp_end_seconds'] + 2
            duration = end_time - start_time
            
            segment_file = os.path.join(temp_dir, f'segment_{idx}.mp4')
            # Cut segment using precise seeking and avoid timestamp issues
            cut_cmd = (
                f'ffmpeg -ss {start_time} -i "{source_video}" '
                f'-t {duration} -c:v copy -c:a copy '
                f'-avoid_negative_ts make_zero -fflags +genpts '
                f'-map 0:v:0 -map 0:a:0? "{segment_file}"'
            )
            logging.info(f"Cutting segment {idx + 1}/{len(highlights)}")
            logging.debug(f"Cut command: {cut_cmd}")
            os.system(cut_cmd)
            cut_segments.append(segment_file)

        # Create concat list with only the clean cut segments
        concat_list_path = os.path.join(temp_dir, 'concat_list.txt')
        with open(concat_list_path, 'w') as f:
            for segment in cut_segments:
                f.write(f"file '{os.path.basename(segment)}'\n")

        # Concatenate the clean segments
        output_file = os.path.join(export_dir, f'highlights_{int(time.time())}.mp4')
        concat_cmd = (
            f'ffmpeg -f concat -safe 0 -i "{concat_list_path}" '
            f'-c copy -movflags +faststart "{output_file}"'
        )
        
        logging.info("Executing final concatenation")
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