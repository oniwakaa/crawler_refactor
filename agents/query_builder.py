"""
QueryBuilderAgent - Optimizes search queries for better lead-relevant results

Transforms raw user input into optimized Firecrawl search parameters using
query operators and domain filtering to improve the relevance of search results.
"""

import json
import logging
from typing import Dict, Optional, List
from tools.llama_wrapper import LlamaWrapper
from tools.linkedin_search_builder import LinkedInPeopleSearchBuilder


class QueryBuilderAgent:
    """
    Agent that transforms user queries into optimized Firecrawl search parameters.
    
    Purpose: Reduce irrelevant URLs (job boards, articles) and increase 
    profile/team page results for lead extraction.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize LLM wrapper using orchestrator model
        self.llm = LlamaWrapper()
        self.orchestrator_model = "gpt-oss:120b-cloud"
        
        # Default domain lists for fallback
        self.default_exclude_domains = [
            "indeed.com", "linkedin.com/jobs", "glassdoor.com", 
            "monster.com", "ziprecruiter.com", "careerbuilder.com",
            "simplyhired.com", "angel.co/jobs", "startupjobs.com",
            "lever.co", "workable.com", "greenhouse.io"
        ]
        
        self.default_include_domains = [
            "linkedin.com/in", "crunchbase.com", "angellist.com",
            "github.com", "stackoverflow.com/users"
        ]
        
        # Job board indicators to detect and exclude
        self.job_board_indicators = [
            "jobs", "careers", "hiring", "apply", "vacancy", 
            "position available", "work with us", "join our team"
        ]
    
    def build_search_query(self, user_query: str) -> Dict:
        """
        Transform user query into optimized Firecrawl search parameters.
        
        Args:
            user_query: Raw user input like "CTOs in Berlin"
            
        Returns:
            Dict with optimized query parameters:
            {
                'query': str,           # Optimized search query
                'exclude_terms': List[str],  # Terms to exclude with -
                'include_terms': List[str],  # Terms to include with +
                'reasoning': str        # Explanation of optimizations
            }
        """
        try:
            self.logger.info(f"Building optimized query for: {user_query}")
            
            # For testing, use fallback logic instead of LLM call
            # In production, this would call the LLM
            self.logger.info("Using fallback query optimization for testing")
            return self._build_fallback_query(user_query)
                
        except Exception as e:
            self.logger.error(f"Error building optimized query: {e}")
            return self._build_fallback_query(user_query)
    
    def _build_optimization_prompt(self, user_query: str) -> str:
        """Build the prompt for LLM to optimize the search query."""
        
        return f"""
You are an expert at building optimized web search queries for finding B2B leads and business professionals. 

Your task: Transform the user's raw query into an optimized search strategy that maximizes lead-relevant results and minimizes irrelevant content.

**User Query:** "{user_query}"

**Optimization Guidelines:**

1. **Identify Lead-Seeking Intent:**
   - The user wants to find PEOPLE (not jobs, not companies as entities)
   - Focus on profiles, team members, executives, founders
   - Avoid job postings, career pages, hiring content

2. **Query Enhancement Strategy:**
   - Add POSITIVE keywords: "profile", "LinkedIn", "team", "about", "founder", "CEO", "CTO", "executive"
   - Add NEGATIVE keywords: "-jobs", "-careers", "-hiring", "-apply", "-vacancy", "-position"
   - Include location terms if mentioned
   - Add professional role keywords

3. **Domain Targeting:**
   - Prioritize: linkedin.com/in, crunchbase.com, angellist.com, github.com
   - Exclude: job boards (indeed.com, glassdoor.com, monster.com, ziprecruiter.com)
   - Use site: operators for inclusion and -site: for exclusion

4. **Return Format (JSON only):**
   {{
       "query": "optimized search query with operators",
       "exclude_terms": ["term1", "term2"],  // Terms to exclude with -
       "include_terms": ["term3", "term4"],  // Terms to include with +
       "reasoning": "Brief explanation of optimizations made"
   }}

**Examples:**

Input: "CTOs in Berlin"
Output: {{
    "query": "CTO Berlin profile LinkedIn -jobs -careers -hiring",
    "exclude_terms": ["jobs", "careers", "hiring", "apply"],
    "include_terms": ["CTO", "profile", "LinkedIn", "Berlin"],
    "reasoning": "Added Berlin location, profile/LinkedIn indicators, excluded job terms"
}}

Input: "SaaS founders in San Francisco"
Output: {{
    "query": "SaaS founder \"San Francisco\" team about -hiring -career",
    "exclude_terms": ["hiring", "career", "jobs"],
    "include_terms": ["SaaS", "founder", "San Francisco", "team"],
    "reasoning": "Targeted SaaS founders in SF, excluded career content"
}}

Now optimize this query: "{user_query}"

Respond with valid JSON only.
"""

    def _build_fallback_query(self, user_query: str) -> Dict:
        """Build a basic optimized query when LLM fails."""
        self.logger.info("Using fallback query optimization")
        
        # Basic optimizations
        exclude_terms = ["jobs", "careers", "hiring"]
        include_terms = ["profile", "LinkedIn"]
        
        # Build basic optimized query
        optimized_query = user_query
        
        # Add positive terms (without + to allow partial matching)
        for term in include_terms:
            optimized_query += f" {term}"
        
        # Add negative terms (keep - for exclusion)
        for term in exclude_terms:
            optimized_query += f" -{term}"
        
        return {
            "query": optimized_query,
            "exclude_terms": exclude_terms,
            "include_terms": include_terms,
            "reasoning": "Basic fallback optimization with standard exclusions"
        }
    
    def validate_query_parameters(self, query_params: Dict) -> Dict:
        """Validate and clean query parameters."""
        
        required_fields = ["query"]
        for field in required_fields:
            if field not in query_params:
                raise ValueError(f"Missing required field: {field}")
        
        # Ensure query is not empty
        if not query_params["query"].strip():
            raise ValueError("Query cannot be empty")
        
        # Clean up the query
        query_params["query"] = query_params["query"].strip()
        
        return query_params
    
    def build_firecrawl_parameters(self, user_query: str) -> Dict:
        """
        Main method to get complete Firecrawl search parameters.
        
        Args:
            user_query: Raw user input
            
        Returns:
            Dict with all parameters needed for Firecrawl search:
            {
                'query': str,           # Optimized search query
                'limit': int,           # Number of results (default 10)
                'sources': List[str],   # Sources to search (default ['web'])
                'country': str,         # Country code for geo-targeting
                'location': str,        # Location string for geo-targeting
                'exclude_terms': List[str],  # Terms to exclude
                'include_terms': List[str],  # Terms to include  
                'reasoning': str        # Explanation
            }
        """
        
        # Get optimized query parameters
        query_params = self.build_search_query(user_query)
        query_params = self.validate_query_parameters(query_params)
        
        # Check if this is a LinkedIn-specific query
        if self._is_linkedin_query(user_query):
            try:
                direct_url = self._build_linkedin_people_url(user_query)
                self.logger.info(f"Generated direct LinkedIn URL: {direct_url}")
                
                return {
                    "search_type": "linkedin_people",
                    "direct_url": direct_url,
                    "query": user_query,
                    "reasoning": "Using LinkedIn People search URL for targeted profile results",
                    # Include standard params for fallback compatibility
                    "limit": 10,
                    "sources": ["web"],
                    "timeout": 60000
                }
            except Exception as e:
                self.logger.warning(f"Failed to build LinkedIn URL: {e}, falling back to standard search")
        
        # Extract location from user query for geo-targeting
        country, location = self._extract_location_from_query(user_query)
        
        # Build complete parameters
        firecrawl_params = {
            "query": query_params["query"],
            "limit": 10,  # Default limit
            "sources": ["web"],  # Focus on web results
            "country": country or "US",  # Default to US if no country detected
            "location": location or "",  # Use empty string if no location specified
            "exclude_terms": query_params.get("exclude_terms", []),
            "include_terms": query_params.get("include_terms", []),
            "reasoning": query_params.get("reasoning", ""),
            "timeout": 60000,  # 60 second timeout
            "ignoreInvalidURLs": True  # Skip URLs that can't be scraped
        }
        
        self.logger.info(f"Built Firecrawl parameters: {firecrawl_params}")
        return firecrawl_params

    def _is_linkedin_query(self, user_query: str) -> bool:
        """Detect if the query is specifically targeting LinkedIn profiles."""
        query_lower = user_query.lower()
        keywords = ["linkedin", "profile", "profiles"]
        return any(keyword in query_lower for keyword in keywords)

    def _build_linkedin_people_url(self, user_query: str) -> str:
        """Build a direct LinkedIn People search URL from the user query."""
        # Extract location
        country_code, location = self._extract_location_from_query(user_query)
        
        # Clean query to get role/keywords (remove location and "linkedin")
        clean_query = user_query.lower()
        if location:
            clean_query = clean_query.replace(location.lower(), "")
        
        for keyword in ["linkedin", "profile", "profiles", "in"]:
            clean_query = clean_query.replace(keyword, "")
            
        role = clean_query.strip()
        
        return LinkedInPeopleSearchBuilder.build_people_search_url(
            role=role,
            location=location
        )
    
    def _extract_location_from_query(self, user_query: str) -> tuple[str, str]:
        """Extract location information from user query."""
        
        # Common location patterns
        location_keywords = [
            "berlin", "munich", "hamburg", "cologne", "frankfurt",  # German cities
            "london", "paris", "amsterdam", "zurich", "vienna",      # European cities
            "san francisco", "new york", "london", "berlin",         # Global cities
            "germany", "usa", "uk", "france", "netherlands",        # Countries
            "europe", "european union", "eu"                        # Regions
        ]
        
        query_lower = user_query.lower()
        
        # Check for exact matches first
        for keyword in location_keywords:
            if keyword in query_lower:
                if keyword in ["germany", "usa", "uk", "france", "netherlands"]:
                    return keyword.upper(), keyword.title()
                elif keyword == "berlin":
                    return "DE", keyword.title()  # Berlin -> Germany
                else:
                    return None, keyword.title()  # Other cities don't need country code
        
        # Default to no location filtering
        return None, None
    
    def log_optimization_metrics(self, original_query: str, optimized_params: Dict, urls_found: List[str]):
        """Log metrics about query optimization effectiveness."""
        
        if not urls_found:
            self.logger.info("No URLs found to analyze optimization effectiveness")
            return
        
        # Analyze URL types
        job_board_count = 0
        profile_count = 0
        article_count = 0
        other_count = 0
        
        for url in urls_found:
            if any(domain in url.lower() for domain in self.default_exclude_domains):
                job_board_count += 1
            elif "linkedin.com/in" in url.lower() or "crunchbase.com" in url.lower():
                profile_count += 1
            elif any(ext in url.lower() for ext in [".blog", ".news", "medium.com"]):
                article_count += 1
            else:
                other_count += 1
        
        total_urls = len(urls_found)
        
        metrics = {
            "total_urls": total_urls,
            "job_board_urls": job_board_count,
            "profile_urls": profile_count,
            "article_urls": article_count,
            "other_urls": other_count,
            "job_board_percentage": (job_board_count / total_urls) * 100 if total_urls > 0 else 0,
            "profile_percentage": (profile_count / total_urls) * 100 if total_urls > 0 else 0,
            "original_query": original_query,
            "optimized_query": optimized_params.get("query", ""),
            "reasoning": optimized_params.get("reasoning", "")
        }
        
        self.logger.info(f"Query optimization metrics: {json.dumps(metrics, indent=2)}")
        
        return metrics