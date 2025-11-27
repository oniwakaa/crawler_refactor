import asyncio
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
        
        # Load configuration
        models_config = self.settings.get("models", {})
        self.model_name = models_config.get("enricher", "hf.co/unsloth/SmolLM3-3B-GGUF:Q4_K_M")
        
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
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
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
                    max_tokens=800
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
            async with self.crawl4ai_client as crawler:
                # Fetch LinkedIn profile
                results = await crawler.batch_fetch([lead.linkedin])
                
                if not results or results[0].get("fetch_status") != "success":
                    log.warning("Failed to fetch LinkedIn profile")
                    return lead
                    
                result = results[0]
                markdown = result.get("markdown", "")
                
                if not markdown:
                    log.warning("Empty LinkedIn content")
                    return lead
                    
                # Extract additional info using content extractor pattern
                # For now, just log that we have the content
                log.info(
                    "LinkedIn profile fetched",
                    content_length=len(markdown)
                )
                
                # TODO: Implement LinkedIn-specific extraction
                # This would involve parsing the LinkedIn profile structure
                # and extracting additional fields like company, role, etc.
                
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