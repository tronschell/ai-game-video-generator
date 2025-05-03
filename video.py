import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import ffmpeg
from loguru import logger

from models import SelectedHighlight, CompilationPlan


def get_video_duration(video_path: str) -> float:
    """Get the duration of a video file in seconds"""
    try:
        probe = ffmpeg.probe(video_path)
        duration = float(probe['format']['duration'])
        logger.debug(f"Video duration: {duration}s for {video_path}")
        return duration
    except ffmpeg.Error as e:
        logger.error(f"Error probing video {video_path}: {e}")
        raise


def list_video_files(folder_path: str, extensions: List[str] = None) -> List[str]:
    """List all video files in a folder with given extensions"""
    if extensions is None:
        extensions = ['.mp4', '.avi', '.mov', '.mkv']
    
    video_files = []
    
    for root, _, files in os.walk(folder_path):
        for file in files:
            if any(file.lower().endswith(ext) for ext in extensions):
                video_files.append(os.path.join(root, file))
    
    logger.info(f"Found {len(video_files)} video files in {folder_path}")
    return video_files


def create_concat_file(highlights: List[SelectedHighlight], concat_file: str) -> None:
    """Create an FFmpeg concat file for the highlights"""
    with open(concat_file, 'w') as f:
        for highlight in highlights:
            # Verify the clip still exists at the source path
            if not os.path.exists(highlight.source_path):
                # Try the original path if the current path doesn't exist
                if os.path.exists(highlight.original_clip_path):
                    logger.warning(f"Using original path for clip {highlight.clip_id} as source path no longer exists")
                    actual_path = highlight.original_clip_path
                else:
                    raise FileNotFoundError(f"Neither source path {highlight.source_path} nor original path {highlight.original_clip_path} exist for clip {highlight.clip_id}")
            else:
                actual_path = highlight.source_path
            
            # Write the concat file entry
            f.write(f"file '{actual_path}'\n")
            f.write(f"inpoint {highlight.start_time}\n")
            f.write(f"outpoint {highlight.end_time}\n")
    
    logger.debug(f"Created concat file at {concat_file}")


def compile_highlights(plan: CompilationPlan, output_path: str) -> str:
    """Compile highlights into a single video using FFmpeg"""
    logger.info(f"Compiling {len(plan.highlights)} highlights into {output_path}")
    logger.info(f"Total duration: {plan.total_duration}s / Target: {plan.target_duration}s")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as concat_file:
        concat_path = concat_file.name
    
    try:
        # Create concat file
        create_concat_file(plan.highlights, concat_path)
        
        # Run ffmpeg concat command
        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_path, '-c', 'copy', output_path
        ]
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        
        logger.success(f"Successfully compiled highlights to {output_path}")
        return output_path
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during ffmpeg execution: {e}")
        raise
    
    finally:
        # Clean up
        if os.path.exists(concat_path):
            os.unlink(concat_path)


def generate_default_output_filename() -> str:
    """Generate default output filename with date"""
    date_str = datetime.now().strftime("%m-%d-%Y")
    return f"output{date_str}.mp4"


def create_thumbnail(video_path: str, output_thumbnail_path: Optional[str] = None) -> str:
    """Create a thumbnail from the compiled video"""
    if output_thumbnail_path is None:
        output_thumbnail_path = f"{os.path.splitext(video_path)[0]}.jpg"
    
    # Extract thumbnail at 20% of video duration
    duration = get_video_duration(video_path)
    timestamp = duration * 0.2
    
    cmd = [
        'ffmpeg', '-y', '-ss', str(timestamp), 
        '-i', video_path, '-vframes', '1', 
        '-q:v', '2', output_thumbnail_path
    ]
    
    logger.debug(f"Running command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    logger.debug(f"Created thumbnail at {output_thumbnail_path}")
    return output_thumbnail_path 