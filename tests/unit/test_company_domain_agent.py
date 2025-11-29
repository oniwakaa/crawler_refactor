import pytest
from unittest.mock import AsyncMock, MagicMock
from agents.company_domain_agent import CompanyDomainAgent, DomainValidationModel

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
    return CompanyDomainAgent(mock_settings)

@pytest.mark.asyncio
async def test_find_domain_success(agent):
    # Mock clients
    agent.firecrawl_client = AsyncMock()
    agent.llama_wrapper = AsyncMock()
    
    # Setup mock returns
    agent.firecrawl_client.search_for_domain.return_value = ["https://www.acme.com", "https://acme.org"]
    agent.firecrawl_client.fetch_homepage.return_value = {
        "markdown": "Welcome to Acme Corp official site.",
        "metadata": {"title": "Acme Corp"}
    }
    
    mock_validation = DomainValidationModel(
        confidence_score=0.95,
        reasoning="Exact match"
    )
    agent.llama_wrapper.structured_extract.return_value = mock_validation
    
    # Run
    domain, metadata = await agent.find_company_domain("Acme Corp")
    
    # Verify
    assert domain == "www.acme.com"
    assert metadata["status"] == "success"
    assert metadata["confidence"] == 0.95

@pytest.mark.asyncio
async def test_find_domain_no_results(agent):
    agent.firecrawl_client = AsyncMock()
    agent.firecrawl_client.search_for_domain.return_value = []
    
    domain, metadata = await agent.find_company_domain("Ghost Corp")
    
    assert domain is None
    assert metadata["reason"] == "no_search_results"

@pytest.mark.asyncio
async def test_find_domain_low_confidence(agent):
    agent.firecrawl_client = AsyncMock()
    agent.llama_wrapper = AsyncMock()
    
    agent.firecrawl_client.search_for_domain.return_value = ["https://directory.com/acme"]
    agent.firecrawl_client.fetch_homepage.return_value = {"markdown": "Directory listing"}
    
    mock_validation = DomainValidationModel(
        confidence_score=0.3,
        reasoning="Directory listing"
    )
    agent.llama_wrapper.structured_extract.return_value = mock_validation
    
    domain, metadata = await agent.find_company_domain("Acme Corp")
    
    assert domain is None
    assert metadata["reason"] == "low_confidence"

@pytest.mark.asyncio
async def test_invalid_company_name(agent):
    domain, metadata = await agent.find_company_domain("Unknown Company")
    assert domain is None
    assert metadata["status"] == "skipped"
