import logging
import re
from typing import Optional, Dict, List
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DrugPageParser:
    """Parses drug description pages from Drugs.com"""

    def __init__(self):
        self.logger = logger

    def parse_drug_page(self, html_content: str, url: str) -> Optional[Dict]:
        """
        Parse a drug description page and extract required fields.
        
        Args:
            html_content: Raw HTML content of the page
            url: URL of the drug page
            
        Returns:
            Dictionary with extracted drug data or None if parsing fails
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            drug_data = {
                'url': url,
                'drug_name': self._extract_drug_name(soup, url),
                'drug_class': self._extract_drug_class(soup),
                'generic_name': self._extract_generic_name(soup),
                'brand_names': self._extract_brand_names(soup),
                'related_conditions': self._extract_related_conditions(soup)
            }
            
            # Validate that we have data
            if not drug_data['drug_name']:
                self.logger.warning(f"Could not extract drug_name from {url}")
                return None
                
            return drug_data
            
        except Exception as e:
            self.logger.error(f"Error parsing page {url}: {str(e)}")
            return None

    def _extract_drug_name(self, soup: BeautifulSoup, url: str) -> str:
        """Extract the primary drug name from the page."""
        try:
            # Try h1 tag first
            h1 = soup.find('h1')
            if h1:
                text = h1.get_text(strip=True)
                drug_name = re.sub(r'\s*[-–].*', '', text).strip()
                return drug_name
            
            # Try page title
            title = soup.find('title')
            if title:
                text = title.get_text(strip=True)
                drug_name = re.sub(r'\s*[-–].*', '', text).strip()
                if drug_name:
                    return drug_name
            
            # Fallback: extract from URL
            url_part = url.split('/')[-1].replace('.html', '')
            return url_part.replace('-', ' ').title()
            
        except Exception as e:
            self.logger.error(f"Error extracting drug_name: {str(e)}")
            return ""

    def _extract_drug_class(self, soup: BeautifulSoup) -> str:
        """Extract drug class/classification."""
        try:
            # Look for drug class in common locations
            for elem in soup.find_all(['div', 'span', 'p']):
                text = elem.get_text(strip=True)
                if 'drug class' in text.lower() or 'class:' in text.lower():
                    # Extract after the label
                    match = re.search(r'(?:drug\s+)?class\s*:?\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
            
            return ""
            
        except Exception as e:
            self.logger.error(f"Error extracting drug_class: {str(e)}")
            return ""

    def _extract_generic_name(self, soup: BeautifulSoup) -> str:
        """Extract generic name of the drug."""
        try:
            # Look for generic name
            for elem in soup.find_all(['div', 'span', 'p']):
                text = elem.get_text(strip=True)
                if 'generic name' in text.lower() or 'generic:' in text.lower():
                    match = re.search(r'generic\s+name\s*:?\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
            
            return ""
            
        except Exception as e:
            self.logger.error(f"Error extracting generic_name: {str(e)}")
            return ""

    def _extract_brand_names(self, soup: BeautifulSoup) -> List[str]:
        """Extract list of brand names."""
        try:
            brand_names = []
            
            # Look for brand names section
            for elem in soup.find_all(['div', 'span', 'p']):
                text = elem.get_text(strip=True)
                if 'brand name' in text.lower():
                    # Try to extract list items
                    parent = elem.parent
                    if parent:
                        for sibling in parent.find_next_siblings(['ul', 'ol', 'p', 'div']):
                            list_items = sibling.find_all('li')
                            if list_items:
                                for item in list_items:
                                    name = item.get_text(strip=True)
                                    if name:
                                        brand_names.append(name)
                            else:
                                text = sibling.get_text(strip=True)
                                if text and len(text) < 100:
                                    brand_names.append(text)
            
            return list(set(brand_names)) if brand_names else []
            
        except Exception as e:
            self.logger.error(f"Error extracting brand_names: {str(e)}")
            return []

    def _extract_related_conditions(self, soup: BeautifulSoup) -> List[str]:
        """Extract list of related medical conditions."""
        try:
            conditions = []
            
            # Look for conditions/indications
            patterns = ['used for', 'condition', 'indication', 'treat', 'uses:']
            
            for elem in soup.find_all(['div', 'span', 'p', 'h2', 'h3']):
                text = elem.get_text(strip=True)
                if any(pattern in text.lower() for pattern in patterns):
                    parent = elem.parent
                    if parent:
                        for sibling in parent.find_next_siblings(['ul', 'ol', 'p', 'div']):
                            list_items = sibling.find_all('li')
                            if list_items:
                                for item in list_items:
                                    condition = item.get_text(strip=True)
                                    if condition:
                                        conditions.append(condition)
                            else:
                                text = sibling.get_text(strip=True)
                                if text and 20 < len(text) < 300:
                                    conditions.append(text)
            
            return list(set(conditions)) if conditions else []
            
        except Exception as e:
            self.logger.error(f"Error extracting related_conditions: {str(e)}")
            return []

    def validate_drug_data(self, drug_data: Dict) -> bool:
        """Validate that all required fields are present."""
        if not drug_data:
            return False
        
        required = {'drug_name', 'url'}
        return all(drug_data.get(field) for field in required)
