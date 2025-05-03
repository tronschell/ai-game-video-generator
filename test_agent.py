#!/usr/bin/env python3
import os
import argparse
import json
import asyncio
from pathlib import Path

from loguru import logger

from agent import process_video_with_agent
from logging_config import setup_logging


async def async_main():
    """Test the agent implementation with a sample video file"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Test the CS2 Highlight Agent")
    parser.add_argument(
        "--video", 
        type=str, 
        required=True,
        help="Path to a CS2 gameplay video"
    )
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    video_path = args.video
    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return 1
    
    logger.info(f"Testing agent with video: {video_path}")
    
    try:
        # Process the video with our agent
        analysis = await process_video_with_agent(video_path)
        
        # Print the results
        logger.info(f"Analysis complete. Found {len(analysis.highlights)} highlights")
        
        for i, highlight in enumerate(analysis.highlights, 1):
            logger.info(f"Highlight {i}:")
            logger.info(f"  Time: {highlight.start_time:.2f}s - {highlight.end_time:.2f}s")
            logger.info(f"  Description: {highlight.clip_description}")
        
        # Save the analysis to a JSON file
        output_file = f"{os.path.splitext(video_path)[0]}_analysis.json"
        with open(output_file, 'w') as f:
            json.dump(analysis.model_dump(), f, indent=2, default=str)
        
        logger.success(f"Analysis saved to {output_file}")
        return 0
        
    except Exception as e:
        logger.exception(f"Error testing agent: {e}")
        return 1


def main():
    """Entry point that runs the async main function"""
    return asyncio.run(async_main())


if __name__ == "__main__":
    exit(main()) 