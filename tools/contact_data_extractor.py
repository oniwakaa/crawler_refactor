import re
from typing import List, Set

class ContactDataExtractor:
    """
    Utility class for extracting contact information from text using regex patterns.
    """
    
    # Comprehensive email regex
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        re.IGNORECASE
    )
    
    # Phone number patterns (various international formats)
    PHONE_PATTERNS = [
        # International format: +XX XXX XXX XXXX or +XX-XXX-XXX-XXXX
        re.compile(r'\+\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,9}'),
        # US format: (123) 456-7890 or 123-456-7890
        re.compile(r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}'),
        # European format: +49 30 12345678
        re.compile(r'\+\d{2}\s\d{2,4}\s\d{4,10}'),
    ]
    
    # Website URL patterns
    WEBSITE_PATTERN = re.compile(
        r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)',
        re.IGNORECASE
    )
    
    @staticmethod
    def extract_emails_from_text(text: str) -> List[str]:
        """
        Extract email addresses from text.
        
        Args:
            text: Text content to search
            
        Returns:
            List of unique email addresses found
        """
        if not text:
            return []
            
        # Find all matches
        matches = ContactDataExtractor.EMAIL_PATTERN.findall(text)
        
        # Lowercase first, then deduplicate
        lowercased_matches = [email.lower() for email in matches]
        
        # Deduplicate
        unique_emails = list(set(lowercased_matches))
        
        # Basic validation: filter out common false positives
        valid_emails = []
        for email in unique_emails:
            # Skip if it's just a file extension or similar
            if len(email) < 6:  # Minimum: a@b.co
                continue
            # Skip common false positives
            if email.endswith(('.png', '.jpg', '.gif', '.pdf')):
                continue
            valid_emails.append(email)
            
        return sorted(valid_emails)
    
    @staticmethod
    def extract_phones_from_text(text: str) -> List[str]:
        """
        Extract phone numbers from text.
        
        Args:
            text: Text content to search
            
        Returns:
            List of unique phone numbers found
        """
        if not text:
            return []
            
        all_matches: Set[str] = set()
        
        for pattern in ContactDataExtractor.PHONE_PATTERNS:
            matches = pattern.findall(text)
            all_matches.update(matches)
            
        # Clean and deduplicate
        cleaned_phones = []
        for phone in all_matches:
            # Basic cleaning
            phone = phone.strip()
            # Must have at least 7 digits
            if sum(c.isdigit() for c in phone) >= 7:
                cleaned_phones.append(phone)
                
        return sorted(list(set(cleaned_phones)))
    
    @staticmethod
    def extract_websites_from_text(text: str) -> List[str]:
        """
        Extract website URLs from text.
        
        Args:
            text: Text content to search
            
        Returns:
            List of unique website URLs found
        """
        if not text:
            return []
            
        matches = ContactDataExtractor.WEBSITE_PATTERN.findall(text)
        
        # Deduplicate
        unique_websites = list(set(matches))
        
        # Filter out LinkedIn URLs (we already have those)
        filtered_websites = []
        for url in unique_websites:
            if 'linkedin.com' not in url.lower():
                filtered_websites.append(url)
                
        return sorted(filtered_websites)
