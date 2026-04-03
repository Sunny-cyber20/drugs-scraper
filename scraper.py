import argparse
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import requests
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    OUTPUT_FILE, CHECKPOINT_FILE, LOG_FILE, LOGS_DIR, URLS_FILE,
    DEFAULT_TIMEOUT, MAX_RETRIES, INITIAL_BACKOFF, MAX_BACKOFF,
    REQUEST_HEADERS, DEFAULT_BATCH_SIZE, DEFAULT_REQUEST_DELAY,
    RESUME_ON_STARTUP, INCREMENTAL_SAVE, SAVE_INTERVAL
)
from parser import DrugPageParser


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DrugScraper:
    """Scrapes drug data from Drugs.com"""

    def __init__(self, batch_size=DEFAULT_BATCH_SIZE, request_delay=DEFAULT_REQUEST_DELAY,
                 timeout=DEFAULT_TIMEOUT, max_retries=MAX_RETRIES):
        self.batch_size = batch_size
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.parser = DrugPageParser()
        self.session = self._create_session()
        self.results = []
        self.processed_urls = set()
        self.failed_urls = []
        
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=INITIAL_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update(REQUEST_HEADERS)
        
        return session

    def load_urls(self, urls_file: Path) -> List[str]:
        """Load drug URLs from file."""
        try:
            if not urls_file.exists():
                logger.error(f"URLs file not found: {urls_file}")
                logger.info("Please provide a file with one URL per line at: data/candidate_urls.txt")
                return []
            
            with open(urls_file, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
            
            logger.info(f"Loaded {len(urls)} URLs from {urls_file}")
            return urls
            
        except Exception as e:
            logger.error(f"Error loading URLs: {str(e)}")
            return []

    def load_checkpoint(self) -> Optional[Dict]:
        """Load checkpoint data if resuming."""
        try:
            if CHECKPOINT_FILE.exists():
                with open(CHECKPOINT_FILE, 'r') as f:
                    checkpoint = json.load(f)
                logger.info(f"Loaded checkpoint: {len(checkpoint.get('processed_urls', []))} processed")
                return checkpoint
        except Exception as e:
            logger.error(f"Error loading checkpoint: {str(e)}")
        
        return None

    def save_checkpoint(self, urls_processed: set, results: List[Dict]):
        """Save checkpoint for resuming."""
        try:
            checkpoint = {
                'timestamp': datetime.now().isoformat(),
                'processed_urls': list(urls_processed),
                'total_results': len(results)
            }
            with open(CHECKPOINT_FILE, 'w') as f:
                json.dump(checkpoint, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving checkpoint: {str(e)}")

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a single page with retries."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch {url}: {str(e)}")
            return None

    def scrape_batch(self, urls: List[str], batch_num: int, total_batches: int) -> List[Dict]:
        """Scrape a batch of URLs."""
        batch_results = []
        
        pbar = tqdm(urls, desc=f"Batch {batch_num}/{total_batches}", leave=False)
        
        for url in pbar:
            if url in self.processed_urls:
                continue
            
            # Fetch page
            html = self.fetch_page(url)
            if not html:
                self.failed_urls.append(url)
                self.processed_urls.add(url)
                continue
            
            # Parse page
            drug_data = self.parser.parse_drug_page(html, url)
            if drug_data and self.parser.validate_drug_data(drug_data):
                batch_results.append(drug_data)
            else:
                self.failed_urls.append(url)
            
            self.processed_urls.add(url)
            
            # Respect rate limiting
            time.sleep(self.request_delay)
        
        return batch_results

    def run(self, urls_file: Path, resume: bool = True):
        """Main scraping loop."""
        logger.info("=" * 80)
        logger.info("Starting Drugs.com Data Scraper")
        logger.info(f"Batch size: {self.batch_size}, Request delay: {self.request_delay}s")
        logger.info("=" * 80)
        
        # Load URLs
        urls = self.load_urls(urls_file)
        if not urls:
            return
        
        # Load checkpoint if resuming
        if resume and RESUME_ON_STARTUP:
            checkpoint = self.load_checkpoint()
            if checkpoint:
                self.processed_urls = set(checkpoint.get('processed_urls', []))
                self.results = []  # Will reload from output file
        
        # Load existing results if they exist
        if OUTPUT_FILE.exists():
            try:
                with open(OUTPUT_FILE, 'r') as f:
                    self.results = json.load(f)
                logger.info(f"Loaded {len(self.results)} existing results")
            except Exception as e:
                logger.warning(f"Could not load existing results: {str(e)}")
        
        # Filter out already processed URLs
        remaining_urls = [u for u in urls if u not in self.processed_urls]
        logger.info(f"Total URLs: {len(urls)}, Remaining: {len(remaining_urls)}")
        
        if not remaining_urls:
            logger.info("All URLs already processed!")
            return
        
        # Process in batches
        total_batches = (len(remaining_urls) + self.batch_size - 1) // self.batch_size
        start_time = time.time()
        
        for batch_num in range(total_batches):
            batch_start = batch_num * self.batch_size
            batch_end = min(batch_start + self.batch_size, len(remaining_urls))
            batch_urls = remaining_urls[batch_start:batch_end]
            
            # Scrape batch
            batch_results = self.scrape_batch(batch_urls, batch_num + 1, total_batches)
            self.results.extend(batch_results)
            
            # Save incrementally
            if INCREMENTAL_SAVE and (batch_num + 1) % SAVE_INTERVAL == 0:
                self._save_results()
                self.save_checkpoint(self.processed_urls, self.results)
            
            # Calculate and display ETA
            elapsed = time.time() - start_time
            processed = len(self.processed_urls)
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = len(remaining_urls) - processed
            eta_seconds = remaining / rate if rate > 0 else 0
            eta_str = self._format_time(eta_seconds)
            
            logger.info(
                f"Batch {batch_num + 1}/{total_batches} complete. "
                f"Results: {len(self.results)}, Failed: {len(self.failed_urls)}, "
                f"ETA: {eta_str}"
            )
        
        # Final save
        self._save_results()
        self.save_checkpoint(self.processed_urls, self.results)
        
        # Print summary
        self._print_summary(time.time() - start_time)

    def _save_results(self):
        """Save and validate results to JSON file."""
        try:
            # Normalize and validate each record
            normalized_results = []
            
            for drug in self.results:
                # Ensure all required fields exist
                normalized_drug = {
                    'drug_name': str(drug.get('drug_name', '')).strip() or 'Unknown',
                    'url': str(drug.get('url', '')).strip(),
                    'drug_class': str(drug.get('drug_class', '')).strip(),
                    'generic_name': str(drug.get('generic_name', '')).strip(),
                    'brand_names': self._clean_list(drug.get('brand_names', [])),
                    'related_conditions': self._clean_list(drug.get('related_conditions', []))
                }
                
                # Only include if it has essential fields
                if normalized_drug['drug_name'] and normalized_drug['url']:
                    normalized_results.append(normalized_drug)
            
            # Write normalized JSON
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(normalized_results, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(normalized_results)} validated results to {OUTPUT_FILE}")
            
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
    
    def _clean_list(self, items: List) -> List[str]:
        """Clean and normalize list items."""
        if not items:
            return []
        
        cleaned = []
        for item in items:
            if isinstance(item, str):
                item = item.strip()
                # Filter out junk entries
                if item and len(item) > 2 and not item.startswith(('http', '⚠', '✓')):
                    cleaned.append(item)
        
        return list(set(cleaned))  # Remove duplicates

    def _print_summary(self, elapsed_time):
        """Print execution summary."""
        logger.info("=" * 80)
        logger.info("SCRAPING COMPLETE")
        logger.info(f"Total time: {self._format_time(elapsed_time)}")
        logger.info(f"Total results: {len(self.results)}")
        logger.info(f"Failed URLs: {len(self.failed_urls)}")
        success_rate = (len(self.results) / (len(self.results) + len(self.failed_urls)) * 100) if (len(self.results) + len(self.failed_urls)) > 0 else 0
        logger.info(f"Success rate: {success_rate:.2f}%")
        logger.info(f"Output file: {OUTPUT_FILE}")
        logger.info("=" * 80)

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds to human-readable time."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}h {minutes}m {secs}s" if hours > 0 else f"{minutes}m {secs}s"


def main():
    parser = argparse.ArgumentParser(
        description="Scrape drug data from Drugs.com",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--urls-file',
        type=Path,
        default=URLS_FILE,
        help='Path to file containing drug URLs (one per line)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help='Number of URLs to process per batch'
    )
    
    parser.add_argument(
        '--delay',
        type=float,
        default=DEFAULT_REQUEST_DELAY,
        help='Delay in seconds between requests'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=DEFAULT_TIMEOUT,
        help='Request timeout in seconds'
    )
    
    parser.add_argument(
        '--max-retries',
        type=int,
        default=MAX_RETRIES,
        help='Maximum number of retries per URL'
    )
    
    parser.add_argument(
        '--resume',
        action='store_true',
        default=True,
        help='Resume from last checkpoint'
    )
    
    args = parser.parse_args()
    
    scraper = DrugScraper(
        batch_size=args.batch_size,
        request_delay=args.delay,
        timeout=args.timeout,
        max_retries=args.max_retries
    )
    
    scraper.run(args.urls_file, resume=args.resume)


if __name__ == '__main__':
    main()
