import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.content_extractor import ContentExtractorAgent
from agents.email_discovery_agent import EmailDiscoveryAgent
from models.lead import LeadProfile

@pytest.mark.asyncio
class TestMultiLayerEmailDiscovery:
    """Integration tests for multi-layer email discovery."""

    async def test_layer_2_integration(self):
        """
        Verify that ContentExtractor extracts emails from profile content
        and EmailDiscoveryAgent uses them (Layer 2).
        """
        # Setup ContentExtractor
        extractor = ContentExtractorAgent()
        
        # Setup EmailDiscoveryAgent
        settings = {
            "models": {"enricher": "mock-model"},
            "email_discovery": {"enabled_layers": [1, 2, 3, 4]},
            "linkedin": {"auth_enabled": True}
        }
        discovery_agent = EmailDiscoveryAgent(settings)
        
        # Mock LlamaWrapper for ContentExtractor
        extractor.llama_wrapper = MagicMock()
        extractor.llama_wrapper.structured_extract = AsyncMock(return_value=LeadProfile(
            name="Test User",
            company="Test Corp",
            linkedin="https://linkedin.com/in/test"
        ))
        
        # Mock dependencies for EmailDiscoveryAgent
        discovery_agent.crawl4ai_client = AsyncMock()
        discovery_agent.firecrawl_client = AsyncMock()
        discovery_agent.llama_wrapper = MagicMock()
        
        # Input data
        markdown = """
        # Test User
        Software Engineer at Test Corp
        
        Contact: test.user@testcorp.com
        """
        url = "https://linkedin.com/in/test"
        
        # 1. Run ContentExtractor
        # We mock _scrape_linkedin_contact_info to avoid network calls
        with patch.object(extractor, '_scrape_linkedin_contact_info', new_callable=AsyncMock) as mock_scrape:
            lead = await extractor.extract_entities(markdown, LeadProfile, url)
            
            # Verify ContentExtractor extracted email from markdown
            assert lead is not None
            assert lead.metadata is not None
            assert "profile_emails" in lead.metadata
            assert "test.user@testcorp.com" in lead.metadata["profile_emails"]
            
        # 2. Run EmailDiscoveryAgent
        # We mock Layer 1 to fail so it falls through to Layer 2
        with patch.object(discovery_agent, '_discover_from_linkedin_contact', return_value={"status": "failed"}):
            email, meta = await discovery_agent.discover_email(lead)
            
            # Verify EmailDiscoveryAgent used the cached email
            assert email == "test.user@testcorp.com"
            assert meta["source"] == "linkedin_profile"
            assert meta["layer"] == 2
            assert meta["status"] == "success"
