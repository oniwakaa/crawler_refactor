import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from agents.web_navigator import WebNavigatorAgent

class TestLinkedInPeopleSearch:
    
    @pytest.mark.asyncio
    async def test_linkedin_search_integration(self):
        """Test the full flow of LinkedIn search URL generation and handling."""
        
        # Mock dependencies
        with patch('agents.web_navigator.FirecrawlClient') as mock_fc, \
             patch('agents.web_navigator.Crawl4AIClient') as mock_c4:
            
            # Setup mocks
            mock_fc_instance = mock_fc.return_value
            mock_fc_instance.__aenter__.return_value = mock_fc_instance
            
            mock_c4_instance = mock_c4.return_value
            mock_c4_instance.__aenter__.return_value = mock_c4_instance
            # Note: validate_linkedin_session should be async
            mock_c4_instance.validate_linkedin_session = AsyncMock(return_value=True)
            
            # Mock search page response
            mock_c4_instance.batch_fetch.return_value = [{
                "url": "https://www.linkedin.com/search/results/people/?keywords=CTO",
                "fetch_status": "success",
                "markdown": "Found results: [John Doe](https://www.linkedin.com/in/john-doe) and [Jane Smith](/in/jane-smith)",
                "html": '<a href="/in/jane-smith">Jane Smith</a>'
            }]
            
            # Initialize agent
            agent = WebNavigatorAgent()
            
            # Mock query builder to return LinkedIn search type
            agent.query_builder.build_firecrawl_parameters = MagicMock(return_value={
                "search_type": "linkedin_people",
                "direct_url": "https://www.linkedin.com/search/results/people/?keywords=CTO",
                "query": "CTO profiles",
                "reasoning": "LinkedIn search"
            })
            
            # Run search
            async with agent:
                results = await agent.search_and_fetch("CTO profiles", max_results=5)
                
            # Verify flow
            # 1. Should have called _fetch_linkedin_people_search
            # 2. Should have extracted URLs: john-doe and jane-smith
            # 3. Should have called batch_fetch for those URLs (in _fetch_with_crawl4ai)
            
            # Check if batch_fetch was called with extracted URLs
            # First call was for search page
            # Second call should be for profiles
            assert mock_c4_instance.batch_fetch.call_count >= 2
            
            # Get arguments of the second call
            call_args = mock_c4_instance.batch_fetch.call_args_list[1]
            urls_fetched = call_args[0][0]
            
            assert "https://www.linkedin.com/in/john-doe" in urls_fetched
            assert "https://www.linkedin.com/in/jane-smith" in urls_fetched
