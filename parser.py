import logging
import re
from typing import Optional, Dict, List
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class DrugPageParser:
    def __init__(self):
        self.logger = logger

    def parse_drug_page(self, html_content: str, url: str) -> Optional[Dict]:
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
            if not drug_data['drug_name']:
                return None
            return drug_data
        except Exception as e:
            self.logger.error(f"Error parsing {url}: {str(e)}")
            return None

    def _extract_drug_name(self, soup: BeautifulSoup, url: str) -> str:
        try:
            h1 = soup.find('h1')
            if h1:
                text = h1.get_text(strip=True)
                return re.sub(r'\s*[-–]\s*.*', '', text).strip()
            return ""
        except:
            return ""

    def _extract_drug_class(self, soup: BeautifulSoup) -> str:
        try:
            text = soup.get_text()
            match = re.search(r'Drug Class:?\s*([A-Z][^.\n]*?)(?:[\n.]|Generic|Brand)', text, re.IGNORECASE)
            if match:
                result = match.group(1).strip()
                result = re.sub(r'\s+', ' ', result)
                if result and len(result) > 3 and len(result) < 200:
                    return result
            return ""
        except:
            return ""

    def _extract_generic_name(self, soup: BeautifulSoup) -> str:
        try:
            text = soup.get_text()
            match = re.search(r'Generic Name:?\s*([a-z][a-z\s\-]*?)(?:\n|Brand|Dosage|\()', text, re.IGNORECASE)
            if match:
                result = match.group(1).strip()
                if result and len(result.split()) <= 3 and len(result) < 100:
                    result = re.sub(r'\s*\(.*\)', '', result)
                    result = re.sub(r'\s*mg.*', '', result, flags=re.IGNORECASE)
                    if result:
                        return result
            return ""
        except:
            return ""

    def _extract_brand_names(self, soup: BeautifulSoup) -> List[str]:
        try:
            brand_names = []
            for header in soup.find_all(['h2', 'h3', 'h4', 'strong', 'b', 'dt']):
                if 'brand' in header.get_text(strip=True).lower() and 'name' in header.get_text(strip=True).lower():
                    for sibling in header.parent.find_next_siblings(['ul', 'ol', 'div', 'p', 'dd']):
                        if sibling.find(['h2', 'h3', 'h4']):
                            break
                        for li in sibling.find_all('li'):
                            text = li.get_text(strip=True)
                            if self._is_valid_brand(text):
                                brand_names.append(text)
            return list(set(brand_names))
        except:
            return []

    def _is_valid_brand(self, text: str) -> bool:
        if not text or len(text) < 2 or len(text) > 150:
            return False
        reject = ['warning', 'side', 'dose', 'mg', 'tablet', 'http', 'helpful', 'review', '(', ')', '[', ']']
        if any(x in text.lower() for x in reject):
            return False
        if len(text.split()) > 4:
            return False
        return text and text[0].isupper()

    def _extract_related_conditions(self, soup: BeautifulSoup) -> List[str]:
        try:
            conditions = []
            text = soup.get_text()
            match = re.search(r'(?:Used For|Indications?|Conditions?|Treatment):?\s*\n(.*?)(?:\n\n|Drug Class|Generic|Brand)', text, re.IGNORECASE | re.DOTALL)
            if match:
                items = re.split(r'[\n•\-]+', match.group(1))
                for item in items:
                    item = item.strip()
                    if self._is_valid_condition(item):
                        conditions.append(item)
            return list(set(conditions))
        except:
            return []

    def _is_valid_condition(self, text: str) -> bool:
        if not text or len(text) < 5 or len(text) > 300:
            return False
        reject = ['helpful', 'review', 'warning', 'disclaimer', 'http', 'click', 'side effect', 'dosage', 'tablet']
        if any(x in text.lower() for x in reject):
            return False
        return True

    def validate_drug_data(self, drug_data: Dict) -> bool:
        if not drug_data:
            return False
        required = {'drug_name', 'url', 'generic_name'}
        return all(drug_data.get(field) for field in required)
