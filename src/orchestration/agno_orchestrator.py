"""
Agno-based orchestrator for B2B lead generation pipeline.

This module implements the main orchestration logic using Agno's agent framework
to coordinate the BrowserNavigator, LangExtract manager, and validation agents.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

from agno.agent import Agent
from agno.models.llm import LLM
from agno.team import Team, TeamContext

# Import our custom modules
from ..extraction.lang_extract_manager import LangExtractManager
from ..extraction.schemas import CompanyProfile, PersonProfile, ExtractionResult
from ..navigation.browser_navigator import BrowserNavigator, NavigationResult

logger = logging.getLogger(__name__)


class ExtractionStage(str, Enum):
    """Pipeline extraction stages."""
    NAVIGATION = "navigation"
    EXTRACTION = "extraction" 
    ENRICHMENT = "enrichment"
    VALIDATION = "validation"
    OUTPUT = "output"


@dataclass
class PipelineTask:
    """Individual task in the pipeline."""
    id: str
    stage: ExtractionStage
    url: str
    content: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PipelineResult:
    """Result from the complete lead generation pipeline."""
    success: bool
    companies: List[CompanyProfile]
    people: List[PersonProfile]
    errors: List[str]
    total_processing_time: float
    extraction_stats: Dict[str, Any]
    metadata: Dict[str, Any]


class WebNavigatorAgent(Agent):
    """Agno agent for web navigation and content extraction."""
    
    def __init__(self, navigator: BrowserNavigator):
        super().__init__(
            name="WebNavigator",
            description="Specialized in web navigation, content extraction, and page analysis",
            model=LLM(id="gpt-4"),  # Cloud model for complex navigation decisions
            instructions=[
                "Navigate to websites and extract relevant content for B2B lead generation.",
                "Use browser automation to access contact pages, about pages, and company information.",
                "Clean and structure extracted content for further processing.",
                "Handle dynamic content, JavaScript-heavy sites, and various page structures.",
                "Identify and extract URLs for contact, about, and company information pages.",
                "Provide clean text content suitable for LLM-based structured extraction."
            ]
        )
        self.navigator = navigator
    
    async def navigate_and_extract(self, urls: List[str]) -> List[NavigationResult]:
        """
        Navigate to multiple URLs and extract content.
        
        Args:
            urls: List of URLs to process
            
        Returns:
            List of NavigationResult objects
        """
        logger.info(f"Navigator agent processing {len(urls)} URLs")
        
        results = []
        for url in urls:
            try:
                result = await self.navigator.navigate_to_page(url)
                if result.success:
                    results.append(result)
                    logger.info(f"Successfully extracted content from: {url}")
                else:
                    logger.warning(f"Failed to extract from {url}: {result.error_message}")
            except Exception as e:
                logger.error(f"Error navigating to {url}: {e}")
        
        return results
    
    async def search_and_discover(self, query: str, max_results: int = 10) -> List[NavigationResult]:
        """
        Search for relevant content and discover URLs.
        
        Args:
            query: Search query
            max_results: Maximum number of results to process
            
        Returns:
            List of NavigationResult objects
        """
        logger.info(f"Navigator agent searching for: {query}")
        
        try:
            results = await self.navigator.search_and_extract(query)
            return results[:max_results]
        except Exception as e:
            logger.error(f"Search and extract failed: {e}")
            return []


class ContentExtractorAgent(Agent):
    """Agno agent for structured content extraction using LangExtract."""
    
    def __init__(self, extract_manager: LangExtractManager):
        super().__init__(
            name="ContentExtractor", 
            description="Specialized in structured data extraction from web content",
            model=LLM(id="gpt-4"),  # Cloud model for complex extraction decisions
            instructions=[
                "Use LangExtract to extract structured company and person information from web content.",
                "Apply appropriate schemas (CompanyProfile, PersonProfile) based on content type.",
                "Implement fallback strategies: local models -> cloud models -> other extraction methods.",
                "Ensure high-quality extraction with confidence scoring.",
                "Handle various content types: contact pages, about pages, team pages, LinkedIn profiles.",
                "Clean and preprocess content for optimal LangExtract performance."
            ]
        )
        self.extract_manager = extract_manager
    
    async def extract_company_data(self, content: str, url: str) -> ExtractionResult:
        """
        Extract company information from content.
        
        Args:
            content: Text content to extract from
            url: Source URL
            
        Returns:
            ExtractionResult with company data
        """
        logger.info(f"Extractor agent processing company data from: {url}")
        
        try:
            result = await self.extract_manager.extract_company_data(
                text_content=content,
                source_url=url,
                context_hints=["extracted from web navigation"]
            )
            
            return result
        except Exception as e:
            logger.error(f"Company extraction failed for {url}: {e}")
            return ExtractionResult(
                success=False,
                error_message=str(e),
                extraction_method="error",
                confidence_score=0.0
            )
    
    async def extract_person_data(self, content: str, url: str) -> ExtractionResult:
        """
        Extract person information from content.
        
        Args:
            content: Text content to extract from  
            url: Source URL
            
        Returns:
            ExtractionResult with person data
        """
        logger.info(f"Extractor agent processing person data from: {url}")
        
        try:
            result = await self.extract_manager.extract_person_data(
                text_content=content,
                source_url=url,
                context_hints=["extracted from web navigation"]
            )
            
            return result
        except Exception as e:
            logger.error(f"Person extraction failed for {url}: {e}")
            return ExtractionResult(
                success=False,
                error_message=str(e),
                extraction_method="error",
                confidence_score=0.0
            )
    
    async def extract_batch(self, content_items: List[Dict[str, str]]) -> List[ExtractionResult]:
        """
        Extract data from multiple content items in batch.
        
        Args:
            content_items: List of dicts with 'content' and 'url' keys
            
        Returns:
            List of ExtractionResult objects
        """
        logger.info(f"Extractor agent processing {len(content_items)} items")
        
        tasks = []
        for item in content_items:
            if item.get('type') == 'company':
                task = self.extract_company_data(item['content'], item['url'])
            elif item.get('type') == 'person':
                task = self.extract_person_data(item['content'], item['url'])
            else:
                # Default to company extraction
                task = self.extract_company_data(item['content'], item['url'])
            
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed results
        extraction_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                extraction_results.append(ExtractionResult(
                    success=False,
                    error_message=str(result),
                    extraction_method="batch_error",
                    confidence_score=0.0
                ))
            else:
                extraction_results.append(result)
        
        return extraction_results


class LeadEnricherAgent(Agent):
    """Agno agent for lead enrichment and data enhancement."""
    
    def __init__(self):
        super().__init__(
            name="LeadEnricher",
            description="Specialized in lead data enrichment and enhancement",
            model=LLM(id="gpt-4"),
            instructions=[
                "Enrich extracted lead data with additional information.",
                "Cross-reference data points for consistency and completeness.",
                "Add missing information where possible through inference.",
                "Format and standardize contact information.",
                "Categorize companies and people appropriately.",
                "Prepare data for validation and final output."
            ]
        )
    
    async def enrich_company_leads(self, companies: List[CompanyProfile]) -> List[CompanyProfile]:
        """
        Enrich company lead data.
        
        Args:
            companies: List of CompanyProfile objects
            
        Returns:
            List of enriched CompanyProfile objects
        """
        logger.info(f"Enricher agent processing {len(companies)} company leads")
        
        enriched_companies = []
        for company in companies:
            try:
                # Add enrichment logic here
                enriched_company = await self._enrich_single_company(company)
                enriched_companies.append(enriched_company)
            except Exception as e:
                logger.error(f"Failed to enrich company {company.company_name}: {e}")
                enriched_companies.append(company)  # Keep original if enrichment fails
        
        return enriched_companies
    
    async def enrich_person_leads(self, people: List[PersonProfile]) -> List[PersonProfile]:
        """
        Enrich person lead data.
        
        Args:
            people: List of PersonProfile objects
            
        Returns:
            List of enriched PersonProfile objects
        """
        logger.info(f"Enricher agent processing {len(people)} person leads")
        
        enriched_people = []
        for person in people:
            try:
                # Add enrichment logic here
                enriched_person = await self._enrich_single_person(person)
                enriched_people.append(enriched_person)
            except Exception as e:
                logger.error(f"Failed to enrich person {person.full_name}: {e}")
                enriched_people.append(person)  # Keep original if enrichment fails
        
        return enriched_people
    
    async def _enrich_single_company(self, company: CompanyProfile) -> CompanyProfile:
        """Enrich a single company profile."""
        # Placeholder for enrichment logic
        # Could add:
        # - Industry categorization
        # - Company size estimation
        # - Technology stack analysis
        # - Social media link discovery
        return company
    
    async def _enrich_single_person(self, person: PersonProfile) -> PersonProfile:
        """Enrich a single person profile."""
        # Placeholder for enrichment logic
        # Could add:
        # - Professional background analysis
        # - Social media profile discovery
        # - Skill extraction and categorization
        return person


class ValidationAgent(Agent):
    """Agno agent for lead data validation and quality assurance."""
    
    def __init__(self):
        super().__init__(
            name="ValidationAgent",
            description="Specialized in lead data validation and quality assurance",
            model=LLM(id="gpt-4"),
            instructions=[
                "Validate extracted lead data for accuracy and completeness.",
                "Check email addresses and phone numbers for validity.",
                "Verify company information and URLs.",
                "Remove duplicates and consolidate similar entries.",
                "Score lead quality and relevance.",
                "Flag potential data quality issues."
            ]
        )
    
    async def validate_leads(
        self, 
        companies: List[CompanyProfile], 
        people: List[PersonProfile]
    ) -> Dict[str, Any]:
        """
        Validate and quality-check lead data.
        
        Args:
            companies: List of CompanyProfile objects
            people: List of PersonProfile objects
            
        Returns:
            Validation report with results and statistics
        """
        logger.info(f"Validation agent validating {len(companies)} companies and {len(people)} people")
        
        validation_report = {
            'companies': {
                'total': len(companies),
                'valid': 0,
                'invalid': 0,
                'issues': []
            },
            'people': {
                'total': len(people),
                'valid': 0,
                'invalid': 0,
                'issues': []
            },
            'overall_quality_score': 0.0
        }
        
        # Validate companies
        for company in companies:
            validation_result = await self._validate_company(company)
            if validation_result['valid']:
                validation_report['companies']['valid'] += 1
            else:
                validation_report['companies']['invalid'] += 1
                validation_report['companies']['issues'].extend(validation_result['issues'])
        
        # Validate people
        for person in people:
            validation_result = await self._validate_person(person)
            if validation_result['valid']:
                validation_report['people']['valid'] += 1
            else:
                validation_report['people']['invalid'] += 1
                validation_report['people']['issues'].extend(validation_result['issues'])
        
        # Calculate overall quality score
        total_items = len(companies) + len(people)
        valid_items = validation_report['companies']['valid'] + validation_report['people']['valid']
        validation_report['overall_quality_score'] = valid_items / max(total_items, 1)
        
        return validation_report
    
    async def _validate_company(self, company: CompanyProfile) -> Dict[str, Any]:
        """Validate a single company profile."""
        issues = []
        
        # Check required fields
        if not company.company_name:
            issues.append("Missing company name")
        
        if not company.website_url:
            issues.append("Missing website URL")
        
        # Validate email if present
        if company.general_email:
            if not self._is_valid_email(company.general_email):
                issues.append("Invalid email format")
        
        # Check confidence score
        if company.extraction_confidence < 0.5:
            issues.append("Low extraction confidence")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }
    
    async def _validate_person(self, person: PersonProfile) -> Dict[str, Any]:
        """Validate a single person profile."""
        issues = []
        
        # Check required fields
        if not person.full_name:
            issues.append("Missing person name")
        
        # Validate email if present
        if person.email:
            if not self._is_valid_email(person.email):
                issues.append("Invalid email format")
        
        # Check confidence score
        if person.extraction_confidence < 0.5:
            issues.append("Low extraction confidence")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }
    
    def _is_valid_email(self, email: str) -> bool:
        """Basic email validation."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None


class LeadGenOrchestrator:
    """
    Main orchestrator for the B2B lead generation pipeline.
    
    Coordinates all agents using Agno's Team framework to execute
    the complete lead generation workflow.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.navigator = BrowserNavigator(self.config.get('browser', {}))
        self.extract_manager = LangExtractManager()
        
        # Initialize agents
        self.navigator_agent = WebNavigatorAgent(self.navigator)
        self.extractor_agent = ContentExtractorAgent(self.extract_manager)
        self.enricher_agent = LeadEnricherAgent()
        self.validation_agent = ValidationAgent()
        
        # Create team
        self.team = Team(
            name="LeadGenerationTeam",
            description="B2B lead generation pipeline team",
            agents=[
                self.navigator_agent,
                self.extractor_agent,
                self.enricher_agent,
                self.validation_agent
            ],
            instructions="Execute the complete B2B lead generation pipeline efficiently and accurately."
        )
    
    async def generate_leads(
        self, 
        query: str, 
        max_companies: int = 20,
        max_people: int = 50
    ) -> PipelineResult:
        """
        Execute the complete lead generation pipeline.
        
        Args:
            query: Search query for lead generation
            max_companies: Maximum number of companies to extract
            max_people: Maximum number of people to extract
            
        Returns:
            PipelineResult with extracted and validated leads
        """
        start_time = asyncio.get_event_loop().time()
        self.logger.info(f"Starting lead generation pipeline for query: {query}")
        
        try:
            # Stage 1: Navigation and Content Discovery
            self.logger.info("Stage 1: Navigation and content discovery")
            nav_results = await self._stage_navigation(query)
            
            # Stage 2: Content Extraction
            self.logger.info("Stage 2: Content extraction")
            extraction_results = await self._stage_extraction(nav_results, max_companies, max_people)
            
            # Stage 3: Data Enrichment
            self.logger.info("Stage 3: Data enrichment")
            enriched_results = await self._stage_enrichment(extraction_results)
            
            # Stage 4: Validation
            self.logger.info("Stage 4: Data validation")
            validation_report = await self._stage_validation(enriched_results)
            
            # Stage 5: Final Output
            self.logger.info("Stage 5: Final output preparation")
            pipeline_result = await self._stage_output(enriched_results, validation_report, start_time)
            
            self.logger.info(f"Lead generation pipeline completed successfully")
            return pipeline_result
            
        except Exception as e:
            self.logger.error(f"Pipeline failed with error: {e}")
            return PipelineResult(
                success=False,
                companies=[],
                people=[],
                errors=[str(e)],
                total_processing_time=asyncio.get_event_loop().time() - start_time,
                extraction_stats={},
                metadata={'error': str(e)}
            )
    
    async def _stage_navigation(self, query: str) -> List[NavigationResult]:
        """Stage 1: Navigation and content discovery."""
        # Use navigator agent to search and extract content
        results = await self.navigator_agent.search_and_discover(query, max_results=20)
        return results
    
    async def _stage_extraction(
        self, 
        nav_results: List[NavigationResult], 
        max_companies: int, 
        max_people: int
    ) -> Dict[str, Any]:
        """Stage 2: Content extraction."""
        # Prepare content items for batch extraction
        company_items = []
        person_items = []
        
        for result in nav_results[:max_companies + max_people]:
            if not result.success:
                continue
            
            # Try both company and person extraction
            if len(company_items) < max_companies:
                company_items.append({
                    'content': result.content,
                    'url': result.url,
                    'type': 'company'
                })
            
            if len(person_items) < max_people:
                person_items.append({
                    'content': result.content,
                    'url': result.url,
                    'type': 'person'
                })
        
        # Execute batch extractions
        all_items = company_items + person_items
        extraction_results = await self.extractor_agent.extract_batch(all_items)
        
        # Separate company and person results
        companies = []
        people = []
        
        for i, result in enumerate(extraction_results):
            if result.success and result.data:
                if i < len(company_items) and isinstance(result.data, CompanyProfile):
                    companies.append(result.data)
                elif i >= len(company_items) and isinstance(result.data, PersonProfile):
                    people.append(result.data)
        
        return {
            'companies': companies,
            'people': people,
            'extraction_stats': {
                'total_extractions': len(extraction_results),
                'successful_extractions': len([r for r in extraction_results if r.success]),
                'average_confidence': sum(r.confidence_score for r in extraction_results) / max(len(extraction_results), 1)
            }
        }
    
    async def _stage_enrichment(self, extraction_results: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 3: Data enrichment."""
        # Enrich company leads
        enriched_companies = await self.enricher_agent.enrich_company_leads(
            extraction_results['companies']
        )
        
        # Enrich person leads
        enriched_people = await self.enricher_agent.enrich_person_leads(
            extraction_results['people']
        )
        
        return {
            'companies': enriched_companies,
            'people': enriched_people,
            'extraction_stats': extraction_results['extraction_stats']
        }
    
    async def _stage_validation(self, enriched_results: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 4: Data validation."""
        validation_report = await self.validation_agent.validate_leads(
            enriched_results['companies'],
            enriched_results['people']
        )
        return validation_report
    
    async def _stage_output(
        self, 
        enriched_results: Dict[str, Any], 
        validation_report: Dict[str, Any],
        start_time: float
    ) -> PipelineResult:
        """Stage 5: Final output preparation."""
        total_time = asyncio.get_event_loop().time() - start_time
        
        return PipelineResult(
            success=True,
            companies=enriched_results['companies'],
            people=enriched_results['people'],
            errors=[],
            total_processing_time=total_time,
            extraction_stats={
                **enriched_results['extraction_stats'],
                'validation_report': validation_report
            },
            metadata={
                'pipeline_version': '1.0',
                'langextract_version': 'primary',
                'total_leads': len(enriched_results['companies']) + len(enriched_results['people'])
            }
        )


# Global orchestrator instance
lead_gen_orchestrator = LeadGenOrchestrator()