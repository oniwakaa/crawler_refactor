import asyncio
import time
from typing import List, Dict, Any, Optional
import structlog
from pathlib import Path
import yaml

from agents.query_builder import QueryBuilderAgent
from tools.firecrawl_client import FirecrawlClient
from tools.crawl4ai_client import Crawl4AIClient

logger = structlog.get_logger()

class WebNavigatorAgent:
    """
    Web Navigator agent responsible for searching and fetching web content.
    Uses Firecrawl for search and both Crawl4AI (primary) and Firecrawl (fallback) for content fetching.
    """
    
    def __init__(self, settings_path: str = "config/settings.yaml"):
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
        self.crawl4ai_client = Crawl4AIClient()
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
                
                if not urls:
                    log.warning("Search returned no URLs")
                    return []
                    
                log.info("Search completed", url_count=len(urls))
                
                # Limit URLs to max_results
                urls = urls[:max_results]
                
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
                
        except Exception as e:
            log.error("Search and fetch failed", error=str(e))
            return []
            
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
            
    async def _fetch_with_concurrency_limit(
        self, 
    ) -> None:
        """
        This method is not implemented as we're using the clients' built-in
        concurrency handling. Crawl4AI's arun_many handles concurrency internally,
        and Firecrawl's batch_scrape is designed for parallel processing.
        """
        pass