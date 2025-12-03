import urllib.parse
from typing import Optional, Dict, Any

class LinkedInPeopleSearchBuilder:
    """
    Helper class to build valid LinkedIn People search URLs.
    Constructs URLs that force LinkedIn to show People results directly.
    """
    
    BASE_URL = "https://www.linkedin.com/search/results/people/"
    
    @staticmethod
    def build_people_search_url(
        role: str, 
        location: Optional[str] = None, 
        company: Optional[str] = None,
        keywords: Optional[str] = None
    ) -> str:
        """
        Build a LinkedIn People search URL.
        
        Args:
            role: Job title or role (e.g. "CTO", "Marketing Director")
            location: Location string (e.g. "Berlin", "Germany")
            company: Company name (optional)
            keywords: Additional keywords (optional)
            
        Returns:
            Full LinkedIn search URL
        """
        # Combine terms into a single keywords string
        # This is often more effective than using specific parameters for broad searches
        search_terms = [role]
        
        if company:
            search_terms.append(company)
            
        if location:
            search_terms.append(location)
            
        if keywords:
            search_terms.append(keywords)
            
        # Filter out empty terms
        search_terms = [term for term in search_terms if term]
        
        if not search_terms:
            raise ValueError("At least one search term (role, company, location) is required")
            
        # Join with spaces
        query_string = " ".join(search_terms)
        
        # URL encode the query
        encoded_query = urllib.parse.quote(query_string)
        
        # Construct URL
        # origin=GLOBAL_SEARCH_HEADER is standard when searching from the top bar
        url = f"{LinkedInPeopleSearchBuilder.BASE_URL}?keywords={encoded_query}&origin=GLOBAL_SEARCH_HEADER"
        
        return url
        
    @staticmethod
    def parse_query_to_components(query: str) -> Dict[str, str]:
        """
        Simple heuristic to parse a natural language query into components.
        In a real agent, the LLM does this, but this is a helper for the builder.
        
        Args:
            query: User query string
            
        Returns:
            Dictionary with role, location, etc.
        """
        # This is a placeholder. The QueryBuilderAgent uses LLM for this.
        # But we can provide a simple fallback here.
        return {
            "role": query,
            "location": None,
            "company": None
        }
