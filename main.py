"""
Main entry point for the School Scraper application.
Simply imports and runs the Streamlit application.
"""
import logging
from app import main

# Configure root logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)

if __name__ == "__main__":
    main()