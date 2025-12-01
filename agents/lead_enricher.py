import asyncio
import os
import time
import json
from typing import List, Dict, Any, Optional
import structlog
from pathlib import Path
import yaml
import re

from tools.llama_wrapper import LlamaWrapper
from tools.crawl4ai_client import Crawl4AIClient
from models.lead import LeadProfile
from agents.linkedin_profile_enricher import LinkedInProfileEnricherAgent
from agents.company_domain_agent import CompanyDomainAgent
from agents.email_discovery_agent import EmailDiscoveryAgent

logger = structlog.get_logger()

class LeadEnricherAgent:
    """
    Lead Enricher agent responsible for inferring missing fields and deduplicating leads.
    Uses LlamaWrapper for inference and maintains lead quality.
    """
    
    def __init__(self, settings_path: str = "config/settings.yaml"):
        """
        Initialize LeadEnricherAgent.
        
        Args:
            settings_path: Path to settings YAML file
        """
        self.settings = self._load_settings(settings_path)
        self.llama_wrapper: Optional[LlamaWrapper] = None
        self.crawl4ai_client: Optional[Crawl4AIClient] = None
        self.linkedin_agent: Optional[LinkedInProfileEnricherAgent] = None
        self.domain_agent: Optional[CompanyDomainAgent] = None
        self.email_agent: Optional[EmailDiscoveryAgent] = None
        
        # Load configuration
        models_config = self.settings.get("models", {})
        self.model_name = os.getenv("ENRICHER_MODEL") or models_config.get("enricher", "nvidia_NVIDIA-Nemotron-Nano-9B-v2")
        
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
        self.llama_wrapper = LlamaWrapper(
            ollama_host=self.settings.get("models", {}).get("ollama_host", "http://localhost:11434")
        )
        self.crawl4ai_client = Crawl4AIClient()
        self.linkedin_agent = LinkedInProfileEnricherAgent(self.settings)
        self.domain_agent = CompanyDomainAgent(self.settings)
        self.email_agent = EmailDiscoveryAgent(self.settings)
        await self.linkedin_agent.__aenter__()
        await self.domain_agent.__aenter__()
        await self.email_agent.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.linkedin_agent:
            await self.linkedin_agent.__aexit__(exc_type, exc_val, exc_tb)
        if self.domain_agent:
            await self.domain_agent.__aexit__(exc_type, exc_val, exc_tb)
        if self.email_agent:
            await self.email_agent.__aexit__(exc_type, exc_val, exc_tb)
        # Clients will be closed by their own context managers
        pass
        
    async def infer_missing_fields(self, lead: LeadProfile) -> LeadProfile:
        """
        Infer missing fields for a lead using LLM inference.
        
        Args:
            lead: LeadProfile with potentially missing fields
            
        Returns:
            LeadProfile with inferred fields
        """
        log = logger.bind(lead_name=lead.name, lead_company=lead.company)
        log.info("Inferring missing fields")
        
        # Check if inference is needed
        missing_fields = self._get_missing_fields(lead)
        if not missing_fields:
            log.info("No missing fields to infer")
            return lead
            
        # Load enrichment prompt
        prompt_path = Path("config/prompts/enricher_inference.txt")
        if not prompt_path.exists():
            raise FileNotFoundError(f"Enricher prompt not found: {prompt_path}")
            
        with open(prompt_path, 'r') as f:
            system_prompt = f.read()
            
        # Create inference prompt (exclude datetime fields for JSON serialization)
        lead_dict = lead.model_dump(exclude={'extraction_timestamp'})
        inference_prompt = f"""{system_prompt}

Current lead data:
{json.dumps(lead_dict, indent=2, default=str)}

Missing fields to infer: {', '.join(missing_fields)}

Infer the missing fields and return updated JSON. Only infer fields with high confidence (>0.7).
Return ONLY valid JSON, no additional text.

JSON Response:"""
        
        try:
            async with self.llama_wrapper as wrapper:
                # Use structured extraction to get updated lead
                enriched_lead = await wrapper.structured_extract(
                    prompt=inference_prompt,
                    schema=LeadProfile,
                    model=self.model_name,
                    temperature=0.2,
                    max_tokens=4096
                )
                
                # Preserve original source URL and timestamp
                enriched_lead.source_url = lead.source_url
                enriched_lead.extraction_timestamp = lead.extraction_timestamp
                
                # Update confidence score based on inference quality
                enriched_lead.confidence_score = self._update_confidence(
                    lead, enriched_lead, missing_fields
                )
                
                # Mark inferred fields in metadata
                inferred_fields = self._get_inferred_fields(lead, enriched_lead)
                if inferred_fields:
                    log.info("Fields inferred", fields=inferred_fields)
                    
                log.info(
                    "Field inference completed",
                    missing_fields_before=len(missing_fields),
                    confidence=enriched_lead.confidence_score
                )
                
                return enriched_lead
                
        except Exception as e:
            log.error("Field inference failed", error=str(e))
            # Return original lead unchanged
            return lead
            
        # Try to discover domain if missing
        if not lead.company_domain and lead.company:
            lead = await self.discover_company_domain(lead)
            
        # Try to discover email if missing
        if not lead.email and lead.company_domain:
            lead = await self.discover_email(lead)
            
        return lead
            
    async def discover_company_domain(self, lead: LeadProfile) -> LeadProfile:
        """
        Discover company domain if missing.
        """
        if lead.company_domain:
            return lead
            
        if not lead.company or lead.company.lower() in ["unknown", "unknown company"]:
            return lead
            
        log = logger.bind(lead_name=lead.name, company=lead.company)
        log.info("Discovering company domain")
        
        try:
            if not self.domain_agent:
                log.warning("Domain agent not initialized")
                return lead
                
            domain = None
            metadata = {}
            
            # Try search with timeout
            try:
                async with asyncio.timeout(20):
                    domain, metadata = await self.domain_agent.find_company_domain(lead.company)
            except TimeoutError:
                log.warning("Domain search timed out, attempting fallback")
                metadata = {"reason": "timeout"}
            except Exception as e:
                log.warning("Domain search failed", error=str(e))
                metadata = {"reason": "error", "error": str(e)}
            
            if domain:
                updated_lead = lead.model_copy()
                updated_lead.company_domain = domain
                updated_lead.confidence_score = min(updated_lead.confidence_score + 0.1, 1.0)
                log.info("Domain discovered via search", domain=domain)
                return updated_lead
            else:
                log.info("Domain search failed", reason=metadata.get("reason"))
                return lead
                
        except Exception as e:
            log.error("Domain discovery failed", error=str(e))
            return lead
            
    async def discover_email(self, lead: LeadProfile) -> LeadProfile:
        """
        Discover email if missing.
        """
        if lead.email:
            return lead
            
        if not lead.company_domain:
            return lead
            
        log = logger.bind(lead_name=lead.name, domain=lead.company_domain)
        log.info("Discovering email")
        
        try:
            if not self.email_agent:
                log.warning("Email agent not initialized")
                return lead
                
            email, metadata = await self.email_agent.discover_email(lead)
            
            if email:
                updated_lead = lead.model_copy()
                updated_lead.email = email
                updated_lead.confidence_score = min(updated_lead.confidence_score + 0.1, 1.0)
                log.info("Email discovered", email=email)
                return updated_lead
            else:
                log.info("Email discovery failed", reason=metadata.get("reason"))
                return lead
                
        except Exception as e:
            log.error("Email discovery failed", error=str(e))
            return lead
            
    async def deduplicate_leads(self, leads: List[LeadProfile]) -> List[LeadProfile]:
        """
        Deduplicate leads based on multiple keys.
        
        Args:
            leads: List of LeadProfile instances
            
        Returns:
            Deduplicated list of leads
        """
        if not leads:
            logger.warning("No leads provided for deduplication")
            return []
            
        log = logger.bind(total_leads=len(leads))
        log.info("Starting deduplication")
        
        start_time = time.time()
        
        # Group leads by deduplication keys
        lead_groups: Dict[str, List[LeadProfile]] = {}
        
        for lead in leads:
            # Primary key: email
            if lead.email:
                key = f"email:{lead.email.lower()}"
                lead_groups.setdefault(key, []).append(lead)
                continue
                
            # Secondary key: linkedin URL
            if lead.linkedin:
                key = f"linkedin:{lead.linkedin.lower()}"
                lead_groups.setdefault(key, []).append(lead)
                continue
                
            # Tertiary key: name + company combination
            if lead.name and lead.company:
                # Normalize name and company
                normalized_name = self._normalize_name(lead.name)
                normalized_company = self._normalize_company(lead.company)
                key = f"name_company:{normalized_name}:{normalized_company}"
                lead_groups.setdefault(key, []).append(lead)
                continue
                
            # No deduplication key, add as unique
            key = f"unique:{id(lead)}"
            lead_groups[key] = [lead]
            
        # Select best lead from each group
        deduplicated_leads = []
        duplicates_removed = 0
        
        for key, group_leads in lead_groups.items():
            if len(group_leads) == 1:
                deduplicated_leads.append(group_leads[0])
            else:
                # Keep lead with highest confidence score
                best_lead = max(group_leads, key=lambda l: l.confidence_score)
                deduplicated_leads.append(best_lead)
                duplicates_removed += len(group_leads) - 1
                
        total_duration = time.time() - start_time
        
        log.info(
            "Deduplication completed",
            original_count=len(leads),
            deduplicated_count=len(deduplicated_leads),
            duplicates_removed=duplicates_removed,
            duration=total_duration
        )
        
        return deduplicated_leads
        
    async def enrich_from_linkedin(self, lead: LeadProfile) -> LeadProfile:
        """
        Enrich lead from LinkedIn profile if available.
        
        Args:
            lead: LeadProfile with LinkedIn URL
            
        Returns:
            Enriched LeadProfile
        """
        if not lead.linkedin:
            logger.debug("No LinkedIn URL for enrichment", lead_name=lead.name)
            return lead
            
        log = logger.bind(lead_name=lead.name, linkedin=lead.linkedin)
        log.info("Enriching from LinkedIn")
        
        try:
            if not self.linkedin_agent:
                log.warning("LinkedIn agent not initialized")
                return lead
                
            enriched_lead, metadata = await self.linkedin_agent.enrich_from_linkedin_profile(lead)
            
            if metadata.get("status") == "success":
                log.info("LinkedIn enrichment successful", 
                         company=enriched_lead.company, 
                         role=enriched_lead.role)
                return enriched_lead
            else:
                log.warning("LinkedIn enrichment failed or skipped", 
                           reason=metadata.get("reason"), 
                           error=metadata.get("error"))
                return lead
                
        except Exception as e:
            log.error("LinkedIn enrichment failed", error=str(e))
            return lead
            
    def _get_missing_fields(self, lead: LeadProfile) -> List[str]:
        """Get list of missing fields that could be inferred"""
        missing = []
        fields = ["company_domain", "email", "phone_number", "linkedin"]
        
        for field in fields:
            if not getattr(lead, field, None):
                missing.append(field)
                
        return missing
        
    def _get_inferred_fields(self, original: LeadProfile, enriched: LeadProfile) -> List[str]:
        """Get list of fields that were inferred"""
        inferred = []
        fields = ["company_domain", "email", "phone_number", "linkedin"]
        
        for field in fields:
            original_value = getattr(original, field, None)
            enriched_value = getattr(enriched, field, None)
            
            if not original_value and enriched_value:
                inferred.append(field)
                
        return inferred
        
    def _update_confidence(self, original: LeadProfile, enriched: LeadProfile, missing_fields: List[str]) -> float:
        """
        Update confidence score based on inference quality.
        
        Args:
            original: Original lead
            enriched: Enriched lead
            missing_fields: Fields that were missing
            
        Returns:
            Updated confidence score
        """
        base_confidence = original.confidence_score
        
        # Check which missing fields were successfully inferred
        inferred_count = 0
        for field in missing_fields:
            original_value = getattr(original, field, None)
            enriched_value = getattr(enriched, field, None)
            
            if not original_value and enriched_value:
                inferred_count += 1
                
        # Boost confidence based on successful inferences
        if missing_fields:
            inference_rate = inferred_count / len(missing_fields)
            confidence_boost = inference_rate * 0.2  # Max 0.2 boost
            base_confidence += confidence_boost
            
        # Validate inferred fields
        if enriched.company_domain and self._is_valid_domain(enriched.company_domain):
            base_confidence += 0.05
            
        if enriched.email and "@" in enriched.email:
            base_confidence += 0.05
            
        if enriched.linkedin and "linkedin.com/in/" in enriched.linkedin:
            base_confidence += 0.05
            
        # Cap at 1.0
        return min(base_confidence, 1.0)
        
    def _is_valid_domain(self, domain: str) -> bool:
        """Simple domain validation"""
        # Basic domain pattern: letters, numbers, hyphens, dots
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, domain))
        
    def _normalize_name(self, name: str) -> str:
        """Normalize name for deduplication"""
        # Remove titles, convert to lowercase, remove extra spaces
        name = name.lower().strip()
        titles = ["dr.", "mr.", "ms.", "mrs.", "prof."]
        for title in titles:
            name = name.replace(title, "")
        return " ".join(name.split())
        
    def _normalize_company(self, company: str) -> str:
        """Normalize company name for deduplication"""
        # Convert to lowercase, remove legal suffixes, remove extra spaces
        company = company.lower().strip()
        suffixes = ["inc", "ltd", "llc", "gmbh", "corp", "corporation", "limited"]
        for suffix in suffixes:
            company = company.replace(f" {suffix}", "").replace(f" {suffix}.", "")
        return " ".join(company.split())