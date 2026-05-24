import logging
import requests
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =========================
# LOGGING
# =========================
def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    return logging.getLogger(__name__)

# =========================
# SESSION WITH RETRIES
# =========================
def create_session():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

# =========================
# PROGRESS RESET
# =========================
def reset_progress(progress_file, partial_file):
    """
    Reset progress tracking for a fresh extraction run.
    
    Args:
        progress_file (str): Path to progress.json
        partial_file (str): Path to papers_partial.csv
    
    Returns:
        bool: True if reset successful, False if nothing to reset
    """
    files_deleted = False
    
    if os.path.exists(progress_file):
        os.remove(progress_file)
        logger = logging.getLogger(__name__)
        logger.info(f"Deleted {progress_file}")
        files_deleted = True
    
    if os.path.exists(partial_file):
        os.remove(partial_file)
        logger = logging.getLogger(__name__)
        logger.info(f"Deleted {partial_file}")
        files_deleted = True
    
    return files_deleted