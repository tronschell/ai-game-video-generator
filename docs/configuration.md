# Configuration Guide

This document provides details on all available configuration options for the Game Highlight Generator.

## Configuration File

The application uses a `config.json` file in the root directory to configure its behavior. Below are all the available options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `batch_size` | Integer | 25 | Number of clips to process in parallel. Higher values increase processing speed but require more system resources. |
| `model_name` | String | "gemini-2.5-flash-preview-04-17" | The Gemini AI model to use for highlight detection. Options include "gemini-2.5-flash-preview-04-17" (faster) and "gemini-2.5-pro-preview-05-06" (more accurate). |
| `max_retries` | Integer | 10 | Maximum number of retry attempts for API calls if they fail. |
| `retry_delay_seconds` | Integer | 2 | Number of seconds to wait between retry attempts. |
| `min_highlight_duration_seconds` | Integer | 10 | Minimum duration in seconds for a moment to be considered a highlight. |
| `username` | String | "i have no enemies" | Your in-game username. The system will focus on highlights featuring this player. |
| `max_clips` | Integer | 25 | Maximum number of video clips to process in a single run. |
| `allow_clip_reuse` | Boolean | false | Whether to allow reusing clips that have been included in previous highlight compilations. |
| `temperature` | Float | 1.0 | Controls the randomness of the AI model's output. Lower values make output more deterministic, higher values more creative. Range: 0.0-1.0. |
| `use_caching` | Boolean | false | Whether to cache API responses to reduce API calls for previously analyzed clips. |
| `cache_ttl_seconds` | Integer | 3600 | Time-to-live in seconds for cached API responses before they expire. |
| `skip_videos` | Integer | 0 | Number of videos to skip from the beginning of the clips directory. Useful for processing newer clips first. |
| `use_low_resolution` | Boolean | false | Process videos in lower resolution to reduce processing time and API costs. May reduce detection accuracy. |
| `clip_order` | String | "oldest_first" | Order in which to process clips. Options are "oldest_first" or "newest_first". |
| `game_type` | String | "cs2" | Type of game for prompt selection. Options include "cs2", "overwatch2", "the_finals", "league_of_legends", and "custom". |

## Example Configuration

```json
{
  "batch_size": 10,
  "model_name": "gemini-2.5-pro-preview-05-06",
  "max_retries": 14,
  "retry_delay_seconds": 2,
  "min_highlight_duration_seconds": 17,
  "username": "your_username_here",
  "max_clips": 27,
  "allow_clip_reuse": true,
  "temperature": 0.8,
  "use_caching": false,
  "cache_ttl_seconds": 3600,
  "skip_videos": 0,
  "use_low_resolution": true,
  "clip_order": "newest_first",
  "game_type": "cs2"
}
```

## Game Types

The `game_type` configuration determines which prompt template is used for video analysis:

- `cs2`: Counter-Strike 2
- `overwatch2`: Overwatch 2
- `the_finals`: The Finals
- `league_of_legends`: League of Legends
- `custom`: General-purpose template for any game

For more information on creating custom game prompts, see the [prompts documentation](../src/prompts/README.md).

## Cost Considerations

Different `model_name` options have different pricing implications:

| Model | Approximate Cost |
|-------|------------------|
| `gemini-2.5-flash-preview-04-17` | About $0.10 per 25 video clips at 1 minute each with audio |
| `gemini-2.5-pro-preview-05-06` | About $0.80 per 25 video clips at 1 minute each with audio | 