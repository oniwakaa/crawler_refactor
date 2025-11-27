import asyncio
import time
from typing import List, Dict, Optional, Any
import structlog
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

logger = structlog.get_logger()

class Crawl4AIClient:
    """
    Client for Crawl4AI to handle web crawling and content extraction.
    Uses AsyncWebCrawler with resource-aware batch processing.
    """
    
    def __init__(self, browser_config: Optional[BrowserConfig] = None):
        """
        Initialize Crawl4AI client.
        
        Args:
            browser_config: BrowserConfig for crawler initialization.
                           If None, uses default config.
        """
        self.browser_config = browser_config or BrowserConfig(
            browser_type="chromium",
            headless=True,
            verbose=False
        )
        self.crawler: Optional[AsyncWebCrawler] = None
        self.retry_attempts = 3
        self.retry_delay = 1.0  # Initial delay in seconds
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.crawler = AsyncWebCrawler(config=self.browser_config)
        await self.crawler.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.crawler:
            await self.crawler.close()
            self.crawler = None
            
    async def batch_fetch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch multiple URLs using Crawl4AI's arun method with retry logic.
        
        Args:
            urls: List of URLs to fetch
            
        Returns:
            List of dictionaries containing fetched content and metadata
        """
        if not self.crawler:
            raise RuntimeError("Crawler not initialized. Use async context manager.")
            
        if not urls:
            logger.warning("No URLs provided for batch fetch")
            return []
            
        log = logger.bind(url_count=len(urls))
        log.info("Starting batch fetch")
        
        results = []
        batch_start_time = time.time()
        
        # Process URLs with retry logic
        for url in urls:
            url_start_time = time.time()
            result = await self._fetch_with_retry(url)
            
            fetch_duration = time.time() - url_start_time
            result["fetch_duration"] = fetch_duration
            results.append(result)
        
        total_duration = time.time() - batch_start_time
        success_count = len([r for r in results if r["fetch_status"] == "success"])
        
        log.info(
            "Batch fetch completed",
            success_count=success_count,
            total_count=len(results),
            total_duration=total_duration
        )
        
        return results
    
    async def _fetch_with_retry(self, url: str) -> Dict[str, Any]:
        """
        Fetch a single URL with exponential backoff retry logic.
        
        Args:
            url: URL to fetch
            
        Returns:
            Dictionary containing fetched content and metadata
        """
        log = logger.bind(url=url)
        last_error = None
        
        for attempt in range(self.retry_attempts):
            try:
                # Configure crawl settings
                crawl_config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    word_count_threshold=10
                )
                
                result = await self.crawler.arun(url=url, config=crawl_config)
                
                if result.success:
                    return {
                        "url": url,
                        "markdown": getattr(result, 'markdown', ''),
                        "html": getattr(result, 'html', ''),
                        "fetch_status": "success",
                        "timestamp": time.time(),
                        "error": None
                    }
                else:
                    last_error = result.error_message
                    log.warning(
                        "Fetch attempt failed",
                        attempt=attempt + 1,
                        error=result.error_message
                    )
                    
            except Exception as e:
                last_error = str(e)
                log.warning(
                    "Fetch attempt failed with exception",
                    attempt=attempt + 1,
                    error=str(e)
                )
            
            # Wait before retry (exponential backoff)
            if attempt < self.retry_attempts - 1:
                delay = self.retry_delay * (2 ** attempt)
                log.debug("Retrying after delay", delay=delay)
                await asyncio.sleep(delay)
        
        # All attempts failed
        log.error("All fetch attempts failed", attempts=self.retry_attempts)
        return {
            "url": url,
            "markdown": "",
            "html": "",
            "fetch_status": "failed",
            "timestamp": time.time(),
            "error": last_error
        }