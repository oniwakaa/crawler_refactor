import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from tools.firecrawl_client import FirecrawlClient, FIRECRAWL_SEARCH_SCHEMA, LINKEDIN_SEARCH_LIMIT
import jsonschema

@pytest.fixture
def mock_client():
    client = FirecrawlClient(api_key="test_key")
    # Mock the internal HTTP client
    client.client = AsyncMock()
    return client

@pytest.mark.asyncio
async def test_schema_validation(mock_client):
    # Valid payload
    valid_payload = {
        "query": "test query",
        "limit": 5,
        "lang": "en",
        "scrapeOptions": {"formats": ["markdown"]}
    }
    assert mock_client.validate_search_params(valid_payload) == valid_payload

    # Invalid payload - missing query
    invalid_payload = {"limit": 5}
    with pytest.raises(ValueError):
        mock_client.validate_search_params(invalid_payload)

    # Invalid payload - wrong type
    invalid_type = {"query": "test", "limit": "five"}
    with pytest.raises(jsonschema.ValidationError):
        mock_client.validate_search_params(invalid_type)

def test_url_normalization(mock_client):
    # Valid cases
    assert mock_client._normalize_linkedin_url("https://www.linkedin.com/in/johndoe") == "https://www.linkedin.com/in/johndoe"
    assert mock_client._normalize_linkedin_url("https://linkedin.com/in/johndoe") == "https://www.linkedin.com/in/johndoe"
    assert mock_client._normalize_linkedin_url("http://www.linkedin.com/in/johndoe") == "https://www.linkedin.com/in/johndoe"
    assert mock_client._normalize_linkedin_url("https://www.linkedin.com/in/johndoe/") == "https://www.linkedin.com/in/johndoe"
    assert mock_client._normalize_linkedin_url("https://www.linkedin.com/in/johndoe?originalSubdomain=it") == "https://www.linkedin.com/in/johndoe"

    # Invalid cases
    assert mock_client._normalize_linkedin_url("https://www.linkedin.com/company/google") is None # Company page
    assert mock_client._normalize_linkedin_url("https://www.google.com/in/johndoe") is None # Wrong domain
    assert mock_client._normalize_linkedin_url("https://www.linkedin.com/jobs/view/123") is None # Job page
    assert mock_client._normalize_linkedin_url(None) is None

@pytest.mark.asyncio
async def test_discover_linkedin_profiles_flow(mock_client):
    # Mock search results for 3 steps
    
    # Step 1: Broad (Role + Location)
    # Returns 2 good URLs, 1 bad
    step1_results = [
        "https://www.linkedin.com/in/person1",
        "https://www.linkedin.com/in/person2",
        "https://www.linkedin.com/company/badresult"
    ]
    
    # Step 2: Specific (Skills)
    # Returns 1 known URL, 1 new good URL
    step2_results = [
        "https://www.linkedin.com/in/person1?ref=search", # Duplicate of person1
        "https://www.linkedin.com/in/person3"
    ]
    
    # Step 3: Exclusions/Synonyms
    # Returns 1 new good URL
    step3_results = [
        "https://www.linkedin.com/in/person4/"
    ]
    
    # Mock the search method
    # We need to act based on the query to return correct results
    async def side_effect(query, max_results=5, **kwargs):
        if "site:linkedin.com/in/" not in query:
            return []
            
        print(f"Mock Search Query: {query}, Limit: {max_results}")
            
        if "Python" in query: # Skill keyword used in test
            return step2_results
        elif "-recruiter" in query: # Exclusion keyword used in test
            return step3_results
        else: # Broad search
            return step1_results
            
    mock_client.search = AsyncMock(side_effect=side_effect)
    
    # Run discovery (uses default limit LINKEDIN_SEARCH_LIMIT = 50)
    results = await mock_client.discover_linkedin_profiles(
        role="Software Engineer",
        location="Berlin",
        skills="Python",
        exclusions="-recruiter"
    )
    
    # Verify results
    # Should contain person1, person2, person3, person4
    # normalized: https://www.linkedin.com/in/personX
    
    expected = {
        "https://www.linkedin.com/in/person1",
        "https://www.linkedin.com/in/person2",
        "https://www.linkedin.com/in/person3",
        "https://www.linkedin.com/in/person4"
    }
    
    assert set(results) == expected
    assert len(results) == 4
    
    # Verify call count (should be 3)
    assert mock_client.search.call_count == 3
    
    # Verify limit was 50 for all calls
    for call in mock_client.search.call_args_list:
        assert call.kwargs['max_results'] == LINKEDIN_SEARCH_LIMIT
