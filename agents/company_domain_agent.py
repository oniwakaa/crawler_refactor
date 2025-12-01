import asyncio
import structlog
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from pydantic import BaseModel, Field

from tools.firecrawl_client import FirecrawlClient
from tools.llama_wrapper import LlamaWrapper

logger = structlog.get_logger()

# Define project root
PROJECT_ROOT = Path(__file__).parent.parent

class DomainValidationModel(BaseModel):
    confidence_score: float = Field(..., description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(..., description="Reasoning for the score")

class CompanyDomainAgent:
    """
    Agent responsible for discovering company domains.
    Searches for company website and validates the match.
    """
    
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.firecrawl_client: Optional[FirecrawlClient] = None
        self.llama_wrapper: Optional[LlamaWrapper] = None
        
        models_config = self.settings.get("models", {})
        self.model_name = models_config.get("enricher", "hf.co/unsloth/SmolLM3-3B-GGUF:Q4_K_M")
        self.ollama_host = models_config.get("ollama_host", "http://localhost:11434")
        
    async def __aenter__(self):
        self.firecrawl_client = FirecrawlClient()
        self.llama_wrapper = LlamaWrapper(ollama_host=self.ollama_host)
        await self.firecrawl_client.__aenter__()
        await self.llama_wrapper.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.firecrawl_client:
            await self.firecrawl_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.llama_wrapper:
            await self.llama_wrapper.__aexit__(exc_type, exc_val, exc_tb)
            
    async def find_company_domain(self, company_name: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Find the official website domain for a company.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Tuple of (domain, metadata)
        """
        if not company_name or company_name.lower() in ["unknown", "unknown company", "none"]:
            return None, {"status": "skipped", "reason": "invalid_company_name"}
            
        log = logger.bind(company_name=company_name)
        log.info("Searching for company domain")
        
        metadata = {
            "status": "failed",
            "stages": [],
            "candidates": []
        }
        
        try:
            # 1. Search for domain
            query = f"{company_name} official website"
            urls = await self.firecrawl_client.search_for_domain(query)
            metadata["stages"].append("search")
            
            if not urls:
                log.warning("No URLs found")
                metadata["reason"] = "no_search_results"
                return None, metadata
                
            # Take top 3 candidates
            candidates = urls[:3]
            best_domain = None
            best_score = 0.0
            
            # 2. Validate candidates
            for url in candidates:
                # Extract domain from URL for logging
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                except:
                    domain = url
                    
                # Fetch homepage content for validation
                # We use a lightweight fetch or just use the snippet if available?
                # The plan says "fetch_homepage(domain) -> uses batch_scrape"
                # But searching gives us URLs.
                
                # Let's try to validate based on URL and maybe snippet if we had it, 
                # but better to fetch the page content to be sure.
                
                content_result = await self.firecrawl_client.fetch_homepage(url)
                content_excerpt = content_result.get("markdown", "")[:500] # First 500 chars (reduced from 1000)
                title = content_result.get("metadata", {}).get("title", "")
                
                score, reasoning = await self._validate_domain(company_name, url, title, content_excerpt)
                
                metadata["candidates"].append({
                    "url": url,
                    "score": score,
                    "reasoning": reasoning
                })
                
                if score > best_score:
                    best_score = score
                    best_domain = domain
                    
            if best_score > 0.7:
                log.info("Domain found", domain=best_domain, score=best_score)
                metadata["status"] = "success"
                metadata["selected_domain"] = best_domain
                metadata["confidence"] = best_score
                return best_domain, metadata
            else:
                log.info("No domain met confidence threshold", best_score=best_score)
                metadata["reason"] = "low_confidence"
                return None, metadata
                
        except Exception as e:
            log.error("Domain discovery failed", error=str(e))
            metadata["error"] = str(e)
            return None, metadata
            
    async def _validate_domain(self, company_name: str, url: str, title: str, content: str) -> Tuple[float, str]:
        """Validate if a domain matches the company using LLM."""
        prompt_path = PROJECT_ROOT / "config/prompts/enricher_domain_validation.txt"
        if not prompt_path.exists():
            return 0.0, "Prompt missing"
            
        with open(prompt_path, 'r') as f:
            system_prompt = f.read()
            
        validation_prompt = f"""{system_prompt}

Company Name: {company_name}
URL: {url}
Page Title: {title}
Content Excerpt: {content}

Validate this match.
JSON Response:"""

        try:
            result = await self.llama_wrapper.structured_extract(
                prompt=validation_prompt,
                schema=DomainValidationModel,
                model=self.model_name,
                temperature=0.1
            )
            return result.confidence_score, result.reasoning
        except Exception as e:
            logger.error("Validation failed", error=str(e))
            return 0.0, str(e)
