import asyncio
import structlog
import yaml
from models.lead import LeadProfile
from agents.linkedin_profile_enricher import LinkedInProfileEnricherAgent

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ]
)

async def test_enrichment():
    # Load settings
    with open("config/settings.yaml", "r") as f:
        settings = yaml.safe_load(f)
        
    # Create test lead
    lead = LeadProfile(
        name="Test User",
        company="Unknown Company",
        role="Unknown Role",
        linkedin="https://www.linkedin.com/in/williamhgates" # Bill Gates as test case
    )
    
    print(f"Original Lead: {lead.name}, {lead.company}, {lead.role}")
    
    async with LinkedInProfileEnricherAgent(settings) as agent:
        enriched_lead, metadata = await agent.enrich_from_linkedin_profile(lead)
        
        print("\n--- Enrichment Results ---")
        print(f"Enriched Lead: {enriched_lead.name}")
        print(f"Company: {enriched_lead.company}")
        print(f"Role: {enriched_lead.role}")
        print(f"Confidence: {enriched_lead.confidence_score}")
        print(f"Metadata Status: {metadata.get('status')}")
        if metadata.get('error'):
            print(f"Error: {metadata.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_enrichment())
