import asyncio
import json
import structlog
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

from tools.crawl4ai_client import Crawl4AIClient
from tools.llama_wrapper import LlamaWrapper
from models.lead import LeadProfile

logger = structlog.get_logger()

from pydantic import BaseModel, Field

class LinkedInExtractionModel(BaseModel):
    name: Optional[str] = Field(None, description="Full name of the person")
    company: Optional[str] = Field(None, description="Current company name")
    role: Optional[str] = Field(None, description="Current job title or role")
    company_linkedin_url: Optional[str] = Field(None, description="URL to company LinkedIn page")

class LinkedInProfileEnricherAgent:
    """
    Agent responsible for enriching leads using LinkedIn profile data.
    Fetches profile content and extracts current company and role.
    """
    
    def __init__(self, settings: Dict[str, Any]):
        """
        Initialize LinkedInProfileEnricherAgent.
        
        Args:
            settings: Configuration dictionary
        """
        self.settings = settings
        self.crawl4ai_client: Optional[Crawl4AIClient] = None
        self.llama_wrapper: Optional[LlamaWrapper] = None
        
        models_config = self.settings.get("models", {})
        self.model_name = models_config.get("enricher", "hf.co/unsloth/SmolLM3-3B-GGUF:Q4_K_M")
        self.ollama_host = models_config.get("ollama_host", "http://localhost:11434")
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.crawl4ai_client = Crawl4AIClient()
        self.llama_wrapper = LlamaWrapper(ollama_host=self.ollama_host)
        
        # Initialize clients
        await self.crawl4ai_client.__aenter__()
        await self.llama_wrapper.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.crawl4ai_client:
            await self.crawl4ai_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.llama_wrapper:
            await self.llama_wrapper.__aexit__(exc_type, exc_val, exc_tb)
            
    async def enrich_from_linkedin_profile(self, lead: LeadProfile) -> Tuple[LeadProfile, Dict[str, Any]]:
        """
        Enrich lead with data extracted from their LinkedIn profile.
        
        Args:
            lead: LeadProfile to enrich
            
        Returns:
            Tuple of (enriched_lead, metadata)
        """
        if not lead.linkedin:
            return lead, {"status": "skipped", "reason": "no_linkedin_url"}
            
        log = logger.bind(lead_name=lead.name, linkedin=lead.linkedin)
        log.info("Starting LinkedIn profile enrichment")
        
        metadata = {
            "status": "failed",
            "stages": [],
            "extracted_data": None
        }
        
        try:
            # 1. Fetch Profile
            fetch_result = await self.crawl4ai_client.fetch_linkedin_profile(lead.linkedin)
            metadata["stages"].append("fetch")
            
            if fetch_result.get("fetch_status") != "success":
                log.warning("Failed to fetch LinkedIn profile", error=fetch_result.get("error"))
                metadata["error"] = fetch_result.get("error")
                return lead, metadata
                
            markdown_content = fetch_result.get("markdown", "")
            if not markdown_content:
                log.warning("Empty LinkedIn content")
                metadata["reason"] = "empty_content"
                return lead, metadata
                
            # 2. Extract Data
            extracted_data = await self._extract_profile_data(markdown_content)
            metadata["stages"].append("extraction")
            metadata["extracted_data"] = extracted_data
            
            if not extracted_data:
                log.warning("Failed to extract data from profile")
                return lead, metadata
                
            # 3. Update Lead
            enriched_lead = self._update_lead(lead, extracted_data)
            metadata["status"] = "success"
            
            log.info("LinkedIn enrichment successful", 
                     company=enriched_lead.company, 
                     role=enriched_lead.role)
            
            return enriched_lead, metadata
            
        except Exception as e:
            log.error("LinkedIn enrichment failed", error=str(e))
            metadata["error"] = str(e)
            return lead, metadata
            
    async def _extract_profile_data(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract structured data from profile markdown using LLM."""
        prompt_path = Path("config/prompts/enricher_linkedin_profile.txt")
        if not prompt_path.exists():
            logger.error(f"Prompt file not found: {prompt_path}")
            return None
            
        with open(prompt_path, 'r') as f:
            system_prompt = f.read()
            
        # Truncate content if too long (approx 15k chars)
        if len(content) > 15000:
            content = content[:15000] + "...(truncated)"
            
        extraction_prompt = f"""{system_prompt}

Profile Content:
{content}

Extract the current company and role.
JSON Response:"""

        try:
            result = await self.llama_wrapper.structured_extract(
                prompt=extraction_prompt,
                schema=LinkedInExtractionModel,
                model=self.model_name,
                temperature=0.1
            )
            return result.model_dump() if result else None
        except Exception as e:
            logger.error("LLM extraction failed", error=str(e))
            return None
            
    def _update_lead(self, lead: LeadProfile, extracted_data: Dict[str, Any]) -> LeadProfile:
        """Update lead with extracted data if confidence is sufficient."""
        # Create a copy of the lead
        updated_lead = lead.model_copy()
        
        new_company = extracted_data.get("company")
        new_role = extracted_data.get("role")
        
        # Update if we have better data
        # Logic: If current is "Unknown" or empty, and new is valid, update.
        # If both exist, we might trust the LinkedIn one more, or keep existing.
        # For now, let's prioritize LinkedIn data if it looks valid.
        
        if new_company and new_company.lower() != "unknown company":
            updated_lead.company = new_company
            
        if new_role and new_role.lower() != "unknown role":
            updated_lead.role = new_role
            
        # Boost confidence if we found data
        if new_company or new_role:
            updated_lead.confidence_score = min(updated_lead.confidence_score + 0.2, 1.0)
            
        return updated_lead
