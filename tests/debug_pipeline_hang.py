#!/usr/bin/env python3
"""
Test script to debug pipeline hanging issue.
Tests basic Crawl4AI functionality with LinkedIn authentication.
"""
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from tools.crawl4ai_client import Crawl4AIClient
import yaml
import structlog

logger = structlog.get_logger()

async def test_basic_scraping():
    """Test basic LinkedIn scraping with authentication."""
    print("Loading settings...")
    with open("config/settings.yaml") as f:
        settings = yaml.safe_load(f)
    
    print("Initializing Crawl4AI with LinkedIn authentication...")
    client = Crawl4AIClient(
        linkedin_auth=True,
        settings=settings
    )
    
    print("Starting crawler...")
    async with client as crawler:
        print("✅ Crawler started successfully")
        
        # Test 1: Fetch Carlo's profile directly
        print("\nTest 1: Direct profile fetch")
        carlo_url = "https://www.linkedin.com/in/carlobizzaro/"
        
        print(f"Fetching: {carlo_url}")
        result = await crawler.fetch_linkedin_profile(carlo_url)
        
        if result["fetch_status"] == "success":
            print(f"✅ Successfully fetched profile")
            print(f"   Markdown length: {len(result['markdown'])} chars")
            print(f"   First 200 chars: {result['markdown'][:200]}")
        else:
            print(f"❌ Failed to fetch profile: {result.get('error')}")
    
    print("\n✅ Test completed successfully")

if __name__ == "__main__":
    asyncio.run(test_basic_scraping())
