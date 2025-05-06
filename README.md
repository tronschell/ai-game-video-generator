# 🎮 Game Highlight Generator

<div align="center">

![Version](https://img.shields.io/badge/version-1.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-brightgreen)

</div>

> AI-powered highlight generator for Counter-Strike 2 that automatically identifies and compiles your best gameplay moments using Google's Gemini AI.

<p align="center">
  <img src="https://img.shields.io/badge/Powered%20by-Gemini%20AI-blue?style=for-the-badge&logo=google&logoColor=white" alt="Powered by Gemini AI">
</p>

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🤖 **Smart Detection** | Uses Gemini Flash 2.5 Thinking to identify clutch moments, multi-kills, and emotional reactions |
| ⚡ **Parallel Processing** | Efficiently analyzes multiple clips concurrently |
| 🎬 **Auto Compilation** | Creates a single, well-edited highlight video |
| 🔍 **Smart Filtering** | Only includes highlights from your gameplay (configurable username) |
| 🧠 **Context Awareness** | Understands game state and round context for meaningful clips |
| 🧹 **Auto Resource Management** | Handles temp files and API resources efficiently |
| 🔄 **Duplicate Prevention** | Tracks previously used clips to avoid repetition |

## 📋 Prerequisites

- Python 3.8+
- FFmpeg (installed and in PATH)
- Google API key for Gemini AI
- Gameplay recordings (optimized for CS2, works with other games)

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd video-creation-agent

# Set up virtual environment
python -m venv .venv

# Activate virtual environment
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# Install dependencies
pip install -e .

# Configure API key
echo "GOOGLE_API_KEY=your_gemini_api_key_here" > .env
```

### Basic Usage

```bash
python main.py /path/to/clips/folder
```

The generator will:
1. Process up to 25 recent video clips (configurable)
2. Intelligently identify highlight-worthy moments
3. Skip any previously used clips
4. Create a compilation with your best moments

## 📂 Project Structure

```
.
├── main.py                 # Entry point script
├── config.json             # Configuration settings
├── src/
│   ├── video_analysis.py   # Gemini AI video analysis
│   ├── video_concatenator.py # Clip compilation
│   ├── prompts.py          # Analysis prompt templates
│   ├── delete_files.py     # Cleanup utilities
│   └── logging_config.py   # Logging setup
├── exported_videos/        # Final highlight compilations
├── logs/                   # Log files
└── temp_segments/          # Temporary processing files
```

## ⚙️ Configuration

Edit `config.json` to customize behavior:

```json
{
  "batch_size": 10,
  "model_name": "gemini-2.5-flash-preview-04-17",
  "max_retries": 14,
  "retry_delay_seconds": 2,
  "min_highlight_duration_seconds": 15,
  "username": "i have no enemies",
  "max_clips": 25,
  "allow_clip_reuse": false
}
```

## 🛠️ Advanced Usage

### Customizing Highlight Detection

The analysis prompts in `src/prompts.py` can be customized to define:

- Different highlight criteria for your specific game
- Custom timestamp formats
- Game-specific detection rules

### Output Files

| File | Purpose |
|------|---------|
| `highlights.json` | Metadata about detected highlights |
| `highlights_[timestamp].mp4` | Final compiled highlight video |
| `used_clips.json` | History of previously used clips |
| `logs/*.log` | Detailed operation logs |

## 📝 Important Notes

- Videos should be in MP4 format for Gemini AI compatibility
- Default username for highlight detection is "i have no enemies" (configurable)
- Kill feed entries with thin red outlines are included in analysis
- Previously used clips are tracked to prevent duplicates

## 🤝 Contributing

Contributions are welcome! Feel free to submit issues, fork the repository, and create pull requests.

---

<div align="center">
  Made with ❤️ for gamers who want to showcase their best moments
</div>
