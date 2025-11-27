Technical Stack

- Python 3.11+, agno-ai>=0.6.*, crawl4ai>=0.1.*, firecrawl-api>=0.2.*, llama-cpp-python, pydantic, httpx, typer, pytest
- LLMs with Ollama: Main agent – gpt-oss:120b-cloud, Mid-complexity – gpt-oss:20b-cloud, Specialized (low complexity) – hf.co/unsloth/SmolLM3-3B-GGUF:Q4_K_M
- Output schema: Lead (Name, Role, LinkedIn, Company, Company Domain, Email, Phone Number)

## Current Implementation Status

- All dependencies installed and verified working
- Test suite operational:
  - Unit tests: tests/unit/ (passing)
  - Integration tests: tests/integration/ (passing)
  - E2E tests: tests/e2e/ (passing)
- Coverage metrics:
  - tools/firecrawl_client.py: 69%
  - tools/crawl4ai_client.py: 77%
  - tools/llama_wrapper.py: 64%
  - Overall: 54%
- API integrations verified:
  - Firecrawl v2 Search API: functional
  - Crawl4AI AsyncWebCrawler: functional
  - Ollama cloud models: functional
  - Local GGUF models: functional

## Known Working Configurations

- Firecrawl API: v2 endpoints, scrapeOptions format
- Crawl4AI: AsyncWebCrawler with BrowserConfig (headless mode)
- Ollama: Both cloud (gpt-oss:120b-cloud, gpt-oss:20b-cloud) and local (SmolLM3-3B-GGUF) models
- Phone validation: Accepts various formats with region detection
- JSON serialization: Datetime exclusion implemented
