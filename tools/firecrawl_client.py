import os
import httpx
import structlog
from typing import List, Dict, Optional, Any, Set
import asyncio
import jsonschema
from urllib.parse import urlparse, urlunparse

logger = structlog.get_logger()

# Firecrawl v2 Search Schema
FIRECRAWL_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "minLength": 1},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        "lang": {"type": "string", "pattern": "^[a-z]{2}$"},
        "location": {"type": "string"},
        "timeout": {"type": "integer", "minimum": 1000},
        "scrapeOptions": {
            "type": "object",
            "properties": {
                "formats": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["markdown", "html", "rawHtml", "links", "screenshot", "extract", "screenshot@fullPage"]}
                }
            }
        }
    },
    "required": ["query"],
    "additionalProperties": True # Allow other optional params firecrawl might add
}

# Constant for maximizing LinkedIn profile discovery
LINKEDIN_SEARCH_LIMIT = 50

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

    def validate_search_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and fix search parameters against the schema.
        
        Args:
            params: Dictionary of search parameters
            
        Returns:
            Validated dictionary of parameters
            
        Raises:
            jsonschema.ValidationError: If params are invalid and cannot be fixed
        """
        # Create a copy to modify
        validated = params.copy()
        
        # Ensure query exists
        if "query" not in validated:
            raise ValueError("Search request must include a 'query' field")
            
        # Validate against schema
        try:
            jsonschema.validate(instance=validated, schema=FIRECRAWL_SEARCH_SCHEMA)
        except jsonschema.ValidationError as e:
            logger.warning(f"Schema validation failed: {e.message}. Attempting to fix...")
            # Simple fixes could go here, or just let it fail if strict
            # For now, we rely on the caller to provide mostly correct data
            raise e
            
        return validated

    def _normalize_linkedin_url(self, url: str) -> Optional[str]:
        """
        Normalize and validate LinkedIn profile URL.
        
        Args:
            url: Raw URL string
            
        Returns:
            Normalized URL or None if invalid
        """
        if not url:
            return None
            
        try:
            # Parse URL
            parsed = urlparse(url)
            
            # Enforce HTTPS
            scheme = "https"
            
            # Standardize host (remove www., ensure linkedin.com)
            netloc = parsed.netloc.lower()
            if "linkedin.com" not in netloc:
                return None
            
            netloc = "www.linkedin.com" # Consistently use www for profiles
            
            # Path should be /in/username
            path = parsed.path
            # Remove trailing slash
            if path.endswith('/'):
                path = path[:-1]
                
            # Must match /in/ pattern
            if not path.startswith("/in/"):
                return None
                
            # Reconstruct without query strings or fragments
            clean_url = urlunparse((scheme, netloc, path, '', '', ''))
            return clean_url
            
        except Exception as e:
            logger.debug(f"Error normalizing URL {url}: {e}")
            return None

    async def discover_linkedin_profiles(
        self, 
        role: str, 
        location: str, 
        skills: Optional[str] = None, 
        exclusions: Optional[str] = None,
        limit_per_step: Optional[int] = None
    ) -> List[str]:
        """
        Discover LinkedIn profiles using a 3-step search strategy.
        
        1. Broad discovery: role + location
        2. Specificity: role + location + skills
        3. Exclusion/Synonyms: synonyms + location + exclusions
        
        Args:
            role: Target job role (e.g. "CTO", "Sales Manager")
            location: Target location (e.g. "Berlin", "Italy")
            skills: Optional specific skills or niche terms
            exclusions: Optional terms to exclude (e.g. "-recruiter -consultant")
            limit_per_step: Max results per search step (defaults to LINKEDIN_SEARCH_LIMIT)
            
        Returns:
            List of unique, normalized LinkedIn profile URLs
        """
        if limit_per_step is None:
            limit_per_step = LINKEDIN_SEARCH_LIMIT
            
        total_capacity = limit_per_step * 3
        log = logger.bind(
            task="linkedin_discovery", 
            role=role, 
            location=location,
            limit_per_step=limit_per_step,
            potential_capacity=total_capacity
        )
        
        log.info(f"Starting LinkedIn discovery (Capacity: up to {total_capacity} profiles via 3 calls x {limit_per_step})")
        
        unique_urls: Set[str] = set()
        
        # Base operator
        site_operator = "site:linkedin.com/in/"
        
        # --- Step 1: Broad Discovery ---
        query1 = f'{role} {location} {site_operator}'
        # --- Step 1: Broad Discovery ---
        query1 = f'{role} {location} {site_operator}'
        log.info(f"Executing Firecrawl search Call 1 (broad) with limit={limit_per_step}", query=query1)
        
        try:
            urls1 = await self.search(query=query1, max_results=limit_per_step)
            for url in urls1:
                norm = self._normalize_linkedin_url(url)
                if norm:
                    unique_urls.add(norm)
        except Exception as e:
            log.error("Step 1 failed", error=str(e))

        # --- Step 2: Specificity (if skills provided) ---
        if skills:
            query2 = f'{role} {location} {skills} {site_operator}'
        if skills:
            query2 = f'{role} {location} {skills} {site_operator}'
            log.info(f"Executing Firecrawl search Call 2 (specificity) with limit={limit_per_step}", query=query2)
            try:
                urls2 = await self.search(query=query2, max_results=limit_per_step)
                new_count = 0
                for url in urls2:
                    norm = self._normalize_linkedin_url(url)
                    if norm and norm not in unique_urls:
                        unique_urls.add(norm)
                        new_count += 1
                log.info("Step 2 results", new_found=new_count)
            except Exception as e:
                log.error("Step 2 failed", error=str(e))
        
        # --- Step 3: Synonyms/Exclusions (if exclusions provided) ---
        if exclusions:
             # Construct a query that emphasizes exclusions or alternatives
             # Assuming exclusions string starts with '-' or just terms
             query3 = f'{role} {location} {exclusions} {site_operator}'
             # Assuming exclusions string starts with '-' or just terms
             query3 = f'{role} {location} {exclusions} {site_operator}'
             log.info(f"Executing Firecrawl search Call 3 (exclusions) with limit={limit_per_step}", query=query3)
             try:
                urls3 = await self.search(query=query3, max_results=limit_per_step)
                new_count = 0
                for url in urls3:
                    norm = self._normalize_linkedin_url(url)
                    if norm and norm not in unique_urls:
                        unique_urls.add(norm)
                        new_count += 1
                log.info("Step 3 results", new_found=new_count)
             except Exception as e:
                log.error("Step 3 failed", error=str(e))

        results = list(unique_urls)
        log.info("Discovery completed", total_unique=len(results))
        return results

    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[str]:
        """
        Perform a web search and return a list of URLs.
        Now validated against FIRECRAWL_SEARCH_SCHEMA.
        """
        log = logger.bind(query=query, max_results=max_results)
        if not self.api_key:
            log.error("Cannot search without API key")
            return []

        try:
            # Build payload
            payload = {
                "query": query,
                "limit": max_results,
            }
            # Add optional kwargs if they fit the schema or are generic
            if "scrapeOptions" in kwargs:
                payload["scrapeOptions"] = kwargs["scrapeOptions"]
            if "lang" in kwargs:
                payload["lang"] = kwargs["lang"]
            if "location" in kwargs:
                payload["location"] = kwargs["location"]
            if "timeout" in kwargs:
                payload["timeout"] = kwargs["timeout"]
                
            # Validate payload
            try:
                self.validate_search_params(payload)
            except Exception as e:
                log.error("Invalid search parameters", error=str(e))
                # For safety, we might want to return empty or proceed if simple
                return []
            
            log.info("Firecrawl search parameters", parameters=payload)
            
            response = await self._make_request(
                "POST",
                f"{self.base_url}/search",
                json=payload
            )
            
            # Extract URLs from search results
            data = response.get("data", [])
            results = []
            
            if isinstance(data, dict):
                results = data.get("web", []) # v2 typical response
                # Fallback or check for 'data' key inside if wrapped differently?
                # The provided example showed data: { web: [...] } or [...]
            elif isinstance(data, list):
                results = data
            
            urls = []
            for item in results:
                url_val = None
                if isinstance(item, dict):
                    url_val = item.get("url")
                elif isinstance(item, str):
                    url_val = item
                
                if url_val and isinstance(url_val, str) and url_val.startswith(('http://', 'https://')):
                    urls.append(url_val)
            
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
            payload = {
                "urls": urls,
                "formats": formats
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
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use async context manager.")
            
        response = await self.client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    async def search_for_domain(self, query: str) -> List[str]:
        """
        Search for a company's domain.
        """
        # Use existing search method
        return await self.search(query, max_results=3)
        
    async def fetch_homepage(self, url: str) -> Dict[str, Any]:
        """
        Fetch content of a homepage for validation.
        """
        # Use batch_scrape for single URL
        results = await self.batch_scrape([url], formats=["markdown"])
        if results:
            return results[0]
        return {"url": url, "markdown": "", "error": "No result returned"}
