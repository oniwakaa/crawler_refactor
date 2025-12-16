import asyncio
import time
from typing import List, Dict, Any, Optional
import structlog
from pathlib import Path
import yaml
import re

from agents.query_builder import QueryBuilderAgent
from tools.firecrawl_client import FirecrawlClient, LINKEDIN_SEARCH_LIMIT
from tools.apify_client import ApifyScraperClient
from utils.url_utils import normalize_linkedin_url

logger = structlog.get_logger()

# Define project root
PROJECT_ROOT = Path(__file__).parent.parent

class WebNavigatorAgent:
    """
    Web Navigator agent responsible for searching and fetching web content.
    Uses Firecrawl for discovery/search and Apify for high-quality LinkedIn profile scraping.
    Firecrawl is also preserved as a general fallback for non-LinkedIn content or if needed.
    """
    
    def __init__(self, settings_path: str = str(PROJECT_ROOT / "config/settings.yaml")):
        """
        Initialize WebNavigatorAgent.
        
        Args:
            settings_path: Path to settings YAML file
        """
        self.settings = self._load_settings(settings_path)
        self.firecrawl_client: Optional[FirecrawlClient] = None
        self.apify_client: Optional[ApifyScraperClient] = None
        
        # Load configuration
        crawling_config = self.settings.get("crawling", {})
        self.max_concurrent = crawling_config.get("max_concurrent", 10)
        
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
        await self.firecrawl_client.__aenter__()
        
        # Initialize Apify client
        self.apify_client = ApifyScraperClient(settings=self.settings)
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.firecrawl_client:
            await self.firecrawl_client.__aexit__(exc_type, exc_val, exc_tb)
        
    async def search_and_fetch(
        self, 
        query: str, 
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search for URLs via Firecrawl and fetch content via Apify (for LinkedIn) or Firecrawl (fallback).
        
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
            
        # Step 2: Search for URLs (using Firecrawl Discovery)
        urls = []
        try:
            # Use existing client if available, or fetch as one-off
            fc_client = self.firecrawl_client 
            if not fc_client:
                fc_client = FirecrawlClient()
            
            # Prepare arguments from optimized_params
            role = query
            location = optimized_params.get("location", "")
            
            skills = None
            if optimized_params.get("include_terms"):
                skills = " ".join(optimized_params["include_terms"])
                
            exclusions = None
            if optimized_params.get("exclude_terms"):
                exclusions = " ".join(f"-{term}" for term in optimized_params["exclude_terms"])
                
            limit_per_step = LINKEDIN_SEARCH_LIMIT
            
            log.info("Executing 3-step LinkedIn discovery", 
                     role=role, location=location, 
                     limit_per_step=limit_per_step)
                     
            urls = await fc_client.discover_linkedin_profiles(
                role=role,
                location=location,
                skills=skills,
                exclusions=exclusions,
                limit_per_step=limit_per_step
            )
            
            # Limit combined results to max_results if needed
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
        
        # Step 3: Fetch content
        # Split URLs into LinkedIn vs others
        linkedin_urls = [u for u in urls if "linkedin.com/in/" in u.lower()]
        other_urls = [u for u in urls if u not in linkedin_urls]
        
        final_results = []
        
        # 3a. Fetch LinkedIn URLs with Apify
        if linkedin_urls:
            log.info("Fetching LinkedIn profiles with Apify", count=len(linkedin_urls))
            try:
                apify_results = self.apify_client.scrape_profiles(linkedin_urls)
                
                # Transform to standard result format
                for res in apify_results:
                    final_results.append({
                        "url": res["url"],
                        "markdown": res["formatted_text"], # Map formatted text to markdown field for content_extractor
                        "fetch_status": "success" if res["success"] else "failed",
                        "error": res.get("error"),
                        "method_used": "apify",
                        "timestamp": res.get("timestamp"),
                        "metadata": {"raw_data": res.get("raw_data")}
                    })
                    
            except Exception as e:
                log.error("Apify batch scraping failed", error=str(e))
                # Mark all as failed
                for url in linkedin_urls:
                     final_results.append({
                        "url": url,
                        "markdown": "",
                        "fetch_status": "failed",
                        "error": str(e),
                        "method_used": "apify",
                        "timestamp": time.time()
                    })

        # 3b. Fetch other URLs with Firecrawl (fallback/generic)
        if other_urls:
            log.info("Fetching non-LinkedIn URLs with Firecrawl", count=len(other_urls))
            try:
                fc_client = self.firecrawl_client or FirecrawlClient()
                other_results = await fc_client.batch_scrape(other_urls)
                
                for res in other_results:
                     final_results.append({
                        "url": res["url"],
                        "markdown": res.get("markdown", ""),
                        "fetch_status": "success" if res.get("markdown") else "failed",
                        "method_used": "firecrawl",
                        "timestamp": time.time()
                    })
            except Exception as e:
                log.error("Firecrawl fetch failed", error=str(e))
                for url in other_urls:
                    final_results.append({
                        "url": url,
                         "markdown": "",
                        "fetch_status": "failed",
                        "error": str(e),
                        "method_used": "firecrawl",
                        "timestamp": time.time()
                    })
        
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

    def _filter_linkedin_profile_urls(self, urls: List[str]) -> List[str]:
        """
        Filter out non-profile LinkedIn URLs (posts, jobs, company pages, etc.)
        """
        filtered_urls = []
        excluded_count = 0
        
        # Regex for excluded patterns
        exclude_pattern = re.compile(r'linkedin\.com/(?:jobs|company|posts|pulse|learning|feed|groups|events)/')
        
        for url in urls:
            url_lower = url.lower()
            
            # If not a LinkedIn URL, keep it (don't filter other sites)
            if "linkedin.com" not in url_lower:
                filtered_urls.append(url)
                continue
                
            # Normalize
            url = normalize_linkedin_url(url)
            url_lower = url.lower()
                
            # If it matches excluded patterns, skip
            if exclude_pattern.search(url_lower):
                excluded_count += 1
                continue
                
            # Must contain /in/ to be a profile
            if "/in/" in url_lower:
                # Check specific sub-pages to exclude
                if any(sub in url_lower for sub in ["/posts/", "/recent-activity/", "/detail/", "/details/"]):
                    excluded_count += 1
                    continue
                    
                filtered_urls.append(url)
            else:
                excluded_count += 1
                
        if excluded_count > 0:
            logger.info("Filtered LinkedIn URLs", total=len(urls), kept=len(filtered_urls), excluded=excluded_count)
            
        return filtered_urls