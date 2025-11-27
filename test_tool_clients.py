#!/usr/bin/env python3
"""
Test script for tool clients to verify basic functionality.
Run this after implementing tool clients to ensure they work correctly.
"""

import asyncio
import sys
import os
from typing import List, Dict, Any
import structlog

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.firecrawl_client import FirecrawlClient
from tools.crawl4ai_client import Crawl4AIClient
from tools.llama_wrapper import LlamaWrapper
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

async def test_firecrawl_search() -> TestResult:
    """Test FirecrawlClient search functionality"""
    test_name = "FirecrawlClient.search"
    
    # Check if API key is available
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        return TestResult(
            test_name=test_name,
            status="skip",
            message="FIRECRAWL_API_KEY not set"
        )
    
    try:
        async with FirecrawlClient(api_key=api_key) as client:
            # Test search
            query = "test search query"
            max_results = 3
            
            logger.info("Testing Firecrawl search", query=query, max_results=max_results)
            urls = await client.search(query, max_results)
            
            if not urls:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Search returned no URLs",
                    details={"query": query, "max_results": max_results}
                )
            
            if len(urls) > max_results:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message=f"Returned more URLs than requested: {len(urls)} > {max_results}",
                    details={"urls_count": len(urls), "max_results": max_results}
                )
            
            logger.info("Firecrawl search test passed", url_count=len(urls))
            return TestResult(
                test_name=test_name,
                status="pass",
                message=f"Found {len(urls)} URLs",
                details={"urls": urls[:2]}  # Show first 2 URLs
            )
            
    except Exception as e:
        logger.error("Firecrawl search test failed", error=str(e))
        return TestResult(
            test_name=test_name,
            status="fail",
            message=f"Exception: {str(e)}",
            details={"error": str(e)}
        )

async def test_firecrawl_batch_scrape() -> TestResult:
    """Test FirecrawlClient batch_scrape functionality"""
    test_name = "FirecrawlClient.batch_scrape"
    
    # Check if API key is available
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        return TestResult(
            test_name=test_name,
            status="skip",
            message="FIRECRAWL_API_KEY not set"
        )
    
    try:
        async with FirecrawlClient(api_key=api_key) as client:
            # Test with a simple, reliable URL
            test_urls = ["https://example.com"]
            
            logger.info("Testing Firecrawl batch scrape", urls=test_urls)
            results = await client.batch_scrape(test_urls)
            
            if not results:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Batch scrape returned no results",
                    details={"urls": test_urls}
                )
            
            # Check result structure
            result = results[0]
            required_fields = ["url", "markdown"]
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message=f"Missing required fields: {missing_fields}",
                    details={"result_keys": list(result.keys())}
                )
            
            if not result.get("markdown"):
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Empty markdown content",
                    details={"url": result.get("url")}
                )
            
            logger.info("Firecrawl batch scrape test passed", result_count=len(results))
            return TestResult(
                test_name=test_name,
                status="pass",
                message=f"Scraped {len(results)} URLs successfully",
                details={
                    "url": result.get("url"),
                    "markdown_length": len(result.get("markdown", ""))
                }
            )
            
    except Exception as e:
        logger.error("Firecrawl batch scrape test failed", error=str(e))
        return TestResult(
            test_name=test_name,
            status="fail",
            message=f"Exception: {str(e)}",
            details={"error": str(e)}
        )

async def test_crawl4ai_batch_fetch() -> TestResult:
    """Test Crawl4AIClient batch_fetch functionality"""
    test_name = "Crawl4AIClient.batch_fetch"
    
    try:
        async with Crawl4AIClient() as client:
            # Test with a simple, reliable URL
            test_urls = ["https://example.com"]
            
            logger.info("Testing Crawl4AI batch fetch", urls=test_urls)
            results = await client.batch_fetch(test_urls)
            
            if not results:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Batch fetch returned no results",
                    details={"urls": test_urls}
                )
            
            # Check result structure
            result = results[0]
            required_fields = ["url", "markdown", "fetch_status"]
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
            
            logger.info("Crawl4AI batch fetch test passed", result_count=len(results))
            return TestResult(
                test_name=test_name,
                status="pass",
                message=f"Fetched {len(results)} URLs successfully",
                details={
                    "url": result.get("url"),
                    "markdown_length": len(result.get("markdown", "")),
                    "fetch_duration": result.get("fetch_duration")
                }
            )
            
    except Exception as e:
        logger.error("Crawl4AI batch fetch test failed", error=str(e))
        return TestResult(
            test_name=test_name,
            status="fail",
            message=f"Exception: {str(e)}",
            details={"error": str(e)}
        )

class TestSchema(BaseModel):
    """Test schema for structured extraction"""
    name: str = Field(..., description="A name")
    description: str = Field(..., description="A description")

async def test_llama_wrapper_generate() -> TestResult:
    """Test LlamaWrapper generate functionality"""
    test_name = "LlamaWrapper.generate"
    
    # Check if Ollama is available
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    
    try:
        async with LlamaWrapper(ollama_host=ollama_host) as wrapper:
            # Test with a simple prompt
            prompt = "Say 'Hello, World!' and nothing else."
            model = "gpt-oss:20b-cloud"  # Use smaller model for testing
            
            logger.info("Testing LlamaWrapper generate", prompt=prompt[:50], model=model)
            response = await wrapper.generate(prompt, model, temperature=0.1, max_tokens=50)
            
            if not response:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Empty response from model",
                    details={"prompt": prompt, "model": model}
                )
            
            if "hello" not in response.lower():
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Response doesn't contain expected content",
                    details={"response": response}
                )
            
            logger.info("LlamaWrapper generate test passed", response_length=len(response))
            return TestResult(
                test_name=test_name,
                status="pass",
                message="Generated response successfully",
                details={"response": response[:100]}  # Show first 100 chars
            )
            
    except Exception as e:
        logger.error("LlamaWrapper generate test failed", error=str(e))
        return TestResult(
            test_name=test_name,
            status="fail",
            message=f"Exception: {str(e)}",
            details={"error": str(e)}
        )

async def test_llama_wrapper_structured_extract() -> TestResult:
    """Test LlamaWrapper structured_extract functionality"""
    test_name = "LlamaWrapper.structured_extract"
    
    # Check if Ollama is available
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    
    try:
        async with LlamaWrapper(ollama_host=ollama_host) as wrapper:
            # Test with a simple extraction prompt
            prompt = "Extract the name 'Alice' and description 'A software engineer' from this text."
            model = "gpt-oss:20b-cloud"  # Use smaller model for testing
            
            logger.info("Testing LlamaWrapper structured extract", prompt=prompt[:50], model=model)
            result = await wrapper.structured_extract(prompt, TestSchema, model, temperature=0.1, max_tokens=200)
            
            if not result:
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Empty result from structured extraction",
                    details={"prompt": prompt, "model": model}
                )
            
            if not isinstance(result, TestSchema):
                return TestResult(
                    test_name=test_name,
                    status="fail",
                    message="Result is not correct type",
                    details={"result_type": type(result).__name__}
                )
            
            logger.info("LlamaWrapper structured extract test passed", result=result.model_dump())
            return TestResult(
                test_name=test_name,
                status="pass",
                message="Structured extraction successful",
                details={"result": result.model_dump()}
            )
            
    except Exception as e:
        logger.error("LlamaWrapper structured extract test failed", error=str(e))
        return TestResult(
            test_name=test_name,
            status="fail",
            message=f"Exception: {str(e)}",
            details={"error": str(e)}
        )

async def run_all_tests() -> List[TestResult]:
    """Run all tool client tests"""
    logger.info("Starting tool client tests")
    
    tests = [
        test_firecrawl_search,
        test_firecrawl_batch_scrape,
        test_crawl4ai_batch_fetch,
        test_llama_wrapper_generate,
        test_llama_wrapper_structured_extract
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
    print("TOOL CLIENT TEST SUMMARY")
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