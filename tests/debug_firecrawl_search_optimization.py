import asyncio
import os
import structlog
from tools.firecrawl_client import FirecrawlClient
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger()

async def test_search_formats():
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print("No API key found")
        return

    print("--- Testing default search ---")
    async with FirecrawlClient(api_key=api_key) as client:
        # 1. Default (with markdown) - to see baseline
        try:
            print("1. Testing default (markdown)...")
            # We have to bypass the client.search method slightly to test raw payload changes if needed,
            # but first let's try to modify client.search to support custom scrapeOptions via kwargs if possible 
            # or just call _make_request directly.
            
            # Use _make_request to test raw payloads
            payload = {
                "query": "Sales managers at food companies Italy",
                "limit": 3,
                "sources": ["web"],
                "scrapeOptions": {"formats": ["markdown"]}
            }
            start = asyncio.get_event_loop().time()
            res = await client._make_request("POST", f"{client.base_url}/search", json=payload)
            duration = asyncio.get_event_loop().time() - start
            print(f"Default duration: {duration:.2f}s")
            data = res.get("data", [])
            if isinstance(data, dict): data = data.get("web", [])
            print(f"Result count: {len(data)}")
            if data:
                print(f"Keys in first result: {data[0].keys()}")
                if "markdown" in data[0]:
                    print(f"Markdown length: {len(data[0]['markdown'])}")

        except Exception as e:
            print(f"Default failed: {e}")

        # 2. Testing without scrapeOptions (if allowed)
        try:
            print("\n2. Testing without scrapeOptions...")
            payload = {
                "query": "Sales managers at food companies Italy",
                "limit": 3,
                "sources": ["web"],
                # "scrapeOptions": {} # omitted
            }
            start = asyncio.get_event_loop().time()
            res = await client._make_request("POST", f"{client.base_url}/search", json=payload)
            duration = asyncio.get_event_loop().time() - start
            print(f"No scrapeOptions duration: {duration:.2f}s")
            data = res.get("data", [])
            if isinstance(data, dict): data = data.get("web", [])
            print(f"Result count: {len(data)}")
            if data:
                print(f"Keys in first result: {data[0].keys()}")
        except Exception as e:
            print(f"No scrapeOptions failed: {e}")

        # 3. Testing formats=["link"] or similar if valid? 
        # Firecrawl generic search usually returns metadata.
        # Let's try explicit scrapeOptions={"formats": []} ?
        try:
            print("\n3. Testing empty formats list...")
            payload = {
                "query": "Sales managers at food companies Italy",
                "limit": 3,
                "sources": ["web"],
                "scrapeOptions": {"formats": []}
            }
            start = asyncio.get_event_loop().time()
            res = await client._make_request("POST", f"{client.base_url}/search", json=payload)
            duration = asyncio.get_event_loop().time() - start
            print(f"Empty formats duration: {duration:.2f}s")
            data = res.get("data", [])
            if isinstance(data, dict): data = data.get("web", [])
            if data:
                print(f"Keys in first result: {data[0].keys()}")
        except Exception as e:
            print(f"Empty formats failed: {e}")

    print("\n--- Testing client.search() default behavior ---")
    async with FirecrawlClient(api_key=api_key) as client:
        try:
            start = asyncio.get_event_loop().time()
            urls = await client.search("Sales managers at food companies Italy", max_results=3)
            duration = asyncio.get_event_loop().time() - start
            print(f"client.search duration: {duration:.2f}s")
            print(f"Result count: {len(urls)}")
            print(f"First result: {urls[0] if urls else 'None'}")
            print(f"Results are strings: {all(isinstance(u, str) for u in urls)}")
        except Exception as e:
            print(f"client.search failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_search_formats())
