import re
from typing import Optional
from utils.url_utils import normalize_linkedin_url

class LinkedInContactURLBuilder:
    """
    Helper class to construct LinkedIn contact info overlay URLs from profile URLs.
    """
    
    @staticmethod
    def build_contact_info_url(profile_url: str) -> Optional[str]:
        """
        Build a LinkedIn contact info overlay URL from a profile URL.
        
        Args:
            profile_url: LinkedIn profile URL (e.g. https://www.linkedin.com/in/username/)
            
        Returns:
            Contact info overlay URL or None if invalid input
        """
        if not profile_url or "linkedin.com/in/" not in profile_url.lower():
            return None
            
        # Normalize the profile URL first (handle regional subdomains)
        profile_url = normalize_linkedin_url(profile_url)
            
        # Remove query parameters and fragments
        clean_url = re.sub(r'[?#].*$', '', profile_url)
        
        # Remove any existing overlay paths (if user passes a contact URL, clean it first)
        clean_url = re.sub(r'/overlay/.*$', '', clean_url)
        
        # Remove trailing slash to avoid double slashes when appending
        clean_url = clean_url.rstrip("/")
        
        # Append the contact info overlay path
        contact_url = f"{clean_url}/overlay/contact-info/"
        
        return contact_url
    
    @staticmethod
    def is_linkedin_profile_url(url: str) -> bool:
        """
        Check if a URL is a valid LinkedIn profile URL.
        
        Returns True only for URLs like:
        - https://www.linkedin.com/in/username/
        - https://www.linkedin.com/in/username
        
        Returns False for:
        - Company pages (/company/)
        - Job pages (/jobs/)
        - Sub-pages (/posts/, /details/, etc.)
        - Other non-profile URLs
        """
        if not url:
            return False
            
        url_lower = url.lower()
        
        # Must contain /in/
        if "/in/" not in url_lower:
            return False
            
        # Check if it looks like a profile URL (avoiding sub-pages)
        # Profile URLs typically end after the username or have query params
        # Ex: linkedin.com/in/username/ or linkedin.com/in/username?param=value
        
        # If it contains certain path segments, it's likely a sub-page
        # and not the main profile
        sub_page_indicators = [
            "/posts/",
            "/details/",
            "/activity/", 
            "/companies/",
            "/jobs/",
            "/certifications/",
            "/skills/",
            "/recommendations/",
            "/interests/",
            "/projects/",
            "/articles/",
            "/groups/",
            "/courses/",
            "/honors/",
            "/testimonials/",
            "/publications/",
            "/about/",
            "/education/",
            "/experience/"
        ]
        
        for indicator in sub_page_indicators:
            if indicator in url_lower:
                return False
        
        # Must be a profile URL
        return "linkedin.com" in url_lower
