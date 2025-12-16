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
    agent.llama_wrapper = AsyncMock()
    
    # Setup mock returns
    # Setup mock returns
    # No longer needed as we expect skip

    
    # Test lead
    lead = LeadProfile(
        name="Test User",
        company="Unknown",
        role="Unknown",
        linkedin="https://linkedin.com/in/test"
    )
    
    # Run enrichment
    enriched_lead, metadata = await agent.enrich_from_linkedin_profile(lead)
    
    # Verify - Agent should skip re-scraping
    assert enriched_lead == lead
    assert metadata["status"] == "skipped"
    assert metadata["reason"] == "already_scraped_by_apify"

@pytest.mark.asyncio
async def test_enrich_no_linkedin(agent):
    lead = LeadProfile(name="Test", company="Test", role="Test")
    enriched_lead, metadata = await agent.enrich_from_linkedin_profile(lead)
    
    assert enriched_lead == lead
    assert metadata["status"] == "skipped"
