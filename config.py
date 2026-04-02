import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
CHECKPOINT_DIR = BASE_DIR / "checkpoints"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
CHECKPOINT_DIR.mkdir(exist_ok=True)

# File paths
URLS_FILE = DATA_DIR / "candidate_urls.txt"  # Your 8,163 URLs
OUTPUT_FILE = DATA_DIR / "drugs_data.json"
CHECKPOINT_FILE = CHECKPOINT_DIR / "checkpoint.json"
LOG_FILE = LOGS_DIR / "scraper.log"

# HTTP Configuration
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
INITIAL_BACKOFF = 1  # seconds
MAX_BACKOFF = 60     # seconds

# Request Configuration
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
DEFAULT_BATCH_SIZE = 50
DEFAULT_REQUEST_DELAY = 1.5  # seconds between requests

# Parsing Configuration
REQUIRED_FIELDS = {
    'drug_name',
    'url',
    'drug_class',
    'generic_name',
    'brand_names',
    'related_conditions'
}

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Feature flags
RESUME_ON_STARTUP = True
INCREMENTAL_SAVE = True
SAVE_INTERVAL = 50  # Save every N batches