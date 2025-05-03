import json
import os
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional

from google import genai
from google.genai import types
from dotenv import load_dotenv
from loguru import logger

from models import HighlightSegment, ClipAnalysis
from video import get_video_duration

# Load environment variables
load_dotenv()

# Initialize the Google GenerativeAI client
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable is required")

# Create the client
# client = genai.Client(api_key=api_key) # Use genai.configure instead
genai.configure(api_key=api_key)

async def analyze_video_with_gemini(video_path: str) -> Dict[str, Any]:
    """
    Analyze a CS2 gameplay video to identify highlights using Gemini model
    
    Args:
        video_path: Path to the video file
    
    Returns:
        Dictionary with highlights information
    """
    try:
        logger.info(f"Sending video to Gemini for analysis: {video_path}")
        
        # Read the video file
        # Use pathlib for better path handling
        video_file = Path(video_path)
        if not video_file.is_file():
            logger.error(f"Video file not found: {video_path}")
            return {"highlights": []}

        logger.info(f"Uploading video file: {video_path}")
        # Upload the video file using the File API for potentially better handling of large files
        # Note: This is an alternative approach; direct embedding as data might still work for smaller files
        # file_response = await genai.upload_file_async(path=video_path, mime_type="video/mp4")
        # logger.info(f"Completed video upload: {file_response.name}")
        
        # Use direct data embedding for now, as File API upload might require different handling
        with open(video_path, 'rb') as f:
            video_data = f.read()

        # Prepare the prompt
        prompt = """
        You are analyzing a Counter-Strike 2 gameplay clip. Your task is to identify highlight moments that would be interesting to include in a compilation video.

        Focus on identifying these specific types of moments:
        1. Clutch situations (1v3, 1v4, 1v5 scenarios where a single player faces multiple opponents)
        2. Impressive kills (headshots, multikills, skillful shots)
        3. Emotional reactions (indicated by loud microphone moments - these usually happen right after something exciting)

        For each identified highlight, provide:
        - start_time: When the highlight begins (in seconds)
        - end_time: When the highlight ends (in seconds)
        - clip_description: A brief description of what makes this a highlight

        Include 1-2 seconds of buffer time before and after the key moment so clips don't start/end abruptly.

        Return your response in this exact JSON format:
        {
          "highlights": [
            {
              "start_time": <start_time_in_seconds>,
              "end_time": <end_time_in_seconds>,
              "clip_description": "<description>"
            },
            ...
          ]
        }
        """
        
        # Prepare GenerationConfig
        generation_config = types.GenerationConfig(
            temperature=0.3,
            max_output_tokens=2048,
            response_mime_type="application/json" # Request JSON directly
        )

        # Select the model
        model = genai.GenerativeModel(model_name='models/gemini-1.5-flash-latest') # Using the recommended model name format

        # Make the API call using the correct format
        logger.info("Generating content with Gemini...")
        response = await model.generate_content_async(
            contents=[
                prompt, # Text part
                types.Part.from_data(mime_type="video/mp4", data=video_data) # Video part using types.Part
            ],
            generation_config=generation_config,
        )
        
        # Parse response - assuming response_mime_type="application/json" works
        # The response object itself might directly contain the parsed JSON if the model respects the mime type
        try:
            # Check if parts contain the JSON directly
            if response.parts:
                 # Accessing the text attribute which should contain the JSON string if response_mime_type is honored
                 # The SDK might automatically parse it if response_mime_type is set, check response structure
                 # Assuming response.text holds the JSON string based on typical behavior
                 json_str = response.text
                 result = json.loads(json_str)
                 logger.info(f"Successfully parsed JSON from response, found {len(result.get('highlights', []))} highlights")
                 return result
            else:
                 logger.warning("Response did not contain parts as expected. Trying response.text.")
                 # Fallback to parsing response.text if parts are empty
                 text_response = response.text
                 logger.info(f"Received text response from Gemini: {text_response[:100]}...")
                 json_start = text_response.find('{')
                 json_end = text_response.rfind('}') + 1
                 if json_start >= 0 and json_end > json_start:
                     json_str = text_response[json_start:json_end]
                     result = json.loads(json_str)
                     logger.info(f"Successfully parsed JSON from fallback text response, found {len(result.get('highlights', []))} highlights")
                     return result
                 else:
                     logger.error("No JSON found in fallback text response")
                     return {"highlights": []}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from response: {e}. Response text: {response.text}")
            return {"highlights": []}
        except AttributeError as e:
             logger.error(f"Could not access response parts or text as expected: {e}. Full response object: {response}")
             return {"highlights": []}
        except Exception as e:
            logger.error(f"Unexpected error during response parsing: {e}")
            return {"highlights": []}

    except types.generation_types.BlockedPromptException as e:
        logger.error(f"Request blocked by API: {e}")
        return {"highlights": []}
    except Exception as e:
        logger.error(f"Error analyzing video with Gemini: {e}")
        return {"highlights": []}


async def process_video_with_agent(video_path: str) -> ClipAnalysis:
    """Process a video file with the Google Gemini model"""
    logger.info(f"Processing video with Gemini: {video_path}")
    
    try:
        # Analyze video
        result = await analyze_video_with_gemini(video_path)
        
        # Convert to our internal model
        highlights = [
            HighlightSegment(
                start_time=h["start_time"],
                end_time=h["end_time"],
                clip_description=h["clip_description"]
            )
            for h in result["highlights"]
        ]
        
        # Create analysis object
        analysis = ClipAnalysis(
            highlights=highlights,
            source_path=video_path,
            total_duration=0.0  # We don't need this for highlight compilation
        )
        
        return analysis
    
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        # Return an empty analysis in case of error
        return ClipAnalysis(
            highlights=[],
            source_path=video_path,
            total_duration=0.0
        ) 