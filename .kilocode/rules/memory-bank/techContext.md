Technical Stack

- Python 3.11+, agno-ai>=0.6.*, crawl4ai>=0.1.*, firecrawl-api>=0.2.*, llama-cpp-python, pydantic, httpx, typer, pytest
- LLMs with Ollama: Main agent – gpt-oss:120b-cloud, Mid-complexity – gpt-oss:20b-cloud, Specialized (low complexity) – hf.co/unsloth/SmolLM3-3B-GGUF:Q4_K_M
- Output schema: Lead (Name, Role, LinkedIn, Company, Company Domain, Email, Phone Number)
