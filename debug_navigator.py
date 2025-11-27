import asyncio
import os
import structlog
from dotenv import load_dotenv
from agents.web_navigator import WebNavigatorAgent

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

async def main():
    load_dotenv()
    api_key = os.getenv("FIRECRAWL_API_KEY")
    print(f"API Key present: {bool(api_key)}")
    
    from tools.firecrawl_client import FirecrawlClient
    
    async with FirecrawlClient(api_key=api_key) as client:
        query = "AI startups in San Francisco"
        print(f"Searching for: {query}")
        
    import httpx
    import json
    
    async with httpx.AsyncClient() as http_client:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        # Test 1: formats as list of strings (Current implementation)
        print("\n--- Test 1: formats=['markdown'] ---")
        payload1 = {
            "query": query,
            "limit": 2,
            "scrapeOptions": {"formats": ["markdown"]}
        }
        response1 = await http_client.post("https://api.firecrawl.dev/v2/search", json=payload1, headers=headers)
        print(f"Status: {response1.status_code}")
        print(f"Response: {response1.text[:200]}...")

        # Test 2: formats as list of objects (Documentation hint)
        print("\n--- Test 2: formats=[{'type': 'markdown'}] ---")
        payload2 = {
            "query": query,
            "limit": 2,
            "scrapeOptions": {"formats": ["markdown"]}  # Wait, doc said [{"type": "markdown"}] but let's try that
        }
        # Actually let's try the object format
        payload3 = {
            "query": query,
            "limit": 2,
            "scrapeOptions": {"formats": [{"type": "markdown"}]}
        }
        
        # Test 3: No scrapeOptions (Basic search)
        print("\n--- Test 3: No scrapeOptions ---")
        payload4 = {
            "query": query,
            "limit": 2,
        }
        response4 = await http_client.post("https://api.firecrawl.dev/v2/search", json=payload4, headers=headers)
        print(f"Status: {response4.status_code}")
        print(f"Response: {response4.text[:200]}...")

if __name__ == "__main__":
    asyncio.run(main())
