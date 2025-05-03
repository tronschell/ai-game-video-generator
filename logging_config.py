import os
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger


def setup_logging(log_file: str = None) -> None:
    """Configure logging for the application"""
    # Remove default logger
    logger.remove()
    
    # Set up console logger
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Set up file logger if specified
    if log_file is None:
        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"highlight_generator_{timestamp}.log"
    
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="1 week"
    )
    
    logger.info(f"Logging initialized. Log file: {log_file}") 