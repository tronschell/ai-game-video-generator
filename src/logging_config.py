import logging
import os
from pathlib import Path
import sys
from datetime import datetime

def setup_logging():
    """Set up logging configuration for all modules"""
    try:
        # Create logs directory if it doesn't exist
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Create dated log filename
        current_date = datetime.now().strftime('%Y-%m-%d')
        log_filename = f'app_{current_date}.log'
        log_file = log_dir / log_filename
        
        # Clear any existing handlers to avoid duplication
        root = logging.getLogger()
        if root.handlers:
            for handler in root.handlers:
                root.removeHandler(handler)
        
        # Create formatters with microsecond precision
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create and configure file handler
        file_handler = logging.FileHandler(str(log_file), mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        
        # Create and configure console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        
        # Configure the root logger
        root.setLevel(logging.INFO)
        root.addHandler(file_handler)
        root.addHandler(console_handler)
        
        # Test log file writing
        root.info(f"Logging system initialized - Writing to {log_file}")
        
        return root
        
    except Exception as e:
        print(f"Error setting up logging: {str(e)}", file=sys.stderr)
        raise

# Create a logger for this module
logger = logging.getLogger(__name__) 