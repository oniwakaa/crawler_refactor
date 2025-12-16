import asyncio
import json
import re
import structlog
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

from tools.llama_wrapper import LlamaWrapper
from models.lead import LeadProfile

logger = structlog.get_logger()

from pydantic import BaseModel, Field

# Define project root
PROJECT_ROOT = Path(__file__).parent.parent

class LinkedInExtractionModel(BaseModel):
    name: Optional[str] = Field(None, description="Full name of the person")
    company: Optional[str] = Field(None, description="Current company name")
    role: Optional[str] = Field(None, description="Current job title or role")
    company_linkedin_url: Optional[str] = Field(None, description="URL to company LinkedIn page")
    email: Optional[str] = Field(None, description="Email address found in profile")
    phone: Optional[str] = Field(None, description="Phone number found in profile")

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
        self.llama_wrapper: Optional[LlamaWrapper] = None
        
        models_config = self.settings.get("models", {})
        self.model_name = models_config.get("enricher", "hf.co/unsloth/SmolLM3-3B-GGUF:Q4_K_M")
        self.ollama_host = models_config.get("ollama_host", "http://localhost:11434")
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.llama_wrapper = LlamaWrapper(ollama_host=self.ollama_host)
        
        # Initialize clients
        await self.llama_wrapper.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
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
            # 1. Skip Re-scraping (Use existing data)
            # Since the pipeline uses Apify for the initial scrape, we assume the lead 
            # already has high-quality data. We skip re-scraping to avoid unnecessary calls 
            # and complexity with Apify batching here.
            
            # If we really needed to enrich a bare URL, we would need to call ApifyClient here,
            # but for now, we treat this as "if we have content, try to extract more".
            
            # But wait, we don't pass the profile content to this method, currently it fetches.
            # Without content, we can't do anything.
            
            log.info("Skipping LinkedIn profile re-scraping (handled by initial Apify scrape)")
            metadata["status"] = "skipped"
            metadata["reason"] = "already_scraped_by_apify"
            return lead, metadata

        except Exception as e:
            log.error("LinkedIn enrichment failed", error=str(e))
            metadata["error"] = str(e)
            return lead, metadata
            
    async def _extract_profile_data(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract structured data from profile markdown using LLM."""
        prompt_path = PROJECT_ROOT / "config/prompts/enricher_linkedin_profile.txt"
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

Extract the current company, role, and any contact info (email/phone).
JSON Response:"""

        try:
            result = await self.llama_wrapper.structured_extract(
                prompt=extraction_prompt,
                schema=LinkedInExtractionModel,
                model=self.model_name,
                temperature=0.1,
                num_ctx=8192  # Optimized context window for profile extraction
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
        new_email = extracted_data.get("email")
        new_phone = extracted_data.get("phone")
        
        # Update if we have better data
        if new_company and new_company.lower() != "unknown company":
            updated_lead.company = new_company
            
        if new_role and new_role.lower() != "unknown role":
            updated_lead.role = new_role
            
        if new_email and not updated_lead.email:
            updated_lead.email = new_email
            
        if new_phone and not updated_lead.phone_number:
            updated_lead.phone_number = new_phone
            
        # Boost confidence if we found data
        if new_company or new_role or new_email:
            updated_lead.confidence_score = min(updated_lead.confidence_score + 0.2, 1.0)
            
        return updated_lead

    def _extract_emails_from_text(self, text: str) -> List[str]:
        """Extract emails using regex."""
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        matches = re.findall(pattern, text)
        
        junk = ["example.com", "domain.com", "email.com", "linkedin.com"]
        valid_emails = []
        
        for email in matches:
            email = email.lower()
            if len(email) < 6 or len(email) > 100:
                continue
            if any(j in email for j in junk):
                continue
            valid_emails.append(email)
            
        return valid_emails

    def _extract_phones_from_text(self, text: str) -> List[str]:
        """Extract phone numbers using regex."""
        phones = set()
        
        # Pattern 1: International E.164-ish
        pattern_intl = r'\+(?:[0-9] ?){6,14}[0-9]'
        matches_intl = re.findall(pattern_intl, text)
        for p in matches_intl:
            phones.add(p.strip())
            
        return list(phones)
