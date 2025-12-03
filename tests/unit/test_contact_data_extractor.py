import pytest
from tools.contact_data_extractor import ContactDataExtractor

class TestContactDataExtractor:
    
    def test_extract_emails(self):
        text = "Contact us at info@example.com or support@test.org for help."
        emails = ContactDataExtractor.extract_emails_from_text(text)
        assert "info@example.com" in emails
        assert "support@test.org" in emails
        assert len(emails) == 2
        
    def test_extract_emails_deduplicate(self):
        text = "Email: test@example.com or TEST@EXAMPLE.COM"
        emails = ContactDataExtractor.extract_emails_from_text(text)
        # Should be deduplicated and lowercased
        assert len(emails) == 1
        assert emails[0] == "test@example.com"
        
    def test_extract_phones_us_format(self):
        text = "Call me at (555) 123-4567 or 555-987-6543"
        phones = ContactDataExtractor.extract_phones_from_text(text)
        assert len(phones) >= 1  # At least one should be found
        
    def test_extract_phones_international(self):
        text = "International: +49 30 12345678"
        phones = ContactDataExtractor.extract_phones_from_text(text)
        assert len(phones) >= 1
        
    def test_extract_websites(self):
        text = "Visit https://www.example.com or http://test.org"
        websites = ContactDataExtractor.extract_websites_from_text(text)
        assert len(websites) >= 2
        
    def test_extract_websites_filter_linkedin(self):
        text = "Visit https://www.example.com and https://www.linkedin.com/in/test"
        websites = ContactDataExtractor.extract_websites_from_text(text)
        # LinkedIn should be filtered out
        assert all('linkedin.com' not in url.lower() for url in websites)
        assert any('example.com' in url for url in websites)
        
    def test_empty_text(self):
        assert ContactDataExtractor.extract_emails_from_text("") == []
        assert ContactDataExtractor.extract_phones_from_text("") == []
        assert ContactDataExtractor.extract_websites_from_text("") == []
        
    def test_no_matches(self):
        text = "This is just some random text without any contact info"
        assert ContactDataExtractor.extract_emails_from_text(text) == []
        assert ContactDataExtractor.extract_phones_from_text(text) == []
        assert ContactDataExtractor.extract_websites_from_text(text) == []
