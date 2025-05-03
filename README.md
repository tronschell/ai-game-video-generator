# CS2 Highlight Generator

This application analyzes CS2 gameplay videos to extract highlight clips and compile them into a single highlight video.

## Features

- Automatically scans a folder for gameplay clips
- Uses Google Gemini Flash 2.5 to analyze videos for clutch moments, cool kills, and reactions
- Compiles identified highlights into a single video
- Tracks processed clips in a SQLite database to avoid duplication

## Installation

1. Clone this repository
2. Install requirements:
   ```
   pip install -e .
   ```
3. Make sure you have FFmpeg installed and available in your PATH

## Usage

```bash
# Default usage - processes clips from default folder
highlight-generator

# Specify a custom clips folder
highlight-generator --clips-folder "path/to/clips"

# Specify output video length (in minutes)
highlight-generator --output-length 15

# Custom output filename
highlight-generator --output-filename "my-highlights.mp4"

# Force include previously used clips
highlight-generator --include-used-clips

# Create a thumbnail from the compiled video
highlight-generator --create-thumbnail

# Limit analysis to a specific number of clips
highlight-generator --max-clips 5
```

## Requirements

- Python 3.8+
- FFMPEG
- Google ADK

## How It Works

1. The application scans the specified folder for video files
2. Each video is analyzed by a Google Gemini Flash 2.5 agent to identify highlights
3. The agent identifies clutch moments, cool kills, and excited reactions
4. Analysis results are stored in a SQLite database and as JSON files
5. The application selects highlights to compile into a video of the desired length
6. FFMPEG is used to concatenate the highlight segments into a single video

## Output

The application generates several files:
- The compiled highlight video (default: output{MM-DD-YYYY}.mp4)
- A JSON file for each analyzed clip ({clip_name}_analysis.json)
- A compilation plan JSON file (compilation_plan_{timestamp}.json)
- Log files in the logs/ directory
