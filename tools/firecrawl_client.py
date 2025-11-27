import os
import httpx
import structlog
from typing import List, Dict, Optional, Any
import asyncio

logger = structlog.get_logger()

class FirecrawlClient:
    """
    Client for Firecrawl API to handle web searching and scraping.
    Uses Firecrawl v2 API endpoints based on documentation.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            logger.warning("FIRECRAWL_API_KEY not found in environment variables")
        
        # Firecrawl v2 API endpoint
        self.base_url = "https://api.firecrawl.dev/v2"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = httpx.Timeout(120.0)  # Increased for batch operations
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def search(self, query: str, max_results: int = 5) -> List[str]:
        """
        Perform a web search and return a list of URLs.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of URLs found by the search
        """
        log = logger.bind(query=query, max_results=max_results)
        if not self.api_key:
            log.error("Cannot search without API key")
            return []

        try:
            # Firecrawl search endpoint
            payload = {
                "query": query,
                "limit": max_results,
                "scrapeOptions": {"formats": ["markdown"]}
            }
            
            response = await self._make_request(
                "POST",
                f"{self.base_url}/search",
                json=payload
            )
            
            # Extract URLs from search results
            data = response.get("data", [])
            results = []
            
            # Handle v2 response structure where data is a dict with 'web', 'news', etc.
            if isinstance(data, dict):
                results = data.get("web", [])
            elif isinstance(data, list):
                results = data
            
            urls = []
            for item in results:
                if isinstance(item, dict) and "url" in item:
                    url = item["url"]
                    # Ensure URL is valid (starts with http/https)
                    if url.startswith(('http://', 'https://')):
                        urls.append(url)
                elif isinstance(item, str) and item.startswith(('http://', 'https://')):
                    urls.append(item)
            
            log.info("Search successful", url_count=len(urls))
            return urls

        except httpx.HTTPStatusError as e:
            log.error("Firecrawl API error", status_code=e.response.status_code, response=e.response.text)
            return []
        except Exception as e:
            log.error("Search failed", error=str(e))
            return []

    async def batch_scrape(self, urls: List[str], formats: List[str] = None) -> List[Dict[str, Any]]:
        """
        Scrape multiple URLs using Firecrawl's batch scrape endpoint.
        
        Args:
            urls: List of URLs to scrape
            formats: List of formats to return (default: ["markdown"])
            
        Returns:
            List of dictionaries containing scraped content and metadata
        """
        if formats is None:
            formats = ["markdown"]
            
        log = logger.bind(url_count=len(urls), formats=formats)
        if not self.api_key:
            log.error("Cannot scrape without API key")
            return []

        if not urls:
            log.warning("No URLs provided for batch scrape")
            return []

        try:
            # Use batch_scrape endpoint for multiple URLs
            # Firecrawl v2 uses scrapeOptions for formats
            payload = {
                "urls": urls,
                "scrapeOptions": {
                    "formats": formats
                }
            }
            
            response = await self._make_request(
                "POST",
                f"{self.base_url}/batch/scrape",
                json=payload
            )
            
            # Wait for batch to complete
            job_id = response.get("id") or response.get("jobId")  # Handle potential API variations
            if not job_id:
                log.error("No job ID returned from batch scrape", response=response)
                return []
            
            results = await self._poll_batch_job(job_id)
            return results

        except httpx.HTTPStatusError as e:
            log.error("Batch scrape API error", 
                     status_code=e.response.status_code, 
                     response=e.response.text,
                     payload=payload)
            return []
        except Exception as e:
            log.error("Batch scrape failed", error=str(e))
            return []

    async def _poll_batch_job(self, job_id: str, poll_interval: int = 2, max_wait: int = 120) -> List[Dict[str, Any]]:
        """
        Poll batch job until completion or timeout.
        
        Args:
            job_id: Batch job ID
            poll_interval: Seconds between poll attempts
            max_wait: Maximum seconds to wait
            
        Returns:
            List of scraped results
        """
        log = logger.bind(job_id=job_id)
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > max_wait:
                log.error("Batch job polling timed out", max_wait=max_wait)
                return []
            
            try:
                response = await self._make_request(
                    "GET",
                    f"{self.base_url}/batch/scrape/{job_id}"
                )
                
                status = response.get("status", "")
                if status == "completed":
                    data = response.get("data", [])
                    # Transform the response to match expected format
                    results = []
                    for item in data:
                        if isinstance(item, dict):
                            # Extract URL from the data if available
                            url = item.get("url") or item.get("metadata", {}).get("sourceURL", "unknown")
                            results.append({
                                "url": url,
                                "markdown": item.get("markdown", ""),
                                "metadata": item.get("metadata", {})
                            })
                    log.info("Batch scrape completed", result_count=len(results))
                    return results
                elif status == "failed":
                    log.error("Batch scrape failed", error=response.get("error"))
                    return []
                    
            except Exception as e:
                log.warning("Poll request failed", error=str(e))
            
            await asyncio.sleep(poll_interval)

    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """
        Make HTTP request with error handling and response validation.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for httpx request
            
        Returns:
            JSON response as dictionary
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use async context manager.")
            
        response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
