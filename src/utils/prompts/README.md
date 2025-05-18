# Switchable Game Prompts

This directory contains prompt templates for different games that can be used for analyzing gameplay videos.

## Available Game Prompts

- `cs2.py` - Counter-Strike 2
- `overwatch2.py` - Overwatch 2
- `the_finals.py` - The Finals
- `league_of_legends.py` - League of Legends
- `custom.py` - General-purpose template for any game

## How to Use

1. Open `config.json` in the root directory
2. Set the `game_type` field to one of the supported values:
   - `"cs2"` - Counter-Strike 2
   - `"overwatch2"` - Overwatch 2
   - `"the_finals"` - The Finals
   - `"league_of_legends"` - League of Legends
   - `"custom"` - General-purpose template

Example:
```json
{
  "game_type": "overwatch2",
  "username": "your_username",
  "min_highlight_duration_seconds": 15
  // other config options...
}
```

## Creating a Custom Prompt

To create a prompt for a new game:

1. Create a new Python file in the `src/prompts` directory (e.g., `valorant.py`)
2. Define a `HIGHLIGHT_PROMPT` template variable using `string.Template`
3. Include `${username}` and `${min_highlight_duration_seconds}` variables in your template
4. Add the new prompt to `__init__.py`:
   - Import your new prompt
   - Add it to the `GameType` Literal type definition
   - Add it to the `PROMPT_TEMPLATES` dictionary
5. Update your `config.json` to use the new game type

### Example: Adding a Valorant Prompt

1. Create `src/prompts/valorant.py`:
```python
from string import Template

HIGHLIGHT_PROMPT = Template('''
    Analyze the provided Valorant gameplay clip to identify highlight moments featuring player "${username}".
    
    # Your prompt content here
    # Make sure to include ${username} and ${min_highlight_duration_seconds} variables
''')
```

2. Update `src/prompts/__init__.py`:
```python
# Add import
from .valorant import HIGHLIGHT_PROMPT as VALORANT_PROMPT

# Update GameType
GameType = Literal["cs2", "overwatch2", "the_finals", "league_of_legends", "custom", "valorant"]

# Add to templates dictionary
PROMPT_TEMPLATES: Dict[GameType, Template] = {
    "cs2": CS2_PROMPT,
    "overwatch2": OVERWATCH2_PROMPT,
    "the_finals": THE_FINALS_PROMPT,
    "league_of_legends": LOL_PROMPT,
    "custom": CUSTOM_PROMPT,
    "valorant": VALORANT_PROMPT
}
```

3. Update `config.json`:
```json
{
  "game_type": "valorant",
  // other config options...
}
```

## Important Notes

- Each prompt template must follow the same output format (JSON list of highlight objects)
- The template variables `${username}` and `${min_highlight_duration_seconds}` are required
- Game-specific templates should include instructions tailored to the specific game UI and gameplay mechanics 