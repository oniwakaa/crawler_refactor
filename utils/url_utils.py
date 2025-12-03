import logging
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

def normalize_linkedin_url(url: str) -> str:
    """
    Normalize LinkedIn URLs by replacing regional subdomains with 'www'.
    
    Examples:
        - https://ro.linkedin.com/in/user -> https://www.linkedin.com/in/user
        - https://nl.linkedin.com/in/user -> https://www.linkedin.com/in/user
        - https://www.linkedin.com/in/user -> unchanged (already correct)
        - https://linkedin.com/in/user -> https://www.linkedin.com/in/user
    
    Args:
        url: LinkedIn URL with any subdomain
        
    Returns:
        Normalized URL with www subdomain
    """
    if not url:
        return url
        
    try:
        parsed = urlparse(url)
        
        # Check if it's a LinkedIn URL
        if "linkedin.com" in parsed.netloc:
            # If netloc is exactly linkedin.com or has a subdomain that is not www
            if parsed.netloc == "linkedin.com" or not parsed.netloc.startswith("www."):
                # Replace the netloc with www.linkedin.com
                # We need to handle the case where it might be just linkedin.com or ro.linkedin.com
                
                # Simple approach: if it ends with linkedin.com, force it to be www.linkedin.com
                # This handles ro.linkedin.com, linkedin.com, etc.
                
                # Split netloc by dots to check structure if needed, but forcing www.linkedin.com is safer for profile URLs
                # We assume we are dealing with the main site.
                
                # Reconstruct with new netloc
                new_netloc = "www.linkedin.com"
                
                # Log the change if it's a significant change (not just adding www to bare domain)
                if parsed.netloc != "linkedin.com" and parsed.netloc != "www.linkedin.com":
                    logger.info(f"Normalizing regional LinkedIn URL: {parsed.netloc} -> {new_netloc}")
                
                normalized_parts = list(parsed)
                normalized_parts[1] = new_netloc # netloc is at index 1
                return urlunparse(normalized_parts)
                
        return url
        
    except Exception as e:
        logger.warning(f"Error normalizing URL {url}: {e}")
        return url
