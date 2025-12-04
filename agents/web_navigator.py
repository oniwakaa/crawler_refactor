import asyncio
import time
from typing import List, Dict, Any, Optional
import structlog
from pathlib import Path
import yaml
import re

from agents.query_builder import QueryBuilderAgent
from tools.firecrawl_client import FirecrawlClient
from tools.crawl4ai_client import Crawl4AIClient
from utils.url_utils import normalize_linkedin_url

logger = structlog.get_logger()

# Define project root
PROJECT_ROOT = Path(__file__).parent.parent

class WebNavigatorAgent:
    """
    Web Navigator agent responsible for searching and fetching web content.
    Uses Firecrawl for search and both Crawl4AI (primary) and Firecrawl (fallback) for content fetching.
    """
    
    def __init__(self, settings_path: str = str(PROJECT_ROOT / "config/settings.yaml")):
        """
        Initialize WebNavigatorAgent.
        
        Args:
            settings_path: Path to settings YAML file
        """
        self.settings = self._load_settings(settings_path)
        self.firecrawl_client: Optional[FirecrawlClient] = None
        self.crawl4ai_client: Optional[Crawl4AIClient] = None
        
        # Load configuration
        crawling_config = self.settings.get("crawling", {})
        self.max_concurrent = crawling_config.get("max_concurrent", 10)
        self.fallback_to_firecrawl = crawling_config.get("fallback_to_firecrawl", True)
        
        # Initialize QueryBuilderAgent for query optimization
        self.query_builder = QueryBuilderAgent()
        
    def _load_settings(self, settings_path: str) -> Dict[str, Any]:
        """Load settings from YAML file"""
        try:
            with open(settings_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Failed to load settings", error=str(e), path=settings_path)
            return {}
            
    async def __aenter__(self):
        """Async context manager entry"""
        self.firecrawl_client = FirecrawlClient()
        
        # Initialize Crawl4AI client with authentication if enabled
        linkedin_config = self.settings.get("linkedin", {})
        linkedin_auth_enabled = linkedin_config.get("auth_enabled", False)
        
        self.crawl4ai_client = Crawl4AIClient(
            linkedin_auth=linkedin_auth_enabled,
            settings=self.settings
        )
        await self.crawl4ai_client.__aenter__()
        
        # Validate session if auth enabled
        if linkedin_auth_enabled:
            session_valid = await self.crawl4ai_client.validate_linkedin_session()
            if session_valid:
                logger.info("LinkedIn authentication active - using authenticated session")
            else:
                logger.error(
                    "LinkedIn session invalid or expired. "
                    "Please refresh session: python scripts/refresh_linkedin_auth.py"
                )
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Clients will be closed by their own context managers
        pass
        
    async def search_and_fetch(
        self, 
        query: str, 
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search for URLs and fetch their content with fallback logic.
        
        Args:
            query: Search query
            max_results: Maximum number of results to fetch
            
        Returns:
            List of dictionaries containing fetched content and metadata
        """
        log = logger.bind(query=query, max_results=max_results)
        log.info("Starting search and fetch")
        
        start_time = time.time()
        
        # Step 1: Build optimized query
        try:
            log.info("Building optimized search query")
            optimized_params = self.query_builder.build_firecrawl_parameters(query)
            
            # Log the optimization
            log.info(
                "Query optimization completed",
                original_query=query,
                optimized_query=optimized_params["query"],
                reasoning=optimized_params.get("reasoning", ""),
                exclude_terms=optimized_params.get("exclude_terms", []),
                include_terms=optimized_params.get("include_terms", [])
            )
            
        except Exception as e:
            log.error("Query optimization failed", error=str(e))
            # Use fallback query parameters
            optimized_params = {
                "query": query,
                "limit": max_results,
                "sources": ["web"],
                "timeout": 60000,
                "ignoreInvalidURLs": True
            }
            log.warning("Using fallback query parameters")
            
        # Step 2: Search for URLs
        # Check for direct LinkedIn search
        if optimized_params.get("search_type") == "linkedin_people":
            log.info("Executing direct LinkedIn People search")
            urls = await self._fetch_linkedin_people_search(
                optimized_params["direct_url"], 
                max_results
            )
        else:
            # Standard Firecrawl search
            try:
                async with self.firecrawl_client as fc_client:
                    # Extract search parameters from optimized_params
                    query = optimized_params["query"]
                    max_results_param = max_results
                    
                    # Extract additional parameters (excluding query)
                    additional_params = {
                        key: value for key, value in optimized_params.items()
                        if key not in ["query"]
                    }
                    
                    urls = await fc_client.search(query, max_results_param, **additional_params)
                    
                    # Limit URLs to max_results
                    urls = urls[:max_results]
                    
            except Exception as e:
                log.error("Search failed", error=str(e))
                urls = []
            
        if not urls:
            log.warning("Search returned no URLs")
            return []
            
        log.info("Search completed", url_count=len(urls))
        
        # Filter URLs to keep only valid profiles if they are LinkedIn URLs
        urls = self._filter_linkedin_profile_urls(urls)
        
        # Step 3: Fetch content with primary method (Crawl4AI)
        crawl4ai_results = await self._fetch_with_crawl4ai(urls)
        
        # Step 4: For failed fetches, use fallback if enabled
        final_results = crawl4ai_results
        
        if self.fallback_to_firecrawl:
            failed_urls = [
                result["url"] for result in crawl4ai_results 
                if result.get("fetch_status") == "failed"
            ]
            
            if failed_urls:
                log.info("Using Firecrawl fallback for failed URLs", failed_count=len(failed_urls))
                fallback_results = await self._fetch_with_firecrawl_fallback(failed_urls)
                
                # Replace failed results with fallback results
                final_results = []
                for result in crawl4ai_results:
                    if result["url"] in failed_urls:
                        # Find corresponding fallback result
                        fallback_result = next(
                            (fr for fr in fallback_results if fr["url"] == result["url"]),
                            None
                        )
                        if fallback_result:
                            final_results.append(fallback_result)
                        else:
                            final_results.append(result)  # Keep original failed result
                    else:
                        final_results.append(result)
        
        # Calculate statistics
        total_duration = time.time() - start_time
        successful_fetches = len([
            r for r in final_results 
            if r.get("fetch_status") == "success"
        ])
        
        method_distribution = {}
        for result in final_results:
            method = result.get("method_used", "unknown")
            method_distribution[method] = method_distribution.get(method, 0) + 1
        
        # Step 5: Log query optimization effectiveness
        try:
            self.query_builder.log_optimization_metrics(
                original_query=query,
                optimized_params=optimized_params,
                urls_found=[result["url"] for result in final_results]
            )
        except Exception as metrics_error:
            log.warning("Failed to log optimization metrics", error=str(metrics_error))
        
        log.info(
            "Search and fetch completed",
            total_urls=len(final_results),
            successful_fetches=successful_fetches,
            total_duration=total_duration,
            method_distribution=method_distribution
        )
        
        return final_results
                
    async def _fetch_with_crawl4ai(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch URLs using Crawl4AI as primary method.
        
        Args:
            urls: List of URLs to fetch
            
        Returns:
            List of fetch results with method_used="crawl4ai"
        """
        log = logger.bind(url_count=len(urls))
        log.info("Fetching with Crawl4AI")
        
        try:
            async with self.crawl4ai_client as crawler:
                results = await crawler.batch_fetch(urls)
                
                # Add method_used field
                for result in results:
                    result["method_used"] = "crawl4ai"
                    
                return results
                
        except Exception as e:
            log.error("Crawl4AI fetch failed", error=str(e))
            # Return failed results for all URLs
            return [
                {
                    "url": url,
                    "markdown": "",
                    "html": "",
                    "fetch_status": "failed",
                    "method_used": "crawl4ai",
                    "error": str(e),
                    "timestamp": time.time()
                }
                for url in urls
            ]
            
    async def _fetch_with_firecrawl_fallback(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch URLs using Firecrawl as fallback method.
        
        Args:
            urls: List of URLs to fetch
            
        Returns:
            List of fetch results with method_used="firecrawl"
        """
        log = logger.bind(url_count=len(urls))
        log.info("Fetching with Firecrawl fallback")
        
        try:
            async with self.firecrawl_client as fc_client:
                results = await fc_client.batch_scrape(urls)
                
                # Convert Firecrawl format to standard format
                converted_results = []
                for result in results:
                    converted_result = {
                        "url": result["url"],
                        "markdown": result.get("markdown", ""),
                        "html": result.get("html", ""),
                        "fetch_status": "success" if result.get("markdown") else "failed",
                        "method_used": "firecrawl",
                        "metadata": result.get("metadata", {}),
                        "timestamp": time.time()
                    }
                    converted_results.append(converted_result)
                    
                return converted_results
                
        except Exception as e:
            log.error("Firecrawl fallback failed", error=str(e))
            # Return failed results for all URLs
            return [
                {
                    "url": url,
                    "markdown": "",
                    "html": "",
                    "fetch_status": "failed",
                    "method_used": "firecrawl",
                    "error": str(e),
                    "timestamp": time.time()
                }
                for url in urls
            ]
            


    def _filter_linkedin_profile_urls(self, urls: List[str]) -> List[str]:
        """
        Filter out non-profile LinkedIn URLs (posts, jobs, company pages, etc.)
        
        Args:
            urls: List of URLs to filter
            
        Returns:
            List of filtered URLs containing only valid profiles or non-LinkedIn URLs
        """
        filtered_urls = []
        excluded_count = 0
        
        # Regex for valid LinkedIn profile URL
        # Matches: linkedin.com/in/username
        # Excludes: /posts/, /jobs/, /company/, /pulse/, /learning/
        profile_pattern = re.compile(r'linkedin\.com/in/[^/]+/?(?:$|\?|#)')
        
        # Regex for excluded patterns
        exclude_pattern = re.compile(r'linkedin\.com/(?:jobs|company|posts|pulse|learning|feed|groups|events)/')
        
        # Get authenticated user URL from settings to prevent self-scraping
        linkedin_config = self.settings.get("linkedin", {})
        auth_user_url = linkedin_config.get("authenticated_user_url", "")
        if auth_user_url:
            auth_user_url = normalize_linkedin_url(auth_user_url).lower()
        
        for url in urls:
            url_lower = url.lower()
            
            # If not a LinkedIn URL, keep it (don't filter other sites)
            if "linkedin.com" not in url_lower:
                filtered_urls.append(url)
                continue
                
            # Normalize LinkedIn URL (handle regional subdomains)
            url = normalize_linkedin_url(url)
            url_lower = url.lower()
                
            # If it matches excluded patterns, skip
            if exclude_pattern.search(url_lower):
                excluded_count += 1
                continue
                
            # Check if it matches authenticated user
            if auth_user_url and (auth_user_url in url_lower or url_lower in auth_user_url):
                logger.info("Skipping authenticated user profile URL", url=url)
                excluded_count += 1
                continue
                
            # If it contains /in/ but has extra path segments like /details/ or /posts/
            # We want to keep the base profile but might need to clean it
            # For now, just check if it looks like a profile
            if "/in/" in url_lower:
                # Check if it's a sub-page of a profile (e.g. /in/user/details/experience/)
                # We might want to keep these if we can strip them, or skip them
                # The requirement says "exclude /posts/, /jobs/"
                
                # Check specific sub-pages to exclude
                if any(sub in url_lower for sub in ["/posts/", "/recent-activity/", "/detail/", "/details/"]):
                    excluded_count += 1
                    continue
                    
                filtered_urls.append(url)
            else:
                # LinkedIn URL but not /in/ (e.g. /pub/, /sales/) - skip for now to be safe
                excluded_count += 1
                
        if excluded_count > 0:
            logger.info(
                "Filtered LinkedIn URLs", 
                total=len(urls), 
                kept=len(filtered_urls), 
                excluded=excluded_count
            )
            
        return filtered_urls

    async def _fetch_linkedin_people_search(self, search_url: str, max_results: int) -> List[str]:
        """
        Execute a direct LinkedIn People search and extract profile URLs.
        
        Args:
            search_url: The LinkedIn search URL
            max_results: Maximum number of profiles to extract
            
        Returns:
            List of profile URLs found
        """
        log = logger.bind(search_url=search_url)
        log.info("Fetching LinkedIn search results page")
        
        try:
            # Use Crawl4AI to fetch the search page
            # We need to use the authenticated client
            async with self.crawl4ai_client as crawler:
                # Fetch the search page
                # We use a single URL fetch here
                results = await crawler.batch_fetch([search_url])
                
                if not results or results[0].get("fetch_status") != "success":
                    log.error("Failed to fetch LinkedIn search page")
                    return []
                    
                content = results[0].get("markdown", "") + results[0].get("html", "")
                
                # Extract profile URLs from content
                # Look for href="/in/username" or full URLs
                # Regex to find LinkedIn profile links
                # Matches: https://www.linkedin.com/in/username or /in/username
                
                # Find all links that look like profiles
                # Pattern for full URLs
                full_url_pattern = re.compile(r'https://(?:www\.)?linkedin\.com/in/[^/"\s?]+')
                full_matches = full_url_pattern.findall(content)
                
                # Pattern for relative URLs (common in HTML)
                relative_pattern = re.compile(r'href=["\'](/in/[^/"\s?]+)')
                relative_matches = relative_pattern.findall(content)
                
                # Combine and normalize
                found_urls = set()
                
                for match in full_matches:
                    found_urls.add(match)
                    
                for match in relative_matches:
                    found_urls.add(f"https://www.linkedin.com{match}")
                    
                # Clean URLs (remove trailing slashes, etc.)
                cleaned_urls = []
                for url in found_urls:
                    # Basic cleaning
                    url = url.rstrip("/")
                    cleaned_urls.append(url)
                    
                log.info("Extracted URLs from search page", count=len(cleaned_urls))
                
                return list(cleaned_urls)[:max_results]
                
        except Exception as e:
            log.error("LinkedIn people search failed", error=str(e))
            return []