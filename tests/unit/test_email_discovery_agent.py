import pytest
from unittest.mock import AsyncMock, MagicMock
from agents.email_discovery_agent import EmailDiscoveryAgent, EmailMatchModel
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
    return EmailDiscoveryAgent(mock_settings)

@pytest.mark.asyncio
async def test_discover_email_success(agent):
    # Mock clients
    agent.llama_wrapper = AsyncMock()
    
    # Note: In actual implementation, firecrawl_client is used for domain searches
    agent.firecrawl_client = AsyncMock()
    agent.firecrawl_client.search.return_value = []
    
    # Mock scrape results
    # Mock firecrawl batch scrape
    agent.firecrawl_client.batch_scrape.return_value = [
        {
            "metadata": {"sourceURL": "http://acme.com"},
            "markdown": "Contact us at info@acme.com or john.doe@acme.com"
        }
    ]

    
    # Mock matching
    mock_match = EmailMatchModel(
        email="john.doe@acme.com",
        confidence_score=0.9,
        reasoning="Exact name match"
    )
    agent.llama_wrapper.structured_extract.return_value = mock_match
    
    # Test lead
    lead = LeadProfile(
        name="John Doe",
        company="Acme Corp",
        role="CEO",
        company_domain="acme.com"
    )
    
    # Run
    email, metadata = await agent.discover_email(lead)
    
    # Verify
    assert email == "john.doe@acme.com"
    assert metadata["status"] == "success"

@pytest.mark.asyncio
async def test_discover_email_no_domain(agent):
    lead = LeadProfile(name="Test", company="Test", role="Test")
    email, metadata = await agent.discover_email(lead)
    
    assert email is None
    assert metadata["reason"] == "all_layers_exhausted"

@pytest.mark.asyncio
async def test_discover_email_no_emails_found(agent):
    agent.firecrawl_client = AsyncMock()
    agent.firecrawl_client.search.return_value = []
    agent.firecrawl_client.batch_scrape.return_value = [
        {"metadata": {"sourceURL": "test.com"}, "markdown": "No emails here"}
    ]
    
    lead = LeadProfile(
        name="Test", 
        company="Test", 
        role="Test", 
        company_domain="test.com"
    )
    
    email, metadata = await agent.discover_email(lead)
    
    assert email is None
    assert metadata["reason"] == "all_layers_exhausted"

@pytest.mark.asyncio
async def test_discover_email_low_confidence(agent):
    """Test that emails with confidence < 0.3 are rejected and falls through without pattern generation"""
    # Disable layer 4 to prevent pattern generation
    agent.enabled_layers = [1, 2, 3]
    
    agent.firecrawl_client = AsyncMock()
    agent.firecrawl_client.search.return_value = []
    agent.llama_wrapper = AsyncMock()
    
    agent.firecrawl_client.batch_scrape.return_value = [
        {"metadata": {"sourceURL": "acme.com"}, "markdown": "info@acme.com"}
    ]
    
    # Use confidence < 0.3 to test rejection
    mock_match = EmailMatchModel(
        email="info@acme.com",
        confidence_score=0.25,  # Below threshold
        reasoning="Generic email"
    )
    agent.llama_wrapper.structured_extract.return_value = mock_match
    
    lead = LeadProfile(
        name="John Doe", 
        company="Acme Corp", 
        role="CEO", 
        company_domain="acme.com"
    )
    
    email, metadata = await agent.discover_email(lead)
    
    assert email is None
    assert metadata["reason"] == "all_layers_exhausted"
