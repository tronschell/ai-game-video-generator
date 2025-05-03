#!/usr/bin/env python3
import os
import sys
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from loguru import logger

from db import ClipDatabase
from highlighter import HighlightCompiler
from logging_config import setup_logging
from video import compile_highlights, generate_default_output_filename, create_thumbnail


@click.command()
@click.option(
    "--clips-folder",
    default="E:\\Game Recordings\\Counter-strike 2",
    help="Path to folder containing CS2 game recordings"
)
@click.option(
    "--output-length",
    default=10.0,
    type=float,
    help="Target length of output video in minutes"
)
@click.option(
    "--output-filename",
    default=None,
    help="Output video filename"
)
@click.option(
    "--include-used-clips",
    is_flag=True,
    help="Include previously used clips"
)
@click.option(
    "--create-thumbnail",
    is_flag=True,
    help="Create a thumbnail from the compiled video"
)
@click.option(
    "--max-clips",
    default=None,
    type=int,
    help="Maximum number of clips to analyze"
)
def main(
    clips_folder: str,
    output_length: float,
    output_filename: Optional[str],
    include_used_clips: bool,
    create_thumbnail: bool,
    max_clips: Optional[int]
) -> None:
    """
    CS2 Highlight Generator
    
    Analyzes CS2 gameplay clips, identifies highlights, and compiles them into a video.
    """
    # Run the async main function
    asyncio.run(async_main(
        clips_folder,
        output_length,
        output_filename,
        include_used_clips,
        create_thumbnail,
        max_clips
    ))


async def async_main(
    clips_folder: str,
    output_length: float,
    output_filename: Optional[str],
    include_used_clips: bool,
    create_thumbnail: bool,
    max_clips: Optional[int]
) -> None:
    """Async main function that handles the highlight generation process"""
    # Setup logging
    setup_logging()
    
    logger.info("Starting CS2 Highlight Generator")
    logger.info(f"Clips folder: {clips_folder}")
    logger.info(f"Output length: {output_length} minutes")
    
    try:
        # Check if clips folder exists
        if not os.path.isdir(clips_folder):
            logger.error(f"Clips folder does not exist: {clips_folder}")
            sys.exit(1)
        
        # Set output filename if not provided
        if output_filename is None:
            output_filename = generate_default_output_filename()
        
        logger.info(f"Output filename: {output_filename}")
        
        # Initialize highlight compiler
        compiler = HighlightCompiler(
            clips_folder=clips_folder,
            output_length_minutes=output_length,
            include_used_clips=include_used_clips
        )
        
        # Scan for video files
        video_files = compiler.scan_clips_folder()
        
        if not video_files:
            logger.error(f"No video files found in {clips_folder}")
            sys.exit(1)
        
        # Limit number of clips to analyze if specified
        if max_clips is not None and max_clips > 0:
            video_files = video_files[:max_clips]
            logger.info(f"Limiting analysis to {max_clips} clips")
        
        # Analyze clips
        await compiler.analyze_clips()
        
        # Plan compilation
        plan = compiler.plan_compilation()
        
        if not plan.highlights:
            logger.error("No highlights found to compile")
            sys.exit(1)
        
        # Save compilation plan as JSON
        plan_filename = f"compilation_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(plan_filename, 'w') as f:
            import json
            json.dump(plan.model_dump(), f, indent=2, default=str)
        
        # Compile highlights
        output_path = compile_highlights(plan, output_filename)
        
        # Mark used clips
        compiler.mark_clips_as_used(plan)
        
        # Create thumbnail if requested
        if create_thumbnail:
            thumbnail_path = create_thumbnail(output_path)
            logger.info(f"Created thumbnail: {thumbnail_path}")
        
        logger.success(f"Compilation complete! Output video: {output_path}")
        
    except Exception as e:
        logger.exception(f"Error during highlight generation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
