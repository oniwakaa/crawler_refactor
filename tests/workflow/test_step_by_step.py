import pytest
import asyncio
import json
import logging
from typing import Any, Dict
from agents.orchestrator import OrchestratorAgent
from agents.web_navigator import WebNavigatorAgent
from agents.content_extractor import ContentExtractorAgent
from agents.lead_enricher import LeadEnricherAgent
from agents.validator import ValidatorAgent
from models.lead import LeadProfile
from dotenv import load_dotenv
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workflow_test")

LOG_FILE = "workflow_internal_log.txt"

def write_log(content: str):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(content + "\n")
    print(content)

def log_section(title: str):
    content = f"\n{'='*80}\n{title}\n{'='*80}"
    write_log(content)

def log_step(step_name: str, input_data: Any, output_data: Any, agent: Any = None):
    header = f"\n{'-'*40}\nSTEP: {step_name}\n{'-'*40}"
    write_log(header)
    
    input_str = f"\n[INPUT]:\n{json.dumps(input_data, indent=2, default=str) if isinstance(input_data, (dict, list)) else str(input_data)}"
    write_log(input_str)
    
    if agent and hasattr(agent, 'llama_wrapper') and hasattr(agent.llama_wrapper, 'last_interaction'):
        interaction = agent.llama_wrapper.last_interaction
        if interaction:
            llm_str = f"\n[LLM INTERACTION]:\n  Model: {interaction.get('model')}\n  Prompt Preview: {interaction.get('prompt')[:500]}..." if interaction.get('prompt') else "None"
            llm_str += f"\n  Response Preview: {str(interaction.get('response'))[:500]}..." if interaction.get('response') else "None"
            write_log(llm_str)
    
    output_str = f"\n[OUTPUT]:\n{json.dumps(output_data, indent=2, default=str) if hasattr(output_data, 'model_dump') else (json.dumps(output_data, indent=2, default=str) if isinstance(output_data, (dict, list)) else str(output_data))}"
    write_log(output_str)

@pytest.mark.asyncio
async def test_workflow_step_by_step():
    """
    Execute the agent workflow step-by-step, logging inputs, outputs, and LLM interactions.
    This test is designed for debugging and prompt engineering.
    """
    log_section("STARTING WORKFLOW TEST")
    
    # Load environment variables
    load_dotenv()
    if not os.getenv("FIRECRAWL_API_KEY"):
        logger.warning("FIRECRAWL_API_KEY not set in environment. Search may fail.")
    
    # Initialize Agents
    orchestrator = OrchestratorAgent()
    navigator = WebNavigatorAgent()
    extractor = ContentExtractorAgent()
    enricher = LeadEnricherAgent()
    validator = ValidatorAgent()
    
    # Use context managers to ensure proper setup (e.g. http clients, sub-agents)
    async with orchestrator, navigator, extractor, enricher, validator:
    
        # --- STEP 1: Query Decomposition ---
        user_query = "Find AI startups in San Francisco"
        log_section("STEP 1: QUERY DECOMPOSITION")
        
        task_plan = await orchestrator.decompose_query(user_query)
        log_step("Decompose Query", user_query, task_plan.model_dump(), agent=orchestrator)
        
        assert task_plan is not None
        assert len(task_plan.search_queries) > 0
        
        # --- STEP 2: Web Search ---
        log_section("STEP 2: WEB SEARCH")
        # Use the first search query from the plan
        search_query = task_plan.search_queries[0]
        
        # Optimize query (sub-step)
        # Navigator uses query_builder internally but we can access it if we want to test it separately
        # But search_and_fetch calls it. Let's call search_and_fetch directly.
        
        # Note: search_and_fetch might optimize the query internally.
        # Let's check if we can see the optimized query.
        # WebNavigatorAgent.search_and_fetch calls self.query_builder.build_search_query
        
        search_results = await navigator.search_and_fetch(search_query, max_results=2)
        
        # We can try to get the optimized query from the query builder's last interaction if we want
        # But let's just log the results.
        log_step("Search and Fetch", search_query, [
            {"url": r.get("url"), "title": r.get("title"), "content_preview": r.get("markdown", "")[:100]} 
            for r in search_results
        ], agent=navigator) # Navigator doesn't have llama_wrapper directly, it uses QueryBuilder
        
        assert len(search_results) > 0
        
        # --- STEP 3: Content Extraction ---
        log_section("STEP 3: CONTENT EXTRACTION")
        
        extracted_leads = await extractor.batch_extract(search_results)
        log_step("Batch Extract", f"{len(search_results)} pages", [l.model_dump() for l in extracted_leads], agent=extractor)
        
        # --- STEP 4: Enrichment ---
        log_section("STEP 4: ENRICHMENT")
        
        if extracted_leads:
            # Orchestrator coordinates enrichment, but it needs the enricher instance.
            # In the pipeline, orchestrator.enricher is set in __aenter__.
            # Here we are managing them manually. 
            # Orchestrator.coordinate_enrichment uses self.enricher.
            # We need to make sure orchestrator has the enricher instance.
            # Orchestrator.__aenter__ creates a NEW LeadEnricherAgent.
            # Since we are using `async with orchestrator`, it has its own enricher.
            # We can use that one.
            
            enriched_leads, enrichment_stats = await orchestrator.coordinate_enrichment(extracted_leads)
            
            log_step("Coordinate Enrichment", [l.model_dump() for l in extracted_leads], [l.model_dump() for l in enriched_leads], agent=orchestrator.enricher)
            
            # Explicitly trigger tool-based enrichment for each lead (Fixing missing step)
            log_section("STEP 4.5: TOOL-BASED ENRICHMENT")
            fully_enriched_leads = []
            for lead in enriched_leads:
                try:
                    enriched_lead = await enricher.infer_missing_fields(lead)
                    fully_enriched_leads.append(enriched_lead)
                except Exception as e:
                    logger.error(f"Enrichment failed for {lead.name}: {e}")
                    fully_enriched_leads.append(lead)
            
            log_step("Tool-Based Enrichment", [l.model_dump() for l in enriched_leads], [l.model_dump() for l in fully_enriched_leads], agent=enricher)
            
            # Use fully enriched leads for validation
            enriched_leads = fully_enriched_leads
            
        else:
            print("No leads extracted, skipping enrichment.")
            enriched_leads = []

        # --- STEP 5: Validation ---
        log_section("STEP 5: VALIDATION")
        
        if enriched_leads:
            validated_leads = validator.validate_and_normalize_batch(enriched_leads)
            log_step("Validate and Normalize", [l.model_dump() for l in enriched_leads], [l.model_dump() for l in validated_leads], agent=validator)
        else:
            validated_leads = []
            
        log_section("WORKFLOW TEST COMPLETED")
        print(f"Total Validated Leads: {len(validated_leads)}")

if __name__ == "__main__":
    asyncio.run(test_workflow_step_by_step())
