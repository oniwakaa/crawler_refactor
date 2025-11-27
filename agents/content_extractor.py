import asyncio
import time
from typing import List, Dict, Any, Optional, Type
import structlog
from pathlib import Path
import yaml
import json

from tools.llama_wrapper import LlamaWrapper
from models.lead import LeadProfile

logger = structlog.get_logger()

class ContentExtractorAgent:
    """
    Content Extractor agent responsible for extracting structured lead data from web content.
    Uses LlamaWrapper for LLM-based extraction with confidence scoring.
    """
    
    def __init__(self, settings_path: str = "config/settings.yaml"):
        """
        Initialize ContentExtractorAgent.
        
        Args:
            settings_path: Path to settings YAML file
        """
        self.settings = self._load_settings(settings_path)
        self.llama_wrapper: Optional[LlamaWrapper] = None
        
        # Load configuration
        extraction_config = self.settings.get("extraction", {})
        self.confidence_threshold = extraction_config.get("confidence_threshold", 0.7)
        self.target_fields = extraction_config.get("fields", [])
        
        # Model configuration
        models_config = self.settings.get("models", {})
        self.model_name = models_config.get("extractor", "gpt-oss:20b-cloud")
        
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
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Wrapper will be closed by its own context manager
        pass
        
    async def extract_entities(self, markdown: str, schema: Type[LeadProfile]) -> LeadProfile:
        """
        Extract structured lead data from markdown content.
        
        Args:
            markdown: Markdown content to extract from
            schema: LeadProfile schema class
            
        Returns:
            LeadProfile instance with extracted data
        """
        log = logger.bind(markdown_length=len(markdown))
        log.info("Extracting entities from content")
        
        # Load extraction prompt
        prompt_path = Path("config/prompts/extractor_lead_profile.txt")
        if not prompt_path.exists():
            raise FileNotFoundError(f"Extractor prompt not found: {prompt_path}")
            
        with open(prompt_path, 'r') as f:
            system_prompt = f.read()
            
        # Create extraction prompt with content
        extraction_prompt = f"""{system_prompt}

Content to extract from:
{markdown[:4000]}  # Limit content length to avoid token limits

Extract lead information and return JSON matching the LeadProfile schema."""
        
        try:
            async with self.llama_wrapper as wrapper:
                # Use structured extraction
                lead = await wrapper.structured_extract(
                    prompt=extraction_prompt,
                    schema=schema,
                    model=self.model_name,
                    temperature=0.1,
                    max_tokens=1000
                )
                
                # Calculate confidence score
                confidence = self._calculate_confidence(lead, markdown)
                lead.confidence_score = confidence
                
                log.info(
                    "Entity extraction completed",
                    confidence=confidence,
                    fields_populated=self._count_populated_fields(lead)
                )
                
                return lead
                
        except Exception as e:
            log.error("Entity extraction failed", error=str(e))
            # Return empty lead with zero confidence
            return LeadProfile(
                name="",
                role="",
                company="",
                confidence_score=0.0
            )
            
    async def batch_extract(self, pages: List[Dict[str, Any]]) -> List[LeadProfile]:
        """
        Extract leads from multiple pages concurrently.
        
        Args:
            pages: List of page dictionaries with markdown content
            
        Returns:
            List of LeadProfile instances (filtered by confidence threshold)
        """
        if not pages:
            logger.warning("No pages provided for batch extraction")
            return []
            
        log = logger.bind(page_count=len(pages))
        log.info("Starting batch extraction")
        
        start_time = time.time()
        
        # Process pages concurrently with semaphore for rate limiting
        semaphore = asyncio.Semaphore(5)  # Limit concurrent extractions
        
        async def extract_with_semaphore(page: Dict[str, Any]) -> Optional[LeadProfile]:
            async with semaphore:
                try:
                    markdown = page.get("markdown", "")
                    if not markdown:
                        return None
                        
                    lead = await self.extract_entities(markdown, LeadProfile)
                    
                    # Add source URL if available
                    if "url" in page:
                        lead.source_url = page["url"]
                        
                    return lead
                    
                except Exception as e:
                    log.warning("Extraction failed for page", url=page.get("url"), error=str(e))
                    return None
                    
        # Run concurrent extractions
        tasks = [extract_with_semaphore(page) for page in pages]
        results = await asyncio.gather(*tasks)
        
        # Filter results
        valid_leads = [lead for lead in results if lead is not None]
        
        # Filter by confidence threshold
        filtered_leads = [
            lead for lead in valid_leads 
            if lead.confidence_score >= self.confidence_threshold
        ]
        
        # Calculate statistics
        total_duration = time.time() - start_time
        avg_confidence = sum(lead.confidence_score for lead in filtered_leads) / len(filtered_leads) if filtered_leads else 0.0
        
        # Field coverage statistics
        field_coverage = self._calculate_field_coverage(filtered_leads)
        
        log.info(
            "Batch extraction completed",
            total_pages=len(pages),
            successful_extractions=len(valid_leads),
            high_confidence_leads=len(filtered_leads),
            avg_confidence=avg_confidence,
            duration=total_duration,
            field_coverage=field_coverage
        )
        
        return filtered_leads
        
    def _calculate_confidence(self, lead: LeadProfile, markdown: str) -> float:
        """
        Calculate confidence score for extracted lead.
        
        Args:
            lead: Extracted LeadProfile
            markdown: Original markdown content
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Base confidence starts at 0.5
        confidence = 0.5
        
        # Check for required fields
        required_fields = ["name", "role", "company"]
        populated_required = sum(1 for field in required_fields if getattr(lead, field, None))
        confidence += (populated_required / len(required_fields)) * 0.3
        
        # Check for optional fields
        optional_fields = ["email", "linkedin", "company_domain", "phone_number"]
        populated_optional = sum(1 for field in optional_fields if getattr(lead, field, None))
        confidence += (populated_optional / len(optional_fields)) * 0.15
        
        # Content quality bonus
        if len(markdown) > 500:
            confidence += 0.05
            
        # Validate specific fields
        if lead.email and "@" in lead.email:
            confidence += 0.05
            
        if lead.linkedin and "linkedin.com/in/" in lead.linkedin:
            confidence += 0.05
            
        # Cap at 1.0
        return min(confidence, 1.0)
        
    def _count_populated_fields(self, lead: LeadProfile) -> int:
        """Count number of populated fields in lead profile"""
        fields = ["name", "role", "linkedin", "company", "company_domain", "email", "phone_number"]
        return sum(1 for field in fields if getattr(lead, field, None))
        
    def _calculate_field_coverage(self, leads: List[LeadProfile]) -> Dict[str, float]:
        """
        Calculate field coverage statistics.
        
        Args:
            leads: List of LeadProfile instances
            
        Returns:
            Dictionary with field coverage percentages
        """
        if not leads:
            return {}
            
        field_coverage = {}
        fields = ["name", "role", "linkedin", "company", "company_domain", "email", "phone_number"]
        
        for field in fields:
            populated_count = sum(1 for lead in leads if getattr(lead, field, None))
            field_coverage[field] = populated_count / len(leads)
            
        return field_coverage
        
    def _handle_extraction_failure(self, page: Dict[str, Any], error: Exception) -> None:
        """
        Handle extraction failure gracefully.
        
        Args:
            page: Page dictionary that failed extraction
            error: Exception that occurred
        """
        logger.warning(
            "Extraction failed for page",
            url=page.get("url"),
            error=str(error),
            markdown_length=len(page.get("markdown", ""))
        )