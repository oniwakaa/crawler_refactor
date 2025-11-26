System Architecture

- Agent Team (Agno-based): Orchestrator (task, strategy), Web Navigator (Firecrawl + Crawl4AI), Content Extractor (Crawl4AI + LLM), Lead Enricher (SmolLM3/Qwen), Validator & Normalizer.
- Data Flow: Web search (Firecrawl) → Content fetching (Crawl4AI) → LLM parsing → Enrichment/validation with local agents.
- Key Patterns: Batch async orchestration, shared memory/artifact store, robust fallback with Firecrawl for bulk/directory/CAPTCHA, persistent JSON logging.
- Storage: No SQL DB required; use artifact store (JSON files).
- All agent communication and state updates are persisted in structured JSON (status, provenance).
