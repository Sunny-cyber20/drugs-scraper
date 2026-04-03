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
            soup = BeautifulSoup(html_content, 'lxml')
            
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
            # Try common patterns for drug name in heading
            h1 = soup.find('h1')
            if h1:
                text = h1.get_text(strip=True)
                # Remove common suffixes like "- FDA Approved Drugs"
                drug_name = re.sub(r'\s*[-–]\s*.*', '', text).strip()
                return drug_name
            
            # Fallback: extract from URL
            url_part = url.rstrip('/').split('/')[-1]
            return url_part.replace('-', ' ').title()
            
        except Exception as e:
            self.logger.error(f"Error extracting drug_name: {str(e)}")
            return ""

    def _extract_drug_class(self, soup: BeautifulSoup) -> str:
        """Extract drug class/classification."""
        try:
            # Look for "Drug Class:" or similar patterns
            for label in soup.find_all(['strong', 'b', 'span']):
                if 'drug class' in label.get_text(strip=True).lower():
                    # Get the next sibling or parent's next element
                    parent = label.parent
                    if parent:
                        text = parent.get_text(strip=True)
                        # Extract content after the label
                        match = re.search(r'Drug Class:\s*(.+?)(?:\n|$)', text)
                        if match:
                            return match.group(1).strip()
            
            # Alternative: check data attributes or specific divs
            for div in soup.find_all('div', class_=re.compile('class', re.I)):
                text = div.get_text(strip=True)
                if text and len(text) < 200:
                    return text
                    
            return ""
            
        except Exception as e:
            self.logger.error(f"Error extracting drug_class: {str(e)}")
            return ""

    def _extract_generic_name(self, soup: BeautifulSoup) -> str:
        """Extract generic name of the drug."""
        try:
            # Look for "Generic Name:" pattern
            for label in soup.find_all(['strong', 'b', 'span']):
                if 'generic name' in label.get_text(strip=True).lower():
                    parent = label.parent
                    if parent:
                        text = parent.get_text(strip=True)
                        match = re.search(r'Generic Name:\s*(.+?)(?:\n|$)', text, re.I)
                        if match:
                            return match.group(1).strip()
            
            return ""
            
        except Exception as e:
            self.logger.error(f"Error extracting generic_name: {str(e)}")
            return ""

    def _extract_brand_names(self, soup: BeautifulSoup) -> List[str]:
        """Extract list of brand names reliably."""
        try:
            brand_names = []
            
            # Strategy 1: Look for "Brand Names" or "Brand Name" section
            for header in soup.find_all(['h2', 'h3', 'strong', 'b', 'span']):
                header_text = header.get_text(strip=True).lower()
                
                if 'brand' in header_text and 'name' in header_text:
                    # Get the parent container
                    container = header.parent
                    if not container:
                        continue
                    
                    # Look for list items in next siblings
                    for sibling in container.find_next_siblings(['ul', 'ol', 'div', 'p']):
                        # Stop if we hit another major section
                        if sibling.find(['h2', 'h3']):
                            break
                        
                        # Extract from <li> elements
                        for li in sibling.find_all('li'):
                            text = li.get_text(strip=True)
                            # Brand names are typically 1-3 words, no special formatting
                            if text and 2 < len(text) < 100 and not any(char in text for char in ['(', ')', '[', ']', 'http']):
                                brand_names.append(text)
                        
                        # Also check for comma-separated values in text
                        if not sibling.find_all('li'):
                            text = sibling.get_text(strip=True)
                            if text and ',' in text:
                                parts = [p.strip() for p in text.split(',')]
                                for part in parts:
                                    if 2 < len(part) < 100:
                                        brand_names.append(part)
            
            # Strategy 2: Look in meta tags or data attributes
            if not brand_names:
                # Check for brand info in common div classes
                for div in soup.find_all('div', class_=re.compile(r'brand|trade', re.I)):
                    text = div.get_text(strip=True)
                    if text and 2 < len(text) < 200:
                        # Split by common delimiters
                        for item in text.split(','):
                            item = item.strip()
                            if 2 < len(item) < 100:
                                brand_names.append(item)
            
            # Remove duplicates and clean
            brand_names = list(set(brand_names))
            # Remove generic terms
            brand_names = [b for b in brand_names if b.lower() not in ['brand names', 'also known as', 'marketed as']]
            
            return brand_names if brand_names else []
            
        except Exception as e:
            self.logger.error(f"Error extracting brand_names: {str(e)}")
            return []

    def _extract_related_conditions(self, soup: BeautifulSoup) -> List[str]:
        """Extract list of related medical conditions ONLY."""
        try:
            conditions = []
            
            # Look for specific sections with medical conditions
            # Target headings like "Used For:", "Conditions Treated:", "Indications:"
            target_headers = ['used for', 'condition', 'indication', 'treat']
            
            for header in soup.find_all(['h2', 'h3', 'strong', 'b']):
                header_text = header.get_text(strip=True).lower()
                
                # Only match actual medical condition headers
                if any(target in header_text for target in target_headers):
                    parent = header.parent
                    if not parent:
                        continue
                    
                    # Get next sibling that contains the actual conditions
                    for sibling in parent.find_next_siblings(['ul', 'ol', 'p', 'div']):
                        # Stop if we hit another section header
                        if sibling.find(['h2', 'h3']):
                            break
                        
                        # Extract from list items
                        list_items = sibling.find_all('li')
                        if list_items:
                            for item in list_items:
                                text = item.get_text(strip=True)
                                # Filter: only medical conditions (50-200 chars, no URLs, no buttons)
                                if (text and 
                                    50 < len(text) < 200 and 
                                    not any(word in text.lower() for word in ['helpful', 'report', 'review', 'read more', 'helpful?', 'http', 'warning', 'side effect']) and
                                    not text.startswith(('⚠', '✓'))):
                                    conditions.append(text)
                        else:
                            # Single paragraph text
                            text = sibling.get_text(strip=True)
                            if (text and 
                                50 < len(text) < 200 and
                                not any(word in text.lower() for word in ['helpful', 'report', 'review', 'read more', 'warning', 'side effect'])):
                                conditions.append(text)
                        
                        break  # Only process first matching sibling
            
            # Remove duplicates and filter
            conditions = list(set(conditions))
            # Keep only actual medical conditions (filter out generic text)
            medical_conditions = [c for c in conditions if len(c.split()) >= 2]
            
            return medical_conditions if medical_conditions else []
            
        except Exception as e:
            self.logger.error(f"Error extracting related_conditions: {str(e)}")
            return []

    def validate_drug_data(self, drug_data: Dict) -> bool:
        """Validate that all required fields are present."""
        if not drug_data:
            return False
        
        required = {'drug_name', 'url', 'generic_name'}
        return all(drug_data.get(field) for field in required)
