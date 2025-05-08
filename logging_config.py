import os
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger


def http_filter(record):
    """Filter out verbose HTTP logs but keep errors and important messages"""
    message = record["message"].lower()
    if any(x in message for x in ["https", "api", "request", "response", "post", "googleapis", "AFC is enabled"]):
        # Only show errors and important status messages
        return record["level"].no >= logger.level("ERROR").no or \
               any(x in message for x in ["successfully", "error", "failed", "complete"])
    return True


def setup_logging(log_file: str = None) -> None:
    """Configure logging for the application"""
    # Remove default logger
    logger.remove()

    # Set up console logger with filter
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        filter=http_filter
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
        retention="1 week",
        filter=http_filter
    )

    logger.info(f"Logging initialized. Log file: {log_file}")
