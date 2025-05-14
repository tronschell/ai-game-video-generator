import logging
from typing import Dict, Any, Literal, Optional
from string import Template

# Import all game-specific prompt templates
from .cs2 import HIGHLIGHT_PROMPT as CS2_PROMPT
from .overwatch2 import HIGHLIGHT_PROMPT as OVERWATCH2_PROMPT
from .the_finals import HIGHLIGHT_PROMPT as THE_FINALS_PROMPT
from .league_of_legends import HIGHLIGHT_PROMPT as LOL_PROMPT
from .custom import HIGHLIGHT_PROMPT as CUSTOM_PROMPT

logger = logging.getLogger(__name__)

# Define supported game types
GameType = Literal["cs2", "overwatch2", "the_finals", "league_of_legends", "custom"]

# Mapping of game types to their prompt templates
PROMPT_TEMPLATES: Dict[GameType, Template] = {
    "cs2": CS2_PROMPT,
    "overwatch2": OVERWATCH2_PROMPT,
    "the_finals": THE_FINALS_PROMPT,
    "league_of_legends": LOL_PROMPT,
    "custom": CUSTOM_PROMPT
}

def get_prompt(game_type: GameType, min_highlight_duration_seconds: int, username: str) -> str:
    """
    Get the prompt template for the specified game type and substitute variables.
    
    Args:
        game_type: The type of game prompt to use
        min_highlight_duration_seconds: Minimum duration for highlight clips
        username: Player username to look for in the videos
        
    Returns:
        String with the prompt content with variables substituted
    """
    if game_type not in PROMPT_TEMPLATES:
        logger.warning(f"Unknown game type '{game_type}', falling back to custom prompt")
        game_type = "custom"
    
    template = PROMPT_TEMPLATES[game_type]
    prompt = template.substitute(
        min_highlight_duration_seconds=min_highlight_duration_seconds,
        username=username
    )
    
    return prompt 