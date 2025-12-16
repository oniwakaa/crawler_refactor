
import os
import time
import logging
from typing import List, Dict, Any, Optional
from apify_client import ApifyClient
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logger
logger = logging.getLogger(__name__)

class ApifyScraperClient:
    """
    Client for interacting with Apify Actors, specifically for LinkedIn scraping.
    Handles authentication, batching, and result transformation.
    """
    
    def __init__(self, settings: Dict = None):
        """
        Initialize Apify client.
        
        Args:
            settings: Configuration dictionary (from settings.yaml).
        """
        self.settings = settings or {}
        self.apify_config = self.settings.get("apify", {})
        
        # API Token priority: Env Var > Config > Hardcoded (last resort/dev)
        self.api_token = os.getenv("APIFY_API_TOKEN") or self.apify_config.get("api_token")
        
        if not self.api_token:
            logger.warning("Apify API token not found in environment or settings. Scraping may fail.")
            
        self.client = ApifyClient(token=self.api_token)
        self.actor_id = self.apify_config.get("actor_id", "oJMZe85C0opC0xcx2")
        self.batch_size = self.apify_config.get("batch_size", 20)
        self.timeout_seconds = self.apify_config.get("timeout_seconds", 120)
        
    def scrape_profiles(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Scrape multiple LinkedIn profiles in batches.
        
        Args:
            urls: List of LinkedIn profile URLs.
            
        Returns:
            List of dictionaries containing scraped content (formatted text and metadata).
        """
        if not urls:
            return []
            
        results = []
        # Split into batches
        for i in range(0, len(urls), self.batch_size):
            batch_urls = urls[i : i + self.batch_size]
            logger.info(f"Processing batch {i//self.batch_size + 1} with {len(batch_urls)} URLs")
            
            try:
                batch_results = self._run_actor(batch_urls)
                results.extend(batch_results)
            except Exception as e:
                logger.error(f"Batch failed: {e}")
                # Create failure records for this batch
                for url in batch_urls:
                    results.append({
                        "url": url,
                        "formatted_text": "",
                        "raw_data": None,
                        "error": str(e),
                        "success": False
                    })
                    
        return results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _run_actor(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Run the Apify Actor for a specific list of URLs.
        Retries on failure.
        """
        run_input = {
            "profiles": urls
        }
        
        # Start Actor
        logger.info(f"Starting Apify Actor {self.actor_id}...")
        run = self.client.actor(self.actor_id).call(
            run_input=run_input,
            timeout_secs=self.timeout_seconds
        )
        
        if not run:
            raise RuntimeError("Apify Actor run returned None.")
            
        # Get results
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
             raise RuntimeError("No dataset ID returned from Apify run.")
             
        logger.info(f"Fetching results from dataset {dataset_id}...")
        start_time = time.time()
        
        # Fetch items
        items = self.client.dataset(dataset_id).list_items().items
        logger.info(f"Retrieved {len(items)} items from Apify.")
        
        # Map back to original URLs if possible, or just process returned items
        # The actor returns 'profile_url' or 'input' which we can match
        
        processed_results = []
        fetched_map = {item.get("profileUrl") or item.get("input") or item.get("url"): item for item in items}
        
        for url in urls:
            # Try specific matching logic involved in the Actor's output
            # Usually strict match, but sometimes trailing slashes differ
            data = fetched_map.get(url) or fetched_map.get(url + "/") or fetched_map.get(url.rstrip("/"))
            
            if data:
                formatted_text = self._transform_to_text(data)
                processed_results.append({
                    "url": url,
                    "formatted_text": formatted_text,  # For ContentExtractor
                    "raw_data": data,        # For direct enrichment if needed
                    "success": True,
                    "timestamp": time.time(),
                    "fetch_duration": time.time() - start_time
                })
            else:
                # Mark as failed for this specific URL if not found in dataset
                # (Could be invalid, private, or 404)
                logger.warning(f"URL not found in Apify results: {url}")
                processed_results.append({
                    "url": url,
                    "formatted_text": "",
                    "raw_data": None,
                    "success": False,
                    "error": "Not found in scraping results",
                    "timestamp": time.time()
                })
                
        return processed_results

    def _transform_to_text(self, data: Dict) -> str:
        """
        Convert structured JSON to a readable text format for the Content Extractor LLM.
        Uses format compatible with ContentExtractorAgent's section detection.
        """
        lines = []
        
        # Header Section
        full_name = data.get("fullName") or data.get("fullname") or f"{data.get('firstName', '')} {data.get('lastName', '')}".strip() or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
        lines.append(f"Name: {full_name}")
        lines.append(f"Headline: {data.get('headline', 'N/A')}")
        lines.append(f"Location: {data.get('location', {}).get('short', data.get('location', 'N/A'))}")
        lines.append(f"Summary: {data.get('summary') or data.get('about') or 'N/A'}")
        
        # Add contact info if available
        email = data.get("email")
        if email:
            lines.append(f"Email: {email}")
        
        phone = data.get("phone") or data.get("phoneNumber") or data.get("phone_number")
        if phone:
            lines.append(f"Phone: {phone}")
            
        lines.append(f"Profile URL: {data.get('profileUrl') or data.get('profile_url') or data.get('url', '')}")
        
        # Experience Section
        lines.append("\n# Experience")
        experiences = data.get("experience", [])
        for exp in experiences:
            title = exp.get("title", "Unknown Title")
            company = exp.get("company", "Unknown Company")
            duration = exp.get("duration") or f"{exp.get('startDate', {}).get('year', '')} - {exp.get('endDate', {}).get('year', 'Present')}"
            desc = exp.get("description", "")
            lines.append(f"Title: {title}")
            lines.append(f"Company: {company}")
            lines.append(f"Duration: {duration}")
            if desc:
                lines.append(f"Description: {desc[:500]}..." if len(desc) > 500 else f"Description: {desc}")
            lines.append("---")

        # Education Section
        lines.append("\n# Education")
        education = data.get("education", [])
        for edu in education:
            school = edu.get("schoolName") or edu.get("school", "Unknown School")
            degree = edu.get("degree") or edu.get("degreeName", "")
            lines.append(f"School: {school}")
            lines.append(f"Degree: {degree}")
            lines.append("---")
            
        return "\n".join(lines)
