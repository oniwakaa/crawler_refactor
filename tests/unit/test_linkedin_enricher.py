import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.linkedin_profile_enricher import LinkedInProfileEnricherAgent, LinkedInExtractionModel
from models.lead import LeadProfile

@pytest.fixture
def mock_settings():
    return {
        "models": {
            "enricher": "test-model",
            "ollama_host": "http://localhost:11434"
        }
    }

@pytest.fixture
def agent(mock_settings):
    return LinkedInProfileEnricherAgent(mock_settings)

@pytest.mark.asyncio
async def test_enrich_success(agent):
    # Mock clients
    agent.crawl4ai_client = AsyncMock()
    agent.llama_wrapper = AsyncMock()
    
    # Setup mock returns
    agent.crawl4ai_client.fetch_linkedin_profile.return_value = {
        "fetch_status": "success",
        "markdown": "Test Profile Content"
    }
    
    mock_extraction = LinkedInExtractionModel(
        name="Test User",
        company="Test Corp",
        role="Senior Tester",
        company_linkedin_url=None
    )
    agent.llama_wrapper.structured_extract.return_value = mock_extraction
    
    # Test lead
    lead = LeadProfile(
        name="Test User",
        company="Unknown",
        role="Unknown",
        linkedin="https://linkedin.com/in/test"
    )
    
    # Run enrichment
    enriched_lead, metadata = await agent.enrich_from_linkedin_profile(lead)
    
    # Verify
    assert enriched_lead.company == "Test Corp"
    assert enriched_lead.role == "Senior Tester"
    assert metadata["status"] == "success"
    assert "fetch" in metadata["stages"]
    assert "extraction" in metadata["stages"]

@pytest.mark.asyncio
async def test_enrich_no_linkedin(agent):
    lead = LeadProfile(name="Test", company="Test", role="Test")
    enriched_lead, metadata = await agent.enrich_from_linkedin_profile(lead)
    
    assert enriched_lead == lead
    assert metadata["status"] == "skipped"

@pytest.mark.asyncio
async def test_enrich_fetch_fail(agent):
    agent.crawl4ai_client = AsyncMock()
    agent.crawl4ai_client.fetch_linkedin_profile.return_value = {
        "fetch_status": "failed",
        "error": "Network error"
    }
    
    lead = LeadProfile(
        name="Test", 
        company="Test", 
        role="Test", 
        linkedin="https://linkedin.com/in/test"
    )
    
    enriched_lead, metadata = await agent.enrich_from_linkedin_profile(lead)
    
    assert enriched_lead == lead
    assert metadata["error"] == "Network error"

@pytest.mark.asyncio
async def test_enrich_extraction_fail(agent):
    agent.crawl4ai_client = AsyncMock()
    agent.llama_wrapper = AsyncMock()
    
    agent.crawl4ai_client.fetch_linkedin_profile.return_value = {
        "fetch_status": "success",
        "markdown": "Content"
    }
    
    agent.llama_wrapper.structured_extract.return_value = None
    
    lead = LeadProfile(
        name="Test", 
        company="Test", 
        role="Test", 
        linkedin="https://linkedin.com/in/test"
    )
    
    enriched_lead, metadata = await agent.enrich_from_linkedin_profile(lead)
    
    assert enriched_lead == lead
    assert metadata["extracted_data"] is None
