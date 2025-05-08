import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Tuple
import dotenv
from google import genai
from google.genai import types
from google.genai.types import GenerateContentConfig
from pathlib import Path
from functools import partial
from delete_files import FileDeleter
from config import Config
from prompts import CS2_HIGHLIGHT_PROMPT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def analyze_videos_batch(video_paths: List[str], output_file: str = "highlights.json", batch_size: int = 10, prompt_template=CS2_HIGHLIGHT_PROMPT) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """
    Analyze multiple videos in batches using Gemini.

    Args:
        video_paths: List of paths to video files
        output_file: Path to the JSON file where highlights will be saved
        batch_size: Number of videos to process concurrently
        prompt_template: Template string for the analysis prompt

    Returns:
        List of tuples containing (video_path, highlights)
    """
    config = Config()
    batch_size = batch_size or config.batch_size

    results = []

    # Get API key once for both analysis and cleanup
    dotenv.load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables")

    try:
        # Process videos in batches
        for i in range(0, len(video_paths), batch_size):
            batch = video_paths[i:i + batch_size]
            logger.info(f"Processing video batch {i//batch_size + 1} ({len(batch)} videos)")

            # Process batch concurrently
            try:
                batch_results = await asyncio.gather(
                    *(analyze_video(video_path, output_file, prompt_template) for video_path in batch),
                    return_exceptions=True
                )

                # Handle results and any exceptions
                for video_path, result in zip(batch, batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"Failed to process {video_path}: {str(result)}")
                        results.append((video_path, []))
                    else:
                        results.append((video_path, result))

                logger.info(f"✓ Completed batch {i//batch_size + 1}")

            except Exception as e:
                logger.error(f"Error processing batch: {str(e)}")
                # Add empty results for failed batch
                for video_path in batch:
                    results.append((video_path, []))

    finally:
        # Cleanup: Delete all files from Google Files API
        try:
            logger.info("Cleaning up temporary API files...")
            file_deleter = FileDeleter(api_key=api_key)
            file_deleter.delete_all_files()
            logger.info("✓ Cleanup complete")
        except Exception as e:
            logger.error(f"Failed to cleanup files from Google Files API: {str(e)}")

    return results

async def analyze_video(video_path: str, output_file: str = "highlights.json", prompt_template=CS2_HIGHLIGHT_PROMPT) -> List[Dict[str, Any]]:
    """
    Analyze a video file using Gemini and append results to JSON file

    Args:
        video_path: Path to the video file to analyze
        output_file: Path to the JSON file where highlights will be saved
        prompt_template: Template string for the analysis prompt
    """
    config = Config()

    try:
        # Validate video file
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Check if it's actually a video file (Gemini supports MP4)
        if not video_path.lower().endswith('.mp4'):
            raise ValueError(f"File must be in MP4 format for best compatibility with Gemini")

        logger.info(f"Analyzing video: {os.path.basename(video_path)}")

        # Initialize Gemini client
        dotenv.load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")

        client = genai.Client(api_key=api_key)

        try:
            # Upload the video file using a thread pool to not block
            logger.debug("Uploading video to API...")
            loop = asyncio.get_event_loop()
            video_file = await loop.run_in_executor(
                None,
                partial(client.files.upload, file=Path(video_path))
            )

            # Wait for file to be processed
            retry_delay = config.retry_delay_seconds

            for attempt in range(config.max_retries):
                try:
                    # Define the schema for structured output with seconds format
                    highlight_schema = {
                        "type": "object",
                        "properties": {
                            "highlights": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "timestamp_start_seconds": {"type": "integer", "minimum": 0},
                                        "timestamp_end_seconds": {"type": "integer", "minimum": 0},
                                        "clip_description": {"type": "string"}
                                    },
                                    "required": ["timestamp_start_seconds", "timestamp_end_seconds", "clip_description"]
                                }
                            }
                        },
                        "required": ["highlights"]
                    }

                    # Generate the prompt using the template
                    prompt = prompt_template.substitute(
                        min_highlight_duration_seconds=config.min_highlight_duration_seconds,
                        username=config.username
                    )

                    # Configure the generation
                    config_gen = GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=highlight_schema,
                        thinking_config=types.ThinkingConfig(thinking_budget=10000),
                        temperature=config.temperature
                    )

                    # Create content parts using the uploaded file
                    contents = [
                        video_file,
                        prompt
                    ]

                    # Generate content using thread pool to not block
                    response = await loop.run_in_executor(
                        None,
                        partial(
                            client.models.generate_content,
                            model=config.model_name,
                            contents=contents,
                            config=config_gen
                        )
                    )

                    logger.debug("Successfully received response from Gemini API")
                    break

                except Exception as e:
                    if "FAILED_PRECONDITION" in str(e) and attempt < config.max_retries - 1:
                        logger.debug(f"File processing in progress, retry {attempt + 1}/{config.max_retries} in {retry_delay:.1f}s")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                        continue
                    raise  # Re-raise the exception if it's not a precondition error or we're out of retries

            response_json = json.loads(response.text)

            if not isinstance(response_json, dict) or "highlights" not in response_json:
                raise ValueError("Invalid response format from API")

            # Add source video path to each highlight
            processed_highlights = []
            for highlight in response_json["highlights"]:
                processed_highlight = {
                    "source_video": str(video_path),
                    "timestamp_start_seconds": highlight["timestamp_start_seconds"],
                    "timestamp_end_seconds": highlight["timestamp_end_seconds"],
                    "clip_description": highlight["clip_description"]
                }
                processed_highlights.append(processed_highlight)

            # Save to file if output_file is specified
            if output_file:
                os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

                # Initialize file if it doesn't exist
                if not os.path.exists(output_file):
                    with open(output_file, 'w') as f:
                        json.dump({"highlights": []}, f)

                # Read existing data
                with open(output_file, 'r') as f:
                    existing_data = json.load(f)

                # Append new highlights
                existing_data["highlights"].extend(processed_highlights)

                with open(output_file, 'w') as f:
                    json.dump(existing_data, f, indent=2)

                logger.info(f"✓ Found {len(processed_highlights)} highlights in {os.path.basename(video_path)}")

            return processed_highlights

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse API response as JSON: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error during API call or response processing: {str(e)}")

    except FileNotFoundError as e:
        logger.error(str(e))
        raise
    except ValueError as e:
        logger.error(str(e))
        raise
    except Exception as e:
        logger.error(f"Unexpected error analyzing video {video_path}: {str(e)}")
        raise

def analyze_videos_sync(video_paths: List[str], output_file: str = "highlights.json", batch_size: int = None, prompt_template=CS2_HIGHLIGHT_PROMPT) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """
    Synchronous wrapper for analyze_videos_batch

    Args:
        video_paths: List of paths to video files
        output_file: Path to the JSON file where highlights will be saved
        batch_size: Number of videos to process concurrently
        prompt_template: Template string for the analysis prompt

    Returns:
        List of tuples containing (video_path, highlights)
    """
    return asyncio.run(analyze_videos_batch(video_paths, output_file, batch_size, prompt_template))

def analyze_video_sync(video_path: str, output_file: str = "highlights.json", prompt_template=CS2_HIGHLIGHT_PROMPT) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper for analyze_video

    Args:
        video_path: Path to the video file to analyze
        output_file: Path to the JSON file where highlights will be saved
        prompt_template: Template string for the analysis prompt

    Returns:
        List of highlights
    """
    results = analyze_videos_sync([video_path], output_file, prompt_template=prompt_template)
    return results[0][1] if results else []
