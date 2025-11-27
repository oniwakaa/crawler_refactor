import pytest
import os
from agents.web_navigator import WebNavigatorAgent
from agents.content_extractor import ContentExtractorAgent

@pytest.mark.asyncio
async def test_search_and_extract_flow():
    """
    Integration test: Search for a query -> Fetch pages -> Extract content.
    Uses real Firecrawl and Crawl4AI clients.
    """
    # Verify API key exists
    if not os.getenv("FIRECRAWL_API_KEY"):
        pytest.skip("FIRECRAWL_API_KEY not set")

    # 1. Search and Fetch
    async with WebNavigatorAgent() as navigator:
        query = "AI startups in San Francisco"
        max_results = 2
        pages = await navigator.search_and_fetch(query, max_results)
        
        print(f"DEBUG: Found {len(pages)} pages for query '{query}'")
        assert len(pages) > 0
        assert "markdown" in pages[0]
        assert len(pages[0]["markdown"]) > 0

    # 2. Extract Content
    async with ContentExtractorAgent() as extractor:
        leads = await extractor.batch_extract(pages)
        
        # We might not get leads from every page, but we should handle the flow without error
        # and hopefully get at least one lead or process the content.
        assert isinstance(leads, list)
        if leads:
            first_lead = leads[0]
            assert first_lead.source_url is not None
