#!/usr/bin/env python
import os
import sys # Add sys for path manipulation
import shutil

# Ensure the project root is in sys.path for imports to work when run directly
if __name__ == '__main__' and __package__ is None:
    script_path = os.path.abspath(__file__)
    src_dir = os.path.dirname(script_path)
    project_root = os.path.dirname(src_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

import json
import argparse
import subprocess
import logging
import tempfile
import hashlib
import time
import csv
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import asyncio
from src.utils.config import Config
from src import video_analysis
from src.utils.analysis_tracker import AnalysisTracker
from src.subtitle_generator import SubtitleGenerator, generate_subtitles_for_video, cleanup_temp_files

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ShortsCreator:
    def __init__(self):
        pass

    async def create_shorts_video(self, video_path: str, start_time: int, end_time: int, output_path: str = None, no_webcam: bool = False, add_subtitles: bool = False):
        """Create a shorts-style video with webcam at top 1/3 and gameplay at bottom 2/3."""
        # Generate output path if not provided
        if output_path is None:
            export_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'exported_videos')
            os.makedirs(export_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(export_dir, f"short_{timestamp}.mp4")
        
        if not os.path.exists(video_path):
            logger.error(f"Source video not found: {video_path}")
            return None
        
        if end_time <= start_time:
            logger.error("Invalid timestamp range")
            return None
        
        duration = end_time - start_time
        
        # Create temp directory for intermediate files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract clip from source video
            clip_path = os.path.join(temp_dir, "clip.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-hwaccel", "cuda",
                "-i", video_path, 
                "-ss", str(start_time), "-t", str(duration),
                "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", 
                "-c:a", "aac", "-b:a", "192k",
                clip_path
            ], check=True)
            
            # Generate subtitles if requested
            subtitle_path = None
            if add_subtitles and os.path.exists(clip_path):
                try:
                    logger.info(f"Generating subtitles for shorts clip")
                    subtitle_path = generate_subtitles_for_video(clip_path, is_short=True)
                    logger.info(f"Subtitles generated for shorts clip: {subtitle_path}")
                except Exception as e:
                    logger.error(f"Failed to generate subtitles for shorts clip: {str(e)}")
                    # Continue without subtitles if generation fails
            
            # Get source video dimensions
            try:
                src_width = int(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", 
                                                     "-show_entries", "stream=width", "-of", "csv=p=0", 
                                                     clip_path]).decode().strip())
                src_height = int(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", 
                                                      "-show_entries", "stream=height", "-of", "csv=p=0", 
                                                      clip_path]).decode().strip())
                logger.info(f"Source video dimensions: {src_width}x{src_height}")
            except Exception as e:
                logger.error(f"Error getting video dimensions: {str(e)}")
                src_width, src_height = 1920, 1080  # Default to common resolution if probe fails
            
            # Set output dimensions - TikTok's preferred resolution
            output_width = 1080
            output_height = 1920
            
            # Set dimensions based on whether webcam is used or not
            if no_webcam:
                gameplay_height_percent = 0.8  # 80% of screen for gameplay
                gameplay_area_height = int(output_height * gameplay_height_percent)
                top_bar_height = int((output_height - gameplay_area_height) / 2)
                bottom_bar_height = output_height - gameplay_area_height - top_bar_height
                webcam_height = 0
            else:
                webcam_height = round(output_height / 3)  # Webcam is top 1/3
                gameplay_area_height = output_height - webcam_height # Gameplay is bottom 2/3
                
            killfeed_scale_factor = 0.6 # Scale killfeed to 60% of output_width
            
            # Create blurred background
            blurred_bg = os.path.join(temp_dir, "blurred_bg.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-hwaccel", "cuda",
                "-i", clip_path,
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5",
                "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", "-an",
                blurred_bg
            ], check=True)
            
            # Extract webcam using hardcoded values from the screenshot
            webcam_path = os.path.join(temp_dir, "webcam.mp4")
            
            if not no_webcam:
                # Hardcoded coordinates and dimensions based on user's latest specification
                # for a 1440p (2560x1440) source video. Coordinates are from top-left.
                # Left edge: 43px from left screen edge
                # Right edge: 1959px from right screen edge (i.e., 2560 - 1959 = 601px from left)
                # Top edge: 463px from top screen edge
                # Bottom edge: 663px from top screen edge
                
                desired_crop_x = 43
                desired_crop_y = 463
                desired_crop_width = 558  # Calculated as (2560 - 1959) - 43
                desired_crop_height = 300 # Calculated as 663 - 463

                # Calculate actual crop dimensions and positions, 
                # ensuring they are within the source video's bounds.
                
                # Ensure x and y are within [0, source_dimension - 1]
                x = max(0, min(desired_crop_x, src_width - 1 if src_width > 0 else 0))
                y = max(0, min(desired_crop_y, src_height - 1 if src_height > 0 else 0))
                
                # Adjust width: ensure it's at least 1px and does not exceed available width from x.
                width = max(1, min(desired_crop_width, src_width - x if src_width > x else 0))
                
                # Adjust height: ensure it's at least 1px and does not exceed available height from y.
                height = max(1, min(desired_crop_height, src_height - y if src_height > y else 0))
                
                logger.info(f"Attempting to extract webcam from coordinates: x={x}, y={y}, width={width}, height={height}")
                
                # Extract webcam region
                subprocess.run([
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", clip_path,
                    "-vf", f"crop={width}:{height}:{x}:{y}", 
                    "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", "-an",
                    webcam_path
                ], check=True)
            
            # Killfeed extraction
            kf_desired_crop_x = 2069
            kf_desired_crop_y = 78
            kf_desired_crop_width = 475
            kf_desired_crop_height = 201

            kf_x = max(0, min(kf_desired_crop_x, src_width - 1 if src_width > 0 else 0))
            kf_y = max(0, min(kf_desired_crop_y, src_height - 1 if src_height > 0 else 0))
            # Ensure width/height are at least 1 and do not exceed available dimensions from x/y
            kf_crop_w = max(1, min(kf_desired_crop_width, src_width - kf_x if src_width > kf_x else 0))
            kf_crop_h = max(1, min(kf_desired_crop_height, src_height - kf_y if src_height > kf_y else 0))

            killfeed_path = os.path.join(temp_dir, "killfeed.mp4")
            logger.info(f"Attempting to extract killfeed from coordinates: x={kf_x}, y={kf_y}, width={kf_crop_w}, height={kf_crop_h}")
            subprocess.run([
                "ffmpeg", "-y", "-hwaccel", "cuda",
                "-i", clip_path,
                "-vf", f"crop={kf_crop_w}:{kf_crop_h}:{kf_x}:{kf_y}",
                "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "10M", "-maxrate", "15M", "-bufsize", "30M", "-an", # Adjusted bitrate for smaller element
                killfeed_path
            ], check=True)
            logger.info(f"Killfeed extracted to {killfeed_path}")
            
            # Create gameplay video with slight zoom for better visibility
            gameplay_path = os.path.join(temp_dir, "gameplay.mp4")
            
            # Add subtitles to gameplay if requested
            if subtitle_path and add_subtitles:
                logger.info("Adding subtitles to gameplay video")
                
                # First extract zoomed clip without subtitles to a temporary file
                zoomed_clip_path = os.path.join(temp_dir, "zoomed_clip.mp4")
                subprocess.run([
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", clip_path,
                    "-vf", "scale=iw*1.15:-1,crop=iw/1.15:ih/1.15:(iw-iw/1.15)/2:(ih-ih/1.15)/2",
                    "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", 
                    "-c:a", "copy",
                    zoomed_clip_path
                ], check=True)
                
                # Then add subtitles as a second pass - this avoids complex filter chains
                try:
                    # Convert to absolute POSIX path for consistency
                    posix_path = Path(subtitle_path).resolve().as_posix()
                    # Escape the colon for Windows drive letters for FFmpeg filter syntax
                    # e.g., C:/path/to/srt -> C\\:/path/to/srt
                    ffmpeg_filter_path = posix_path.replace(':', '\\:')
                    
                    # Construct the video filter string for subtitles with styling
                    # Note: No extra single quotes around ffmpeg_filter_path for filename value
                    vf_filter = f"subtitles=filename={ffmpeg_filter_path}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF,BackColour=&H00000000,OutlineColour=&H80000000,BorderStyle=1,Outline=1,Shadow=1'"
                    
                    subprocess.run([
                        "ffmpeg", "-y", "-hwaccel", "cuda",
                        "-i", zoomed_clip_path,
                        "-vf", vf_filter,
                        "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", 
                        "-c:a", "copy",
                        gameplay_path
                    ], check=True)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Error adding subtitles: {str(e)}")
                    logger.warning("Falling back to processing without subtitles")
                    # Use the zoomed clip directly if subtitle overlay fails
                    shutil.copy(zoomed_clip_path, gameplay_path)
                
                # Clean up temporary file
                try:
                    if os.path.exists(zoomed_clip_path):
                        os.unlink(zoomed_clip_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {e}")
            else:
                # No subtitles, just apply zoom
                subprocess.run([
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", clip_path,
                    # Apply slight zoom to fill more of the screen
                    "-vf", "scale=iw*1.15:-1,crop=iw/1.15:ih/1.15:(iw-iw/1.15)/2:(ih-ih/1.15)/2",
                    "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", 
                    "-c:a", "copy",
                    gameplay_path
                ], check=True)
            
            # Create filter complex for ffmpeg
            filter_complex = []
            
            if no_webcam:
                # For no webcam mode, the gameplay takes up 70% of the screen with blurry bars
                filter_complex.extend([
                    # Gameplay - scale to fit the 70% height while maintaining aspect ratio
                    f"[2:v]scale=-1:{gameplay_area_height}:force_original_aspect_ratio=1[gameplay_base]",
                    
                    # Killfeed processing: scale and set opacity
                    f"[3:v]scale={output_width}*{killfeed_scale_factor}:-1,format=rgba,colorchannelmixer=aa=0.6[killfeed_scaled]",
                    
                    # Overlay killfeed at the top of gameplay
                    f"[gameplay_base][killfeed_scaled]overlay=x=(W-w)/2:y=0[gameplay_with_killfeed]",
                    
                    # Overlay gameplay_with_killfeed onto blurred background, positioned in the middle
                    f"[0:v][gameplay_with_killfeed]overlay=x=(W-w)/2:y={top_bar_height}[v]"
                ])
            else:
                # Original layout with webcam at top
                filter_complex.extend([
                    # Webcam at top - scale to fit the container, potentially changing aspect ratio
                    f"[1:v]scale={output_width}:{webcam_height}[webcam_scaled]",
                    
                    # Gameplay at bottom - scale to fill gameplay_height (cropping width if needed)
                    f"[2:v]scale={output_width}:{gameplay_area_height}:force_original_aspect_ratio=increase,crop={output_width}:{gameplay_area_height}[gameplay_base]",
                    
                    # Killfeed processing: scale and set opacity
                    f"[3:v]scale={output_width}*{killfeed_scale_factor}:-1,format=rgba,colorchannelmixer=aa=0.6[killfeed_scaled]",
                    
                    # Overlay killfeed onto the top of gameplay_base
                    f"[gameplay_base][killfeed_scaled]overlay=x=(W-w)/2:y=0[gameplay_with_killfeed]",
                    
                    # Overlay webcam_scaled onto blurred_bg
                    f"[0:v][webcam_scaled]overlay=x=0:y=0[bg_plus_webcam]",
                    
                    # Overlay gameplay_with_killfeed onto bg_plus_webcam, positioned below webcam
                    f"[bg_plus_webcam][gameplay_with_killfeed]overlay=x=0:y={webcam_height}[v]"
                ])
            
            try:
                # Final composition
                ffmpeg_command = [
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", blurred_bg,
                ]
                
                if not no_webcam:
                    ffmpeg_command.append("-i")
                    ffmpeg_command.append(webcam_path)
                else:
                    # Add a dummy input for consistency in filter_complex indexing
                    ffmpeg_command.append("-f")
                    ffmpeg_command.append("lavfi")
                    ffmpeg_command.append("-i")
                    ffmpeg_command.append("color=c=black:s=16x16:r=30")
                
                ffmpeg_command.extend([
                    "-i", gameplay_path,
                    "-i", killfeed_path,
                    "-filter_complex", ";".join(filter_complex),
                    "-map", "[v]", "-map", "2:a",
                    "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M",
                    "-c:a", "aac", "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    "-s", f"{output_width}x{output_height}",
                    output_path
                ])
                
                subprocess.run(ffmpeg_command, check=True)
                logger.info(f"Created shorts video: {output_path}")
                return output_path
            except subprocess.CalledProcessError as e:
                logger.error(f"Error executing FFmpeg command: {str(e)}")
                logger.error(f"Filter complex: {';'.join(filter_complex)}")
                return None

async def _concatenate_videos_ffmpeg(input_files: List[str]) -> Optional[str]:
    """Concatenate multiple video files into a single temporary file using ffmpeg."""
    if not input_files or len(input_files) < 2: # No need to concatenate if less than 2 files
        return input_files[0] if input_files else None

    # Create a temporary file for ffmpeg's file list
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_filelist:
        for video_file in input_files:
            abs_video_path = os.path.abspath(video_file)
            # Ensure path escaping for ffmpeg if necessary, though quotes should handle most cases.
            # For 'file' directive, paths with special characters might need careful handling.
            # Using forward slashes is generally safer with ffmpeg's concat demuxer.
            safe_path = abs_video_path.replace("\\\\", "/").replace("\\", "/")
            tmp_filelist.write(f"file '{safe_path}'\\n")
        filelist_path = tmp_filelist.name
    
    concatenated_video_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    output_path = concatenated_video_temp_file.name
    concatenated_video_temp_file.close()

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", filelist_path,
        "-c", "copy",
        output_path
    ]
    
    logger.info(f"Attempting to concatenate videos: {input_files} into {output_path}")
    try:
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg concatenation failed. Return code: {process.returncode}")
            logger.error(f"FFmpeg stdout: {stdout.decode(errors='ignore') if stdout else 'N/A'}")
            logger.error(f"FFmpeg stderr: {stderr.decode(errors='ignore') if stderr else 'N/A'}")
            if os.path.exists(output_path): os.remove(output_path)
            final_output_path = None
        else:
            logger.info(f"Successfully concatenated videos into {output_path}")
            final_output_path = output_path
            
    except Exception as e:
        logger.error(f"Error during video concatenation: {str(e)}")
        if os.path.exists(output_path): os.remove(output_path)
        final_output_path = None
    finally:
        if os.path.exists(filelist_path): os.remove(filelist_path)

    return final_output_path

async def process_video(video_path_for_highlight_lookup: str, video_path_for_short_creation: str, output_path: Optional[str] = None, no_webcam: bool = False, add_subtitles: bool = False):
    """Process a single video to create a shorts video, using metadata from one path and media from another."""
    try:
        if not os.path.exists(video_path_for_short_creation):
            logger.error(f"Video file for short creation not found: {video_path_for_short_creation}")
            return False
        if not os.path.exists(video_path_for_highlight_lookup):
            logger.error(f"Video file for highlight lookup not found: {video_path_for_highlight_lookup}")
            return False
        
        analysis_tracker = AnalysisTracker()
        creator = ShortsCreator()
        
        # Clean up any temporary files at the end
        temp_files_to_clean = []

        abs_lookup_path = os.path.abspath(video_path_for_highlight_lookup)
        highlights_to_use = None

        if analysis_tracker.is_clip_analyzed(abs_lookup_path):
            logger.info(f"Found existing analysis for {os.path.basename(abs_lookup_path)} via AnalysisTracker.")
            highlights_to_use = analysis_tracker.get_clip_results(abs_lookup_path)
            if not highlights_to_use:
                 logger.warning(f"AnalysisTracker reported clip as analyzed, but no highlights were retrieved for {os.path.basename(abs_lookup_path)}. Re-analyzing.")
                 # Fall through to analysis block
        
        if not highlights_to_use:
            logger.info(f"No existing valid highlights for {os.path.basename(abs_lookup_path)} via AnalysisTracker. Analyzing video...")
            try:
                # video_analysis.analyze_video returns (highlights_list, token_data_dict)
                newly_analyzed_highlights, _ = await video_analysis.analyze_video(
                    video_path=abs_lookup_path, 
                    output_file=None  # Prevent analyze_video from writing to its default file
                )

                if newly_analyzed_highlights:
                    logger.info(f"Successfully analyzed {os.path.basename(abs_lookup_path)}, found {len(newly_analyzed_highlights)} highlights.")
                    analysis_tracker.mark_clip_as_analyzed(abs_lookup_path, newly_analyzed_highlights)
                    analysis_tracker.save_analyzed_clips()
                    logger.info(f"Saved new highlights for {os.path.basename(abs_lookup_path)} using AnalysisTracker.")
                    highlights_to_use = newly_analyzed_highlights
                else:
                    logger.error(f"Analysis of {os.path.basename(abs_lookup_path)} yielded no highlights.")
                    return False
            except Exception as e:
                logger.error(f"Error during analysis of {os.path.basename(abs_lookup_path)}: {str(e)}")
                return False
        
        if highlights_to_use:
            # Using the first highlight found
            if not isinstance(highlights_to_use, list) or not highlights_to_use:
                logger.error(f"Highlights for {os.path.basename(abs_lookup_path)} are not in the expected format or empty. Cannot create short.")
                return False

            first_highlight = highlights_to_use[0]
            start_time = first_highlight.get("timestamp_start_seconds")
            end_time = first_highlight.get("timestamp_end_seconds")

            if start_time is None or end_time is None:
                logger.error(f"Highlight for {os.path.basename(abs_lookup_path)} is missing start or end time. Highlight data: {first_highlight}")
                return False
            
            logger.info(f"Creating short from '{os.path.basename(video_path_for_short_creation)}' using highlight: {first_highlight.get('clip_description')}")
            result = await creator.create_shorts_video(
                video_path_for_short_creation, start_time, end_time, output_path, no_webcam, add_subtitles
            )
            return result is not None
        else:
            logger.error(f"No highlights available for {os.path.basename(abs_lookup_path)} to create a short video after attempting analysis.")
            return False
    
    except Exception as e:
        logger.error(f"An error occurred in process_video for {video_path_for_highlight_lookup}: {str(e)}")
        return False
    finally:
        # Clean up any temporary filter script files
        for i in range(len(temp_files_to_clean)):
            try:
                temp_file = temp_files_to_clean[i]
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up temporary filter script: {temp_file}")
            except Exception as e:
                logger.warning(f"Error cleaning up temporary file: {e}")

async def main_async():
    parser = argparse.ArgumentParser(description="Create a shorts-style video from analyzed clips")
    parser.add_argument("--video-paths", nargs='+', required=True, help="Path(s) to video file(s) to use. If multiple, they will be concatenated.")
    parser.add_argument("--output", "-o", help="Output video path (optional)")
    parser.add_argument("--no-webcam", action="store_true", help="Create video without webcam, gameplay takes up most of the screen")
    parser.add_argument("--subtitles", action="store_true", help="Add subtitles to the video (3 words per line)")
    args = parser.parse_args()
    
    if not args.video_paths:
        logger.error("No video paths provided.")
        return

    actual_video_file_for_short = None
    temp_concatenated_video_path = None 

    try:
        if len(args.video_paths) > 1:
            logger.info(f"Multiple video paths provided. Attempting to concatenate: {args.video_paths}")
            temp_concatenated_video_path = await _concatenate_videos_ffmpeg(args.video_paths)
            if not temp_concatenated_video_path:
                logger.error("Failed to concatenate videos. Aborting.")
                return
            actual_video_file_for_short = temp_concatenated_video_path
        else:
            actual_video_file_for_short = args.video_paths[0]

        path_for_metadata_lookup = args.video_paths[0] # Always use the first video for metadata

        if actual_video_file_for_short and path_for_metadata_lookup:
            logger.info(f"Processing video for short: {actual_video_file_for_short}")
            logger.info(f"Using metadata from: {path_for_metadata_lookup}")
            logger.info(f"No webcam mode: {args.no_webcam}")
            logger.info(f"Add subtitles: {args.subtitles}")
            
            success = await process_video(
                video_path_for_highlight_lookup=path_for_metadata_lookup,
                video_path_for_short_creation=actual_video_file_for_short,
                output_path=args.output,
                no_webcam=args.no_webcam,
                add_subtitles=args.subtitles
            )
            if success:
                logger.info(f"Successfully created shorts video from {os.path.basename(actual_video_file_for_short)}")
            else:
                logger.error(f"Failed to create shorts video from {os.path.basename(actual_video_file_for_short)}")
        else:
            logger.error("Could not determine video for processing or metadata lookup.")

    finally:
        if temp_concatenated_video_path and os.path.exists(temp_concatenated_video_path):
            logger.info(f"Cleaning up temporary concatenated video: {temp_concatenated_video_path}")
            try:
                os.remove(temp_concatenated_video_path)
            except Exception as e:
                logger.error(f"Error cleaning up temporary file {temp_concatenated_video_path}: {e}")

def main():
    """Entry point that runs the async main function."""
    try:
        asyncio.run(main_async())
    finally:
        # Clean up any temporary files created by the subtitle generator
        cleanup_temp_files()

if __name__ == "__main__":
    main()
