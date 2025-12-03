import pytest
from tools.linkedin_contact_url_builder import LinkedInContactURLBuilder

class TestLinkedInContactURLBuilder:
    
    def test_basic_profile_url(self):
        url = "https://www.linkedin.com/in/carlo-bizzaro/"
        result = LinkedInContactURLBuilder.build_contact_info_url(url)
        assert result == "https://www.linkedin.com/in/carlo-bizzaro/overlay/contact-info/"
        
    def test_url_without_trailing_slash(self):
        url = "https://www.linkedin.com/in/john-doe"
        result = LinkedInContactURLBuilder.build_contact_info_url(url)
        assert result == "https://www.linkedin.com/in/john-doe/overlay/contact-info/"
        
    def test_url_with_query_params(self):
        url = "https://www.linkedin.com/in/jane-smith?trk=public_profile"
        result = LinkedInContactURLBuilder.build_contact_info_url(url)
        assert result == "https://www.linkedin.com/in/jane-smith/overlay/contact-info/"
        
    def test_url_with_fragment(self):
        url = "https://www.linkedin.com/in/bob-jones#experience"
        result = LinkedInContactURLBuilder.build_contact_info_url(url)
        assert result == "https://www.linkedin.com/in/bob-jones/overlay/contact-info/"
        
    def test_already_overlay_url(self):
        # If user passes an already-overlay URL, clean it and rebuild
        url = "https://www.linkedin.com/in/alice/overlay/some-other-thing/"
        result = LinkedInContactURLBuilder.build_contact_info_url(url)
        assert result == "https://www.linkedin.com/in/alice/overlay/contact-info/"
        
    def test_invalid_url(self):
        url = "https://www.google.com"
        result = LinkedInContactURLBuilder.build_contact_info_url(url)
        assert result is None
        
    def test_empty_url(self):
        result = LinkedInContactURLBuilder.build_contact_info_url("")
        assert result is None
        
    def test_is_profile_url(self):
        assert LinkedInContactURLBuilder.is_linkedin_profile_url("https://www.linkedin.com/in/test/")
        assert not LinkedInContactURLBuilder.is_linkedin_profile_url("https://www.google.com")
        assert not LinkedInContactURLBuilder.is_linkedin_profile_url("")
