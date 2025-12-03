import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from agents.content_extractor import ContentExtractorAgent

async def verify_cleaning():
    print("Starting verification...")
    agent = ContentExtractorAgent()
    
    # Load mock profile
    mock_path = "tests/fixtures/sample_markdown/linkedin_profile_mock.md"
    if not os.path.exists(mock_path):
        print(f"Mock file not found at {mock_path}")
        return

    with open(mock_path, "r") as f:
        raw_markdown = f.read()
        
    print(f"Original size: {len(raw_markdown)} bytes")
    
    # Test cleaning
    cleaned = agent._extract_linkedin_sections(raw_markdown)
    
    print(f"Cleaned size: {len(cleaned)} bytes")
    print("-" * 50)
    print("CLEANED CONTENT PREVIEW:")
    print("-" * 50)
    print(cleaned[:2000]) # Print first 2000 chars
    print("-" * 50)
    
    # Validation
    if len(cleaned) < len(raw_markdown) * 0.5:
        print("SUCCESS: Significant size reduction achieved")
    else:
        print("WARNING: Size reduction might not be sufficient")
        
    if "HEADER:" in cleaned and "EXPERIENCE:" in cleaned:
        print("SUCCESS: Sections detected")
    else:
        print("FAILURE: Missing expected sections")

if __name__ == "__main__":
    asyncio.run(verify_cleaning())
