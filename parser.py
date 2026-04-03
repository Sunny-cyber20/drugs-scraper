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
            # STRICT: Must find explicit "Drug Class:" label followed by actual content
            patterns = [
                r'Drug Class:\s*([A-Z][A-Za-z0-9\s\-]+?)(?:\n|$)',
                r'Classification:\s*([A-Z][A-Za-z0-9\s\-]+?)(?:\n|$)',
                r'Drug Type:\s*([A-Z][A-Za-z0-9\s\-]+?)(?:\n|$)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    result = match.group(1).strip()
                    # STRICT: Must be 5-200 chars, no junk
                    if 5 < len(result) < 200 and not any(x in result.lower() for x in ['http', 'click', 'warning']):
                        return result
            
            return ""
        except:
            return ""

    def _extract_generic_name(self, soup: BeautifulSoup) -> str:
        try:
            text = soup.get_text()
            # STRICT: Find explicit "Generic Name:" and extract ONLY the name (1-3 words max)
            match = re.search(r'Generic Name:\s*([a-z][a-z\-]*?)(?:\s*\n|\s*\(|\s*–)', text, re.IGNORECASE)
            if match:
                result = match.group(1).strip()
                # STRICT: Only 1-3 words, no numbers, no special chars except hyphen
                if result and 1 <= len(result.split()) <= 3:
                    if re.match(r'^[a-z][a-z\-]*$', result, re.IGNORECASE):
                        return result.lower()
            
            return ""
        except:
            return ""

    def _extract_brand_names(self, soup: BeautifulSoup) -> List[str]:
        try:
            brand_names = []
            text = soup.get_text()
            
            # STRICT: Find "Brand Names:" section
            match = re.search(r'Brand Names?:\s*\n(.*?)(?:\n\n|\nGeneric|\nDrug Class)', text, re.IGNORECASE | re.DOTALL)
            if match:
                section = match.group(1)
                # Split by bullets, newlines, commas
                items = re.split(r'[\n•,\-]+', section)
                
                for item in items:
                    item = item.strip()
                    # STRICT: Must be actual brand name (capitalized, 2-50 chars, no junk)
                    if self._is_strict_brand_name(item):
                        brand_names.append(item)
            
            return list(set(brand_names))
        except:
            return []

    def _is_strict_brand_name(self, text: str) -> bool:
        """STRICT brand name validation"""
        if not text or len(text) < 2 or len(text) > 50:
            return False
        
        # REJECT: Any suspicious keywords
        reject_words = [
            'warning', 'side effect', 'symptom', 'dose', 'dosage', 'mg',
            'tablet', 'capsule', 'injection', 'cream', 'gel', 'solution',
            'helpful', 'report', 'review', 'date', 'reviewer', 'http',
            'click', 'read', 'more', 'fda', 'approved', 'indication',
            'treatment', 'condition', 'caution', 'disclaimer', '(', ')',
            'disclaimer', 'use', 'important', 'see also', 'related'
        ]
        
        text_lower = text.lower()
        for word in reject_words:
            if word in text_lower:
                return False
        
        # ACCEPT: Only if it looks like a brand name
        # Must start with capital, be short (1-3 words)
        if not text or not text[0].isupper():
            return False
        
        if len(text.split()) > 3:
            return False
        
        return True

    def _extract_related_conditions(self, soup: BeautifulSoup) -> List[str]:
        try:
            conditions = []
            text = soup.get_text()
            
            # STRICT: Find explicit "Used For:" or "Indications:" section
            match = re.search(
                r'(?:Used For|Indications?):\s*\n(.*?)(?:\n\n|\nBrand|\nGeneric|\nDrug Class)',
                text, re.IGNORECASE | re.DOTALL
            )
            
            if match:
                section = match.group(1)
                # Split by newlines and bullets
                items = re.split(r'[\n•\-]+', section)
                
                for item in items:
                    item = item.strip()
                    # STRICT: Must be actual medical condition
                    if self._is_strict_condition(item):
                        conditions.append(item)
            
            return list(set(conditions))
        except:
            return []

    def _is_strict_condition(self, text: str) -> bool:
        """STRICT medical condition validation"""
        if not text or len(text) < 5 or len(text) > 300:
            return False
        
        # REJECT: Disclaimers, warnings, reviews
        reject_words = [
            'helpful', 'report', 'review', 'warning', 'caution', 'disclaimer',
            'http', 'click', 'read more', 'see also', 'related', 'feedback',
            'comment', 'rating', 'date', 'reviewer', 'side effect', 'symptom',
            'dosage', 'dose', 'mg', 'tablet', 'use this', 'do not', 'fda',
            'approved', 'important', 'disclaimer:', 'warning:'
        ]
        
        text_lower = text.lower()
        for word in reject_words:
            if word in text_lower:
                return False
        
        # ACCEPT: Only if it contains medical keywords
        medical_keywords = [
            'disease', 'disorder', 'condition', 'syndrome', 'failure',
            'infection', 'cancer', 'diabetes', 'heart', 'pressure',
            'arthritis', 'inflammation', 'pain', 'fever', 'anxiety',
            'depression', 'asthma', 'allergy', 'hypertension'
        ]
        
        has_medical = any(keyword in text_lower for keyword in medical_keywords)
        
        # Must have medical keyword OR be reasonable medical text
        if not has_medical:
            # If no medical keyword, reject it
            return False
        
        return True

    def validate_drug_data(self, drug_data: Dict) -> bool:
        if not drug_data:
            return False
        
        # STRICT: ALL fields must be populated
        required_fields = {
            'drug_name': drug_data.get('drug_name', '').strip(),
            'url': drug_data.get('url', '').strip(),
            'drug_class': drug_data.get('drug_class', '').strip(),
            'generic_name': drug_data.get('generic_name', '').strip(),
        }
        
        # All required fields must have content
        if not all(required_fields.values()):
            return False
        
        # drug_class must NOT be empty
        if not required_fields['drug_class']:
            return False
        
        return True
