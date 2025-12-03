import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.email_discovery_agent import EmailDiscoveryAgent
from models.lead import LeadProfile

@pytest.fixture
def mock_settings():
    return {
        "models": {"enricher": "mock-model"},
        "email_discovery": {
            "enabled_layers": [1, 2, 3, 4],
            "layers": {}
        },
        "linkedin": {"auth_enabled": True}
    }

@pytest.fixture
def agent(mock_settings):
    return EmailDiscoveryAgent(mock_settings)

@pytest.mark.asyncio
async def test_layer_1_cached_email(agent):
    """Test Layer 1 uses cached email from metadata."""
    lead = LeadProfile(
        name="Test User",
        company="Test Corp",
        linkedin="https://linkedin.com/in/test",
        metadata={"all_emails": ["cached@example.com"]}
    )
    
    email, meta = await agent.discover_email(lead)
    
    assert email == "cached@example.com"
    assert meta["source"] == "linkedin_contact"
    assert meta["layer"] == 1
    assert meta["confidence"] == 0.9

@pytest.mark.asyncio
async def test_layer_2_cached_email(agent):
    """Test Layer 2 uses cached email from metadata."""
    lead = LeadProfile(
        name="Test User",
        company="Test Corp",
        linkedin="https://linkedin.com/in/test",
        metadata={"profile_emails": ["profile@example.com"]}
    )
    
    # Disable Layer 1 to force Layer 2
    agent.enabled_layers = [2]
    
    email, meta = await agent.discover_email(lead)
    
    assert email == "profile@example.com"
    assert meta["source"] == "linkedin_profile"
    assert meta["layer"] == 2
    assert meta["confidence"] == 0.8

@pytest.mark.asyncio
async def test_layer_4_pattern_generation(agent):
    """Test Layer 4 generates email pattern."""
    lead = LeadProfile(
        name="John Doe",
        company="Test Corp",
        company_domain="testcorp.com"
    )
    
    # Disable Layers 1-3
    agent.enabled_layers = [4]
    
    email, meta = await agent.discover_email(lead)
    
    assert email == "john.doe@testcorp.com"
    assert meta["source"] == "pattern_generated"
    assert meta["layer"] == 4
    assert meta["confidence"] == 0.3
    assert "warning" in meta

@pytest.mark.asyncio
async def test_all_layers_fail(agent):
    """Test behavior when all layers fail."""
    lead = LeadProfile(
        name="John Doe",
        company="Test Corp",
        company_domain="testcorp.com",
        linkedin="https://linkedin.com/in/test"
    )
    
    # Mock methods to return failure using patch on the class
    with patch('agents.email_discovery_agent.EmailDiscoveryAgent._discover_from_linkedin_contact', new_callable=AsyncMock) as m1, \
         patch('agents.email_discovery_agent.EmailDiscoveryAgent._discover_from_linkedin_profile_content', new_callable=MagicMock) as m2, \
         patch('agents.email_discovery_agent.EmailDiscoveryAgent._discover_from_company_website', new_callable=AsyncMock) as m3, \
         patch('agents.email_discovery_agent.EmailDiscoveryAgent._discover_via_pattern_generation', new_callable=MagicMock) as m4:
        
        m1.return_value = {"status": "failed"}
        m2.return_value = {"status": "failed"}
        m3.return_value = {"status": "failed"}
        m4.return_value = {"status": "failed"}
        
        email, meta = await agent.discover_email(lead)
        
        assert email is None
        assert meta["status"] == "failed"
        assert meta["reason"] == "all_layers_exhausted"
