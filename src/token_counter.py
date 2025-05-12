import logging
from typing import Dict, Any

# Get module-specific logger
logger = logging.getLogger(__name__)

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