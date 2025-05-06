import os
import logging
import dotenv
from google import genai
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FileDeleter:
    def __init__(self, api_key: str):
        """Initialize the FileDeleter with Google API credentials."""
        self.client = genai.Client(api_key=api_key)
        
    def delete_all_files(self) -> None:
        """Delete all files from Google Files API."""
        try:
            # Get list of all files
            files = list(self.client.files.list())
            total_files = len(files)
            logger.info(f"Found {total_files} files to delete")
            
            # Delete each file
            for i, file in enumerate(files, 1):
                try:
                    self.client.files.delete(name=file.name)
                    logger.info(f"Deleted file {i}/{total_files}: {file.name}")
                except Exception as e:
                    logger.error(f"Failed to delete file {file.name}: {str(e)}")
                    
            logger.info("File deletion process completed")
            
        except Exception as e:
            logger.error(f"An error occurred while deleting files: {str(e)}")
            raise

def main():
    """Main function to run the file deletion process."""

    dotenv.load_dotenv()
    # Get the API key from the environment variable
    API_KEY = os.getenv("GOOGLE_API_KEY")
    
    try:
        deleter = FileDeleter(api_key=API_KEY)
        deleter.delete_all_files()
    except Exception as e:
        logger.error(f"Failed to complete file deletion process: {str(e)}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main()) 