import logging
import requests
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