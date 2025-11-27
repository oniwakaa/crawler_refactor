#!/usr/bin/env python3
"""
Test script for agent integration to verify agents work together correctly.
Run this after implementing agents to ensure they integrate properly.
"""

import asyncio
import sys
import os
from typing import List, Dict, Any
import structlog

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.orchestrator import OrchestratorAgent, TaskPlan
from agents.web_navigator import WebNavigatorAgent
from agents.content_extractor import ContentExtractorAgent
from agents.lead_enricher import LeadEnricherAgent
from agents.validator import ValidatorAgent, ValidationResult
from models.lead import LeadProfile, LeadBatch
from pydantic import BaseModel, Field

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

class TestResult(BaseModel):
    """Test result model"""
    test_name: str
    status: str  # "pass", "fail", "skip"
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)

async def test_orchestrator_decompose_query() -> TestResult:
    """Test OrchestratorAgent query decomposition"""
    test_name = "OrchestratorAgent.decompose_query"
    
    try:
        async with OrchestratorAgent() as orchestrator:
            # Test query
            user_input = "Find CTOs at SaaS companies in Berlin"
            
            logger.info("Testing orchestrator query decomposition", query=user_input)
            task_plan = await orchestrator.decompose_query(user_input)
            
            # Validate task plan
            if not task_plan.search_queries:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="No search queries generated",
                    details={"task_plan": task_plan.model_dump()}
                )
            
            if not task_plan.target_fields:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="No target fields specified",
                    details={"task_plan": task_plan.model_dump()}
                )
            
            if task_plan.max_results <= 0:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Invalid max_results",
                    details={"max_results": task_plan.max_results}
                )
            
            if not (0.0 <= task_plan.quality_threshold <= 1.0):
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Invalid quality_threshold",
                    details={"quality_threshold": task_plan.quality_threshold}
                )
            
            logger.info("Orchestrator test passed", task_plan=task_plan.model_dump())
            return TestResult(
                test_name=test_name,
                status="pass",
                message="Query decomposition successful",
                details={"search_queries": task_plan.search_queries, "target_fields": task_plan.target_fields}
            )
            
    except Exception as e:
        logger.error("Orchestrator test failed", error=str(e))
        return TestResult(
            test_name=test_name,
            status="fail",
            message=f"Exception: {str(e)}",
            details={"error": str(e)}
        )

async def test_web_navigator_search_and_fetch() -> TestResult:
    """Test WebNavigatorAgent search and fetch"""
    test_name = "WebNavigatorAgent.search_and_fetch"
    
    # Check if API key is available
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        return TestResult(
            test_name=test_name,
            status="skip",
            message="FIRECRAWL_API_KEY not set"
        )
    
    try:
        async with WebNavigatorAgent() as navigator:
            # Test with a simple query
            query = "test query"
            max_results = 3
            
            logger.info("Testing web navigator search and fetch", query=query, max_results=max_results)
            results = await navigator.search_and_fetch(query, max_results)
            
            if not results:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="No results returned",
                    details={"query": query, "max_results": max_results}
                )
            
            # Check result structure
            result = results[0]
            required_fields = ["url", "markdown", "fetch_status", "method_used"]
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message=f"Missing required fields: {missing_fields}",
                    details={"result_keys": list(result.keys())}
                )
            
            if result.get("fetch_status") != "success":
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message=f"Fetch failed with status: {result.get('fetch_status')}",
                    details={"error": result.get("error")}
                )
            
            if not result.get("markdown"):
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Empty markdown content",
                    details={"url": result.get("url")}
                )
            
            logger.info("Web navigator test passed", result_count=len(results))
            return TestResult(
                test_name=test_name,
                status="pass",
                message=f"Fetched {len(results)} URLs successfully",
                details={
                    "url": result.get("url"),
                    "markdown_length": len(result.get("markdown", "")),
                    "method_used": result.get("method_used")
                }
            )
            
    except Exception as e:
        logger.error("Web navigator test failed", error=str(e))
        return TestResult(
            test_name=test_name,
            status="fail",
            message=f"Exception: {str(e)}",
            details={"error": str(e)}
        )

async def test_content_extractor_batch_extract() -> TestResult:
    """Test ContentExtractorAgent batch extraction"""
    test_name = "ContentExtractorAgent.batch_extract"
    
    # Create test pages with sample content
    test_pages = [
        {
            "url": "https://example.com/test1",
            "markdown": """
            John Doe
            CTO at TechCorp
            Email: john@techcorp.com
            LinkedIn: linkedin.com/in/johndoe
            Phone: +1-555-123-4567
            """
        },
        {
            "url": "https://example.com/test2",
            "markdown": """
            Jane Smith
            VP of Engineering at SaaS Inc
            Email: jane@saasinc.com
            LinkedIn: linkedin.com/in/janesmith
            """
        }
    ]
    
    try:
        async with ContentExtractorAgent() as extractor:
            logger.info("Testing content extractor batch extraction", page_count=len(test_pages))
            leads = await extractor.batch_extract(test_pages)
            
            if not leads:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="No leads extracted",
                    details={"page_count": len(test_pages)}
                )
            
            # Check lead structure
            lead = leads[0]
            if not isinstance(lead, LeadProfile):
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Extracted object is not a LeadProfile",
                    details={"lead_type": type(lead).__name__}
                )
            
            if not lead.name:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="No name extracted",
                    details={"lead": lead.model_dump()}
                )
            
            if not lead.company:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="No company extracted",
                    details={"lead": lead.model_dump()}
                )
            
            logger.info("Content extractor test passed", lead_count=len(leads))
            return TestResult(
                test_name=test_name,
                status="pass",
                message=f"Extracted {len(leads)} leads successfully",
                details={
                    "lead_count": len(leads),
                    "sample_lead": {
                        "name": lead.name,
                        "role": lead.role,
                        "company": lead.company,
                        "confidence": lead.confidence_score
                    }
                }
            )
            
    except Exception as e:
        logger.error("Content extractor test failed", error=str(e))
        return TestResult(
            test_name=test_name,
            status="fail",
            message=f"Exception: {str(e)}",
            details={"error": str(e)}
        )

async def test_lead_enricher_infer_missing_fields() -> TestResult:
    """Test LeadEnricherAgent field inference"""
    test_name = "LeadEnricherAgent.infer_missing_fields"
    
    # Create test lead with missing fields
    test_lead = LeadProfile(
        name="Alice Johnson",
        role="CEO",
        company="StartupXYZ",
        company_domain=None,  # Missing
        email=None,  # Missing
        phone_number=None,  # Missing
        linkedin=None,  # Missing
        confidence_score=0.5
    )
    
    try:
        async with LeadEnricherAgent() as enricher:
            logger.info("Testing lead enricher field inference", lead_name=test_lead.name)
            enriched_lead = await enricher.infer_missing_fields(test_lead)
            
            # Check if any fields were inferred
            inferred_fields = []
            if enriched_lead.company_domain and not test_lead.company_domain:
                inferred_fields.append("company_domain")
            if enriched_lead.email and not test_lead.email:
                inferred_fields.append("email")
            if enriched_lead.phone_number and not test_lead.phone_number:
                inferred_fields.append("phone_number")
            if enriched_lead.linkedin and not test_lead.linkedin:
                inferred_fields.append("linkedin")
            
            logger.info("Lead enricher test completed", inferred_fields=inferred_fields)
            return TestResult(
                test_name=test_name,
                status="pass",
                message=f"Field inference completed. Inferred: {inferred_fields}",
                details={
                    "inferred_fields": inferred_fields,
                    "original_confidence": test_lead.confidence_score,
                    "enriched_confidence": enriched_lead.confidence_score
                }
            )
            
    except Exception as e:
        logger.error("Lead enricher test failed", error=str(e))
        return TestResult(
            test_name=test_name,
            status="fail",
            message=f"Exception: {str(e)}",
            details={"error": str(e)}
        )

async def test_lead_enricher_deduplicate_leads() -> TestResult:
    """Test LeadEnricherAgent deduplication"""
    test_name = "LeadEnricherAgent.deduplicate_leads"
    
    # Create test leads with duplicates
    test_leads = [
        LeadProfile(
            name="John Doe",
            role="CTO",
            company="TechCorp",
            email="john@techcorp.com",
            confidence_score=0.9
        ),
        LeadProfile(
            name="John Doe",
            role="Chief Technology Officer",
            company="TechCorp Inc",
            email="john@techcorp.com",  # Same email - duplicate
            confidence_score=0.7
        ),
        LeadProfile(
            name="Jane Smith",
            role="VP Engineering",
            company="SaaS Inc",
            linkedin="linkedin.com/in/janesmith",
            confidence_score=0.8
        ),
        LeadProfile(
            name="Jane Smith",
            role="VP of Engineering",
            company="SaaS Inc",
            linkedin="linkedin.com/in/janesmith",  # Same LinkedIn - duplicate
            confidence_score=0.6
        )
    ]
    
    try:
        async with LeadEnricherAgent() as enricher:
            logger.info("Testing lead enricher deduplication", lead_count=len(test_leads))
            deduplicated_leads = await enricher.deduplicate_leads(test_leads)
            
            if len(deduplicated_leads) >= len(test_leads):
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="No duplicates removed",
                    details={
                        "original_count": len(test_leads),
                        "deduplicated_count": len(deduplicated_leads)
                    }
                )
            
            logger.info("Lead enricher deduplication test passed", 
                       original_count=len(test_leads), 
                       deduplicated_count=len(deduplicated_leads))
            return TestResult(
                test_name=test_name,
                status="pass",
                message=f"Removed {len(test_leads) - len(deduplicated_leads)} duplicates",
                details={
                    "original_count": len(test_leads),
                    "deduplicated_count": len(deduplicated_leads),
                    "duplicates_removed": len(test_leads) - len(deduplicated_leads)
                }
            )
            
    except Exception as e:
        logger.error("Lead enricher deduplication test failed", error=str(e))
        return TestResult(
            test_name=test_name,
            status="fail",
            message=f"Exception: {str(e)}",
            details={"error": str(e)}
        )

async def test_validator_validate_lead() -> TestResult:
    """Test ValidatorAgent lead validation"""
    test_name = "ValidatorAgent.validate_lead"
    
    # Create test lead with valid data
    test_lead = LeadProfile(
        name="John Doe",
        role="CTO",
        company="TechCorp",
        email="john@techcorp.com",
        linkedin="linkedin.com/in/johndoe",
        company_domain="techcorp.com",
        phone_number="+1-555-123-4567",
        confidence_score=0.9
    )
    
    try:
        async with ValidatorAgent() as validator:
            logger.info("Testing validator lead validation", lead_name=test_lead.name)
            validation_result = validator.validate_lead(test_lead)
            
            if not validation_result.is_valid:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Valid lead failed validation",
                    details={"errors": validation_result.errors}
                )
            
            logger.info("Validator test passed", validation_result=validation_result.is_valid)
            return TestResult(
                test_name=test_name,
                status="pass",
                message="Lead validation successful",
                details={
                    "is_valid": validation_result.is_valid,
                    "error_count": len(validation_result.errors),
                    "warning_count": len(validation_result.warnings)
                }
            )
            
    except Exception as e:
        logger.error("Validator test failed", error=str(e))
        return TestResult(
            test_name=test_name,
            status="fail",
            message=f"Exception: {str(e)}",
            details={"error": str(e)}
        )

async def test_validator_normalize_data() -> TestResult:
    """Test ValidatorAgent data normalization"""
    test_name = "ValidatorAgent.normalize_data"
    
    # Create test lead with messy data
    test_lead = LeadProfile(
        name="john doe",
        role="cto",
        company="techcorp inc",
        email="JOHN@TECHCORP.COM",
        linkedin="linkedin.com/in/johndoe",
        company_domain="https://www.techcorp.com",
        phone_number="555-123-4567",
        confidence_score=0.8
    )
    
    try:
        async with ValidatorAgent() as validator:
            logger.info("Testing validator data normalization", lead_name=test_lead.name)
            normalized_lead = validator.normalize_data(test_lead)
            
            # Check normalization
            if normalized_lead.name != "John Doe":
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Name not normalized correctly",
                    details={"original": test_lead.name, "normalized": normalized_lead.name}
                )
            
            if normalized_lead.email != "john@techcorp.com":
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Email not normalized correctly",
                    details={"original": test_lead.email, "normalized": normalized_lead.email}
                )
            
            if normalized_lead.company_domain != "techcorp.com":
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Domain not normalized correctly",
                    details={"original": test_lead.company_domain, "normalized": normalized_lead.company_domain}
                )
            
            logger.info("Validator normalization test passed")
            return TestResult(
                test_name=test_name,
                status="pass",
                message="Data normalization successful",
                details={
                    "original_name": test_lead.name,
                    "normalized_name": normalized_lead.name,
                    "original_email": test_lead.email,
                    "normalized_email": normalized_lead.email
                }
            )
            
    except Exception as e:
        logger.error("Validator normalization test failed", error=str(e))
        return TestResult(
            test_name=test_name,
            status="fail",
            message=f"Exception: {str(e)}",
            details={"error": str(e)}
        )

async def run_all_tests() -> List[TestResult]:
    """Run all agent integration tests"""
    logger.info("Starting agent integration tests")
    
    tests = [
        test_orchestrator_decompose_query,
        test_web_navigator_search_and_fetch,
        test_content_extractor_batch_extract,
        test_lead_enricher_infer_missing_fields,
        test_lead_enricher_deduplicate_leads,
        test_validator_validate_lead,
        test_validator_normalize_data
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
            logger.info(f"Test {result.test_name}: {result.status}", message=result.message)
        except Exception as e:
            logger.error(f"Test {test.__name__} crashed", error=str(e))
            results.append(TestResult(
                test_name=test.__name__,
                status="fail",
                message=f"Test crashed: {str(e)}",
                details={"error": str(e)}
            ))
    
    # Print summary
    print("\n" + "="*60)
    print("AGENT INTEGRATION TEST SUMMARY")
    print("="*60)
    
    status_counts = {"pass": 0, "fail": 0, "skip": 0}
    for result in results:
        status_counts[result.status] += 1
        status_symbol = {
            "pass": "✅",
            "fail": "❌",
            "skip": "⏭️"
        }[result.status]
        
        print(f"{status_symbol} {result.test_name}: {result.message}")
        if result.details:
            print(f"   Details: {result.details}")
    
    print("\n" + "-"*60)
    print(f"Total: {len(results)} | Passed: {status_counts['pass']} | Failed: {status_counts['fail']} | Skipped: {status_counts['skip']}")
    print("="*60)
    
    return results

if __name__ == "__main__":
    # Run tests
    results = asyncio.run(run_all_tests())
    
    # Exit with error code if any tests failed
    failed_count = len([r for r in results if r.status == "fail"])
    sys.exit(1 if failed_count > 0 else 0)