# Game Highlight Generator 🎮

An intelligent highlight generator for Counter-Strike 2 gameplay videos that automatically identifies and compiles your best moments using Google's Gemini AI.

## 🌟 Features

- **Smart Highlight Detection**: Uses Google Gemini Flash 2.5 to identify:
  - Clutch moments (1vX situations)
  - Impressive kills and multi-kills
  - Emotional reactions and key moments
- **Batch Processing**: Efficiently processes multiple video files concurrently
- **Automatic Compilation**: Combines highlights into a single, well-edited video
- **Smart Filtering**: Only includes highlights from your gameplay (username: "i have no enemies")
- **Context-Aware**: Analyzes round context to ensure meaningful highlights
- **Automatic Cleanup**: Manages temporary files and API resources
- **Clip Tracking**: Maintains a history of used clips to prevent duplicates in future compilations

## 🛠️ Prerequisites

- Python 3.8 or higher
- FFmpeg installed and available in your system PATH
- Google API key for Gemini AI
- Gameplay recordings, defaulting to Counter Strike 2 but can work with any game.

## 📦 Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd video-highlight-generator
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```

3. Install the package in editable mode:
   ```bash
   pip install -e .
   ```

4. Create a `.env` file in the project root:
   ```
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

## 🚀 Usage

### Basic Usage

```bash
python main.py /path/to/clips/folder
```

The script will:
1. Process the 25 most recent video clips in the specified folder
2. Analyze each clip for highlight-worthy moments
3. Check for and skip any previously used clips
4. Generate a compilation video with the best unused moments

### Output Files

- `highlights.json`: Contains metadata about detected highlights
- `highlights_[timestamp].mp4`: The final compiled highlight video
- `used_clips.json`: Tracks which clips have been used in previous compilations
- Log files in the `logs/` directory
- Temporary files in `temp_segments/` (automatically cleaned up)
- Final videos in `exported_videos/` directory

## 🔧 Project Structure

- `main.py`: Entry point and orchestration
- `video_analysis.py`: Video analysis using Gemini AI
- `video_concatenator.py`: Video compilation utilities with clip tracking
- `delete_files.py`: Cleanup utilities
- `logging_config.py`: Logging configuration

### config.json
The following parameters can be customized in `config.json`:

- `batch_size`: Number of clips to process concurrently (default: 10)
- `model_name`: Gemini model version to use (default: "gemini-2.5-flash-preview-04-17")
- `max_retries`: Maximum API retry attempts (default: 14)
- `retry_delay_seconds`: Delay between retries in seconds (default: 2)
- `min_highlight_duration_seconds`: Minimum duration for a highlight clip (default: 15)
- `username`: Your in-game username for highlight detection (default: "i have no enemies")
- `max_clips`: Maximum number of clips to process in one session (default: 25)

### Customizing Prompts
The analysis prompts can be customized in `src/prompts.py`. The main prompt template (`CS2_HIGHLIGHT_PROMPT`) defines:

- Timestamp requirements and formatting
- Highlight criteria for clip selection
- Exclusion criteria
- Example highlight formats

You can modify these criteria to better suit your needs while maintaining the required timestamp format and structure.

## 📝 Notes

- Videos must be in MP4 format for compatibility with Gemini AI
- The system identifies highlights based on your username "i have no enemies" in the kill feed
- Kill feed entries with thin red outlines are included, while fully red highlights are excluded
- Previously used clips are tracked in `used_clips.json` to prevent duplicates
- The `exported_videos` directory contains all final compilations

## 🤝 Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.
