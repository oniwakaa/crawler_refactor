#!/usr/bin/env python3
"""
B2B Lead Generation Pipeline
Main orchestration script that coordinates all agents for end-to-end lead generation.
"""

import asyncio
import os
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

import typer
import yaml
from dotenv import load_dotenv
import structlog
import sys

# Add project root to sys.path to allow imports from agents, models, etc.
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from agents.orchestrator import OrchestratorAgent, TaskPlan
from agents.web_navigator import WebNavigatorAgent
from agents.content_extractor import ContentExtractorAgent
from agents.lead_enricher import LeadEnricherAgent
from agents.validator import ValidatorAgent
from models.lead import LeadBatch, LeadProfile

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

@dataclass
class PipelineConfig:
    """Pipeline configuration"""
    query: str
    max_results: int = 50
    settings_path: str = str(PROJECT_ROOT / "config/settings.yaml")
    output_path: Optional[str] = None
    verbose: bool = False

class B2BLeadPipeline:
    """
    Main pipeline orchestrator for B2B lead generation.
    Coordinates all agents and manages the end-to-end workflow.
    """
    
    def __init__(self, config: PipelineConfig):
        """
        Initialize pipeline with configuration.
        
        Args:
            config: PipelineConfig instance
        """
        self.config = config
        self.settings = self._load_settings()
        self.artifacts_dir = Path("artifacts")
        self.artifacts_dir.mkdir(exist_ok=True)
        
        # Initialize agents (will be set up in context manager)
        self.orchestrator: Optional[OrchestratorAgent] = None
        self.navigator: Optional[WebNavigatorAgent] = None
        self.extractor: Optional[ContentExtractorAgent] = None
        self.enricher: Optional[LeadEnricherAgent] = None
        self.validator: Optional[ValidatorAgent] = None
        
        # Pipeline metadata
        self.pipeline_id = f"pipeline_{int(time.time())}"
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from YAML file"""
        try:
            with open(self.config.settings_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Failed to load settings", error=str(e), path=self.config.settings_path)
            return {}
            
    async def __aenter__(self):
        """Async context manager entry"""
        # Initialize all agents
        self.orchestrator = OrchestratorAgent(self.config.settings_path)
        self.navigator = WebNavigatorAgent(self.config.settings_path)
        self.extractor = ContentExtractorAgent(self.config.settings_path)
        self.enricher = LeadEnricherAgent(self.config.settings_path)
        self.validator = ValidatorAgent(self.config.settings_path)
        
        self.start_time = time.time()
        logger.info("Pipeline initialized", pipeline_id=self.pipeline_id, query=self.config.query)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        self.end_time = time.time()
        if self.start_time:
            duration = self.end_time - self.start_time
            logger.info("Pipeline completed", pipeline_id=self.pipeline_id, duration=duration)
            
    async def run_pipeline(self) -> LeadBatch:
        """
        Run the complete B2B lead generation pipeline.
        
        Returns:
            LeadBatch with final results
        """
        logger.info("Starting pipeline execution", pipeline_id=self.pipeline_id)
        
        try:
            # Step 1: Orchestrator decomposes query
            logger.info("Step 1: Query decomposition")
            task_plan = await self._step_orchestrate()
            
            # Step 2: Navigator searches and fetches
            logger.info("Step 2: Search and fetch")
            pages = await self._step_navigate(task_plan)
            
            if not pages:
                logger.warning("No pages fetched, returning empty results")
                return LeadBatch(leads=[], query=self.config.query)
            
            # Step 3: Extractor extracts leads
            logger.info("Step 3: Lead extraction")
            raw_leads = await self._step_extract(pages)
            
            if not raw_leads:
                logger.warning("No leads extracted, returning empty results")
                return LeadBatch(leads=[], query=self.config.query)
            
            # Step 4: Enricher enriches and deduplicates
            logger.info("Step 4: Lead enrichment and deduplication")
            enriched_leads = await self._step_enrich(raw_leads)
            
            # Step 5: Validator validates and normalizes
            logger.info("Step 5: Lead validation")
            validated_leads = await self._step_validate(enriched_leads)
            
            # Step 6: Orchestrator aggregates final results
            logger.info("Step 6: Result aggregation")
            lead_batch = await self._step_aggregate(validated_leads)
            
            # Save final output
            self._save_artifact("pipeline_complete", {
                "lead_batch": lead_batch.model_dump(),
                "statistics": {
                    "total_leads": len(lead_batch.leads),
                    "query": self.config.query,
                    "duration": time.time() - self.start_time if self.start_time else 0
                }
            })
            
            logger.info(
                "Pipeline execution completed successfully",
                total_leads=len(lead_batch.leads),
                duration=time.time() - self.start_time if self.start_time else 0
            )
            
            return lead_batch
            
        except Exception as e:
            logger.error("Pipeline execution failed", error=str(e), pipeline_id=self.pipeline_id)
            raise
            
    async def _step_orchestrate(self) -> TaskPlan:
        """Step 1: Query decomposition"""
        try:
            async with self.orchestrator as orchestrator:
                task_plan = await orchestrator.decompose_query(self.config.query)
                logger.info(
                    "Query decomposition completed",
                    search_queries=task_plan.search_queries,
                    max_results=task_plan.max_results
                )
                return task_plan
                
        except Exception as e:
            logger.error("Query decomposition failed", error=str(e))
            raise
            
    async def _step_navigate(self, task_plan: TaskPlan) -> List[Dict[str, Any]]:
        """Step 2: Search and fetch"""
        try:
            async with self.navigator as navigator:
                all_pages = []
                max_results = min(task_plan.max_results, self.config.max_results)
                
                # Try search queries until we get results
                queries = task_plan.search_queries if task_plan.search_queries else [self.config.query]
                
                for query in queries:
                    if len(all_pages) >= max_results:
                        break
                        
                    logger.info("Executing search query", query=query)
                    pages = await navigator.search_and_fetch(query, max_results - len(all_pages))
                    
                    if pages:
                        all_pages.extend(pages)
                        logger.info("Found pages", count=len(pages), query=query)
                    else:
                        logger.warning("No results for query", query=query)
                
                logger.info("Search and fetch completed", total_pages=len(all_pages))
                return all_pages
                
        except Exception as e:
            logger.error("Search and fetch failed", error=str(e))
            return []  # Continue with empty results
            
    async def _step_extract(self, pages: List[Dict[str, Any]]) -> List[LeadProfile]:
        """Step 3: Lead extraction"""
        try:
            async with self.extractor as extractor:
                leads = await extractor.batch_extract(pages)
                logger.info("Lead extraction completed", lead_count=len(leads))
                return leads
                
        except Exception as e:
            logger.error("Lead extraction failed", error=str(e))
            return []  # Continue with empty results
            
    async def _step_enrich(self, leads: List[LeadProfile]) -> List[LeadProfile]:
        """Step 4: Lead enrichment and deduplication"""
        try:
            async with self.orchestrator as orchestrator:
                # Use orchestrator to coordinate multi-stage enrichment
                enriched_leads, stats = await orchestrator.coordinate_enrichment(leads)
                
                logger.info(
                    "Lead enrichment completed",
                    original_count=len(leads),
                    stats=stats
                )
                
                # Deduplicate leads
                async with self.enricher as enricher:
                    deduplicated_leads = await enricher.deduplicate_leads(enriched_leads)
                    
                return deduplicated_leads
                
        except Exception as e:
            logger.error("Lead enrichment failed", error=str(e))
            return leads  # Return original leads if enrichment fails
            
    async def _step_validate(self, leads: List[LeadProfile]) -> List[LeadProfile]:
        """Step 5: Lead validation"""
        try:
            async with self.validator as validator:
                # Validate and normalize leads
                validated_leads = validator.validate_and_normalize_batch(leads)
                logger.info("Lead validation completed", validated_count=len(validated_leads))
                return validated_leads
                
        except Exception as e:
            logger.error("Lead validation failed", error=str(e))
            return leads  # Return original leads if validation fails
            
    async def _step_aggregate(self, leads: List[LeadProfile]) -> LeadBatch:
        """Step 6: Result aggregation"""
        try:
            async with self.orchestrator as orchestrator:
                # Create agent outputs format for aggregation
                agent_outputs = [
                    {
                        "validated_leads": leads,
                        "total_processed": len(leads)
                    }
                ]
                
                lead_batch = await orchestrator.aggregate_results(agent_outputs)
                logger.info("Result aggregation completed", total_leads=len(lead_batch.leads))
                return lead_batch
                
        except Exception as e:
            logger.error("Result aggregation failed", error=str(e))
            # Return basic LeadBatch if aggregation fails
            return LeadBatch(leads=leads, query=self.config.query)
            
    def _save_artifact(self, stage: str, data: Dict[str, Any]):
        """
        Save pipeline artifact.
        
        Args:
            stage: Stage name
            data: Data to save
        """
        timestamp = int(time.time())
        filename = f"{self.pipeline_id}_{stage}_{timestamp}.json"
        filepath = self.artifacts_dir / filename
        
        artifact = {
            "pipeline_id": self.pipeline_id,
            "timestamp": timestamp,
            "stage": stage,
            "data": data,
            "metadata": {
                "query": self.config.query,
                "max_results": self.config.max_results
            }
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(artifact, f, indent=2, default=str)
                
            logger.info("Pipeline artifact saved", stage=stage, filepath=str(filepath))
        except Exception as e:
            logger.error("Failed to save pipeline artifact", stage=stage, error=str(e))

# CLI Interface
app = typer.Typer(help="B2B Lead Generation Pipeline")

@app.command()
def run(
    query: str = typer.Argument(..., help="Search query for lead generation"),
    max_results: int = typer.Option(50, "--max-results", "-m", help="Maximum number of results"),
    settings: str = typer.Option(str(PROJECT_ROOT / "config/settings.yaml"), "--settings", "-s", help="Settings file path"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (JSON)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """
    Run B2B lead generation pipeline with specified query.
    """
    # Load environment variables
    load_dotenv()
    
    # Configure logging level
    if verbose:
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    # Create pipeline config
    config = PipelineConfig(
        query=query,
        max_results=max_results,
        settings_path=settings,
        output_path=output,
        verbose=verbose
    )
    
    # Run pipeline
    async def run_async():
        async with B2BLeadPipeline(config) as pipeline:
            return await pipeline.run_pipeline()
    
    try:
        # Run async pipeline
        lead_batch = asyncio.run(run_async())
        
        # Print results summary
        print("\n" + "="*60)
        print("B2B LEAD GENERATION RESULTS")
        print("="*60)
        print(f"Query: {query}")
        print(f"Total Leads: {len(lead_batch.leads)}")
        print(f"Average Confidence: {lead_batch.metadata.get('avg_confidence', 0):.2f}")
        print(f"Success Rate: {lead_batch.metadata.get('success_rate', 0):.2%}")
        print("="*60)
        
        # Display sample leads
        if lead_batch.leads:
            print("\nSample Leads:")
            for i, lead in enumerate(lead_batch.leads[:3], 1):
                print(f"{i}. {lead.name} - {lead.role} at {lead.company}")
                if lead.email:
                    print(f"   Email: {lead.email}")
                if lead.linkedin:
                    print(f"   LinkedIn: {lead.linkedin}")
                print()
        
        # Save to output file if specified
        if output:
            output_path = Path(output)
            with open(output_path, 'w') as f:
                json.dump(lead_batch.model_dump(), f, indent=2, default=str)
            print(f"Results saved to: {output_path}")
        
        return lead_batch
        
    except Exception as e:
        logger.error("Pipeline execution failed", error=str(e))
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)

@app.command()
def validate_config(
    settings: str = typer.Option(str(PROJECT_ROOT / "config/settings.yaml"), "--settings", "-s", help="Settings file path"),
):
    """
    Validate pipeline configuration and dependencies.
    """
    # Load environment variables
    load_dotenv()
    
    print("Validating configuration...")
    
    # Check settings file
    settings_path = Path(settings)
    if not settings_path.exists():
        typer.echo(f"Error: Settings file not found: {settings_path}", err=True)
        raise typer.Exit(1)
    
    # Check environment variables
    required_vars = ["FIRECRAWL_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        typer.echo(f"Warning: Missing environment variables: {', '.join(missing_vars)}", err=True)
    
    # Check prompt files
    prompt_files = [
        PROJECT_ROOT / "config/prompts/orchestrator_system.txt",
        PROJECT_ROOT / "config/prompts/extractor_lead_profile.txt",
        PROJECT_ROOT / "config/prompts/enricher_inference.txt"
    ]
    
    missing_prompts = [str(f) for f in prompt_files if not f.exists()]
    if missing_prompts:
        typer.echo(f"Warning: Missing prompt files: {', '.join(missing_prompts)}", err=True)
    
    print("Configuration validation completed")
    print("✅ Settings file found")
    print("✅ Environment variables loaded")
    print("✅ Prompt files checked")

if __name__ == "__main__":
    app()