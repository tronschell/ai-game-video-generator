import os
import json
import logging
import asyncio
import csv
from typing import List, Dict, Any, Tuple, Optional
import dotenv
from google import genai
from google.genai import types
from google.genai.types import GenerateContentConfig
from pathlib import Path
from functools import partial
from delete_files import FileDeleter
from config import Config
from prompts import CS2_HIGHLIGHT_PROMPT

# Get module-specific logger
logger = logging.getLogger(__name__)

# Stores the current prompt cache reference
_prompt_cache = None

# Gemini API pricing per model (USD per 1M tokens)
GEMINI_PRICING = {
    # Gemini 2.5 Flash Preview
    "gemini-2.5-flash-preview": {
        "input": {"text": 0.15, "image": 0.15, "video": 0.15, "audio": 1.00},
        "output": {"non_thinking": 0.60, "thinking": 3.50}
    },
    # Gemini 2.5 Pro Preview
    "gemini-2.5-pro-preview": {
        "input": {
            "text": {"<=200k": 1.25, ">200k": 2.50},
            "image": {"<=200k": 1.25, ">200k": 2.50},
            "video": {"<=200k": 1.25, ">200k": 2.50},
            "audio": {"<=200k": 1.25, ">200k": 2.50}
        },
        "output": {"<=200k": 10.00, ">200k": 15.00}
    },
    # Gemini 2.0 Flash
    "gemini-2.0-flash": {
        "input": {"text": 0.10, "image": 0.10, "video": 0.10, "audio": 0.70},
        "output": {"default": 0.40}
    },
    # Default pricing if model not found
    "default": {
        "input": {"text": 0.10, "image": 0.10, "video": 0.10, "audio": 0.70},
        "output": {"default": 0.40}
    }
}

def get_model_pricing(model_name: str) -> Dict[str, Any]:
    """Get pricing for a specific model, falling back to default if not found."""
    # Try to match the model name with known pricing
    for pricing_key in GEMINI_PRICING:
        if pricing_key in model_name.lower():
            return GEMINI_PRICING[pricing_key]
    return GEMINI_PRICING["default"]

def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> float:
    """Calculate cost based on model-specific pricing."""
    pricing = get_model_pricing(model_name)
    
    # Calculate input cost (video input)
    input_tokens = prompt_tokens - cached_tokens
    input_cost = 0
    
    if "gemini-2.5-pro-preview" in model_name.lower():
        # Pro preview has different pricing based on token count
        if input_tokens <= 200000:
            input_cost = (input_tokens / 1000000) * pricing["input"]["video"]["<=200k"]
        else:
            input_cost = (input_tokens / 1000000) * pricing["input"]["video"][">200k"]
            
        # Output cost also varies based on token count
        if completion_tokens <= 200000:
            output_cost = (completion_tokens / 1000000) * pricing["output"]["<=200k"]
        else:
            output_cost = (completion_tokens / 1000000) * pricing["output"][">200k"]
    else:
        # Standard pricing for other models
        input_cost = (input_tokens / 1000000) * pricing["input"]["video"]
        
        # For Flash preview, check if thinking is enabled (assuming non-thinking by default)
        if "gemini-2.5-flash-preview" in model_name.lower():
            output_cost = (completion_tokens / 1000000) * pricing["output"]["non_thinking"]
        else:
            output_cost = (completion_tokens / 1000000) * pricing["output"]["default"]
    
    return input_cost + output_cost

async def get_or_create_prompt_cache(client, config: Config) -> Optional[str]:
    """Get or create a cache for the prompt template."""
    global _prompt_cache
    
    if not config.use_caching:
        return None
        
    if _prompt_cache:
        try:
            # Check if cache still exists and is valid
            cache = client.caches.get(name=_prompt_cache)
            return _prompt_cache
        except Exception as e:
            logger.debug(f"Cached prompt no longer valid: {str(e)}")
            _prompt_cache = None
    
    # Create a new cache for the prompt
    try:
        prompt = CS2_HIGHLIGHT_PROMPT.substitute(
            min_highlight_duration_seconds=config.min_highlight_duration_seconds,
            username=config.username
        )
        
        cache = client.caches.create(
            model=config.model_name,
            config=types.CreateCachedContentConfig(
                display_name=f"cs2_highlight_prompt_{config.username}",
                system_instruction="",
                contents=[prompt],
                ttl=f"{config.cache_ttl_seconds}s"
            )
        )
        _prompt_cache = cache.name
        logger.info(f"Created new prompt cache with TTL of {config.cache_ttl_seconds}s")
        return _prompt_cache
    except Exception as e:
        logger.error(f"Failed to create prompt cache: {str(e)}")
        return None

async def analyze_videos_batch(video_paths: List[str], output_file: str = "highlights.json", batch_size: int = 10, prompt_template=CS2_HIGHLIGHT_PROMPT, token_cost_file: str = "token_costs.csv") -> List[Tuple[str, List[Dict[str, Any]]]]:
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
    token_usage = []  # Track token usage for each video

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
                        token_usage.append({"video": video_path, "status": "failed", "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0})
                    else:
                        if isinstance(result, tuple) and len(result) == 2:
                            highlights, usage = result
                            results.append((video_path, highlights))
                            token_usage.append(usage)
                        else:
                            results.append((video_path, result))
                            logger.warning(f"No token usage data for {video_path}")
                            token_usage.append({"video": video_path, "status": "no_tokens", "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0})

                logger.info(f"✓ Completed batch {i//batch_size + 1}")

            except Exception as e:
                logger.error(f"Error processing batch: {str(e)}")
                # Add empty results for failed batch
                for video_path in batch:
                    results.append((video_path, []))
                    logger.error(f"Failed to process {video_path} in batch")

    finally:
        # Cleanup: Delete all files from Google Files API
        try:
            logger.info("Cleaning up temporary API files...")
            file_deleter = FileDeleter(api_key=api_key)
            file_deleter.delete_all_files()
            logger.info("✓ Cleanup complete")
        except Exception as e:
            logger.error(f"Failed to cleanup files from Google Files API: {str(e)}")
        
        # Save token usage data to file
        try:
            # Calculate total cost
            total_prompt_tokens = sum(item.get("prompt_tokens", 0) for item in token_usage)
            total_completion_tokens = sum(item.get("completion_tokens", 0) for item in token_usage)
            total_tokens = total_prompt_tokens + total_completion_tokens
            total_cost = sum(item.get("cost", 0) for item in token_usage)
            
            # Add summary row
            token_usage.append({
                "video": "TOTAL",
                "status": "summary",
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
                "cost": total_cost
            })
            
            with open(token_cost_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=["video", "status", "prompt_tokens", "completion_tokens", "total_tokens", "cost"])
                writer.writeheader()
                writer.writerows(token_usage)
            logger.info(f"✓ Token usage saved to {token_cost_file}")
            logger.info(f"Total tokens: {total_tokens} (Input: {total_prompt_tokens}, Output: {total_completion_tokens})")
            logger.info(f"Estimated cost: ${total_cost:.4f}")
        except Exception as e:
            logger.error(f"Failed to save token usage data: {str(e)}")

    return results

async def analyze_video(video_path: str, output_file: str = "highlights.json", prompt_template=CS2_HIGHLIGHT_PROMPT) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
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
        
        # Get or create prompt cache if enabled
        prompt_cache = await get_or_create_prompt_cache(client, config)

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

                    # Generate content config
                    config_gen = GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=highlight_schema,
                        temperature=config.temperature
                    )
                    
                    # Use cache if available
                    if prompt_cache:
                        config_gen.cached_content = prompt_cache
                        
                        # Create content parts with just the video
                        contents = [video_file]
                        logger.debug("Using cached prompt")
                    else:
                        # Generate the prompt using the template
                        prompt = prompt_template.substitute(
                            min_highlight_duration_seconds=config.min_highlight_duration_seconds,
                            username=config.username
                        )
                        
                        # Create content parts using the uploaded file and prompt
                        contents = [video_file, prompt]
                        logger.debug("Using standard prompt (caching disabled)")

                    # Count tokens before generating content
                    token_count = await loop.run_in_executor(
                        None,
                        partial(
                            client.models.count_tokens,
                            model=config.model_name,
                            contents=contents
                        )
                    )
                    prompt_tokens = token_count.total_tokens
                    logger.debug(f"Prompt token count: {prompt_tokens}")
            
                    # Generate content
                    response = await loop.run_in_executor(
                        None,
                        partial(
                            client.models.generate_content,
                            model=config.model_name,
                            contents=contents,
                            config=config_gen
                        )
                    )
            
                    # Get token usage from response
                    completion_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
                    cached_tokens = getattr(response.usage_metadata, 'cached_content_token_count', 0) if response.usage_metadata else 0
                    total_tokens = prompt_tokens + (completion_tokens or 0)
                    
                    if cached_tokens:
                        logger.info(f"Cached tokens used: {cached_tokens}")
            
                    # Calculate cost based on Gemini API pricing
                    total_cost = calculate_cost(
                        config.model_name,
                        prompt_tokens or 0,
                        completion_tokens or 0,
                        cached_tokens or 0
                    )
            
                    logger.debug(f"Token usage - Input: {prompt_tokens}, Cached: {cached_tokens}, Output: {completion_tokens}, Total: {total_tokens}")
                    logger.debug(f"Estimated cost: ${total_cost:.6f}")

                    logger.debug("Successfully received response from Gemini API")
                    break

                except Exception as e:
                    if "FAILED_PRECONDITION" in str(e) and attempt < config.max_retries - 1:
                        logger.debug(f"File processing in progress, retry {attempt + 1}/{config.max_retries} in {retry_delay:.1f}s")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                        continue
                    raise  # Re-raise the exception if it's not a precondition error or we're out of retries

            # Extract response parts
            if not response.candidates or not response.candidates[0].content:
                raise ValueError("Empty response from API")
                
            try:
                response_json = json.loads(response.candidates[0].content.parts[0].text)
            except (json.JSONDecodeError, AttributeError, IndexError) as e:
                raise ValueError(f"Failed to parse API response as JSON: {str(e)}")

            if not isinstance(response_json, dict) or "highlights" not in response_json:
                raise ValueError("Invalid response format from API")

            # Process highlights (rest of the function remains unchanged)
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

                # Write updated data back to file
                with open(output_file, 'w') as f:
                    json.dump(existing_data, f, indent=2)

                logger.info(f"✓ Found {len(processed_highlights)} highlights in {os.path.basename(video_path)}")
            
            # Create token usage data
            token_data = {
                "video": video_path,
                "status": "success",
                "prompt_tokens": (prompt_tokens or 0) - (cached_tokens or 0),  # Only count non-cached tokens
                "completion_tokens": completion_tokens or 0,
                "total_tokens": (total_tokens or 0) - (cached_tokens or 0),  # Adjust total for cached tokens
                "cost": total_cost or 0.0
            }

            return processed_highlights, token_data

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse API response as JSON: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error during API call or response processing: {str(e)}")

    except FileNotFoundError as e:
        logger.error(str(e))
        token_data = {"video": video_path, "status": "error", "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0}
        raise
    except ValueError as e:
        logger.error(str(e))
        token_data = {"video": video_path, "status": "error", "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0}
        raise
    except Exception as e:
        logger.error(f"Unexpected error analyzing video {video_path}: {str(e)}")
        token_data = {"video": video_path, "status": "error", "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0}
        raise

def analyze_videos_sync(video_paths: List[str], output_file: str = "highlights.json", batch_size: int = None, prompt_template=CS2_HIGHLIGHT_PROMPT, token_cost_file: str = "token_costs.csv") -> List[Tuple[str, List[Dict[str, Any]]]]:
    """
    Synchronous wrapper for analyze_videos_batch

    Args:
        video_paths: List of paths to video files
        output_file: Path to the JSON file where highlights will be saved
        batch_size: Number of videos to process concurrently
        prompt_template: Template string for the analysis prompt
        token_cost_file: Path to the CSV file where token costs will be saved

    Returns:
        List of tuples containing (video_path, highlights)
    """
    return asyncio.run(analyze_videos_batch(video_paths, output_file, batch_size, prompt_template, token_cost_file))

def analyze_video_sync(video_path: str, output_file: str = "highlights.json", prompt_template=CS2_HIGHLIGHT_PROMPT, token_cost_file: str = "token_costs.csv") -> List[Dict[str, Any]]:
    """
    Synchronous wrapper for analyze_video

    Args:
        video_path: Path to the video file to analyze
        output_file: Path to the JSON file where highlights will be saved
        prompt_template: Template string for the analysis prompt
        token_cost_file: Path to the CSV file where token costs will be saved

    Returns:
        List of highlights
    """
    results = analyze_videos_sync([video_path], output_file, prompt_template=prompt_template, token_cost_file=token_cost_file)
    return results[0][1] if results else []
