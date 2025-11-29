import asyncio
import structlog
import re
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from pydantic import BaseModel, Field

from tools.crawl4ai_client import Crawl4AIClient
from tools.llama_wrapper import LlamaWrapper
from models.lead import LeadProfile

logger = structlog.get_logger()

class EmailMatchModel(BaseModel):
    email: Optional[str] = Field(None, description="The best matching email address")
    confidence_score: float = Field(..., description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(..., description="Reasoning for the selection")

class EmailDiscoveryAgent:
    """
    Agent responsible for discovering contact emails.
    Scrapes company website contact pages and extracts emails.
    """
    
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.crawl4ai_client: Optional[Crawl4AIClient] = None
        self.llama_wrapper: Optional[LlamaWrapper] = None
        
        models_config = self.settings.get("models", {})
        self.model_name = models_config.get("enricher", "hf.co/unsloth/SmolLM3-3B-GGUF:Q4_K_M")
        self.ollama_host = models_config.get("ollama_host", "http://localhost:11434")
        
    async def __aenter__(self):
        self.crawl4ai_client = Crawl4AIClient()
        self.llama_wrapper = LlamaWrapper(ollama_host=self.ollama_host)
        await self.crawl4ai_client.__aenter__()
        await self.llama_wrapper.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.crawl4ai_client:
            await self.crawl4ai_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.llama_wrapper:
            await self.llama_wrapper.__aexit__(exc_type, exc_val, exc_tb)
            
    async def discover_email(self, lead: LeadProfile) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Discover email for a lead.
        
        Args:
            lead: LeadProfile with company_domain
            
        Returns:
            Tuple of (email, metadata)
        """
        if not lead.company_domain:
            return None, {"status": "skipped", "reason": "no_domain"}
            
        log = logger.bind(lead_name=lead.name, domain=lead.company_domain)
        log.info("Starting email discovery")
        
        metadata = {
            "status": "failed",
            "stages": [],
            "found_emails": []
        }
        
        try:
            # 1. Scrape contact pages
            pages_to_scrape = self._get_contact_urls(lead.company_domain)
            results = await self.crawl4ai_client.batch_fetch(pages_to_scrape)
            metadata["stages"].append("scrape")
            
            # 2. Extract emails from content
            all_emails = set()
            for result in results:
                if result.get("fetch_status") == "success":
                    content = result.get("markdown", "")
                    emails = self._extract_emails_from_text(content)
                    all_emails.update(emails)
                    
            if not all_emails:
                log.info("No emails found on website")
                metadata["reason"] = "no_emails_found"
                return None, metadata
                
            metadata["found_emails"] = list(all_emails)
            
            # 3. Match email to lead
            best_email, score, reasoning = await self._match_email(lead, list(all_emails))
            metadata["stages"].append("match")
            
            if best_email and score > 0.7:
                log.info("Email discovered", email=best_email, score=score)
                metadata["status"] = "success"
                metadata["confidence"] = score
                metadata["reasoning"] = reasoning
                return best_email, metadata
            else:
                log.info("No matching email found with high confidence")
                metadata["reason"] = "low_confidence_match"
                return None, metadata
                
        except Exception as e:
            log.error("Email discovery failed", error=str(e))
            metadata["error"] = str(e)
            return None, metadata
            
    def _get_contact_urls(self, domain: str) -> List[str]:
        """Generate list of potential contact URLs."""
        # Ensure domain has protocol
        base_url = domain
        if not base_url.startswith("http"):
            base_url = f"https://{base_url}"
            
        # Remove trailing slash
        base_url = base_url.rstrip("/")
        
        paths = [
            "", # Homepage
            "/contact",
            "/contact-us",
            "/about",
            "/about-us",
            "/team",
            "/imprint",
            "/impressum" # Common in DACH region
        ]
        
        return [f"{base_url}{path}" for path in paths]
        
    def _extract_emails_from_text(self, text: str) -> List[str]:
        """Extract emails using regex."""
        # Simple email regex
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        matches = re.findall(pattern, text)
        
        # Filter out common junk
        junk = ["example.com", "domain.com", "email.com", ".png", ".jpg", ".jpeg", ".gif", "wixpress.com", "sentry.io"]
        valid_emails = []
        
        for email in matches:
            email = email.lower()
            if any(j in email for j in junk):
                continue
            valid_emails.append(email)
            
        return valid_emails
        
    async def _match_email(self, lead: LeadProfile, emails: List[str]) -> Tuple[Optional[str], float, str]:
        """Match discovered emails to the lead using LLM."""
        prompt_path = Path("config/prompts/enricher_email_discovery.txt")
        if not prompt_path.exists():
            return None, 0.0, "Prompt missing"
            
        with open(prompt_path, 'r') as f:
            system_prompt = f.read()
            
        match_prompt = f"""{system_prompt}

Lead Name: {lead.name}
Lead Role: {lead.role}
Lead Company: {lead.company}

Discovered Emails:
{", ".join(emails)}

Find the best match.
JSON Response:"""

        try:
            result = await self.llama_wrapper.structured_extract(
                prompt=match_prompt,
                schema=EmailMatchModel,
                model=self.model_name,
                temperature=0.1
            )
            return result.email, result.confidence_score, result.reasoning
        except Exception as e:
            logger.error("Email matching failed", error=str(e))
            return None, 0.0, str(e)
