System Architecture

- Agent Team (Agno-based): Orchestrator (task, strategy), Web Navigator (Firecrawl + Crawl4AI), Content Extractor (Crawl4AI + LLM), Lead Enricher (SmolLM3/Qwen), Validator & Normalizer.
- Data Flow: Web search (Firecrawl) → Content fetching (Crawl4AI) → LLM parsing → Enrichment/validation with local agents.
- Key Patterns: Batch async orchestration, shared memory/artifact store, robust fallback with Firecrawl for bulk/directory/CAPTCHA, persistent JSON logging.
- Storage: No SQL DB required; use artifact store (JSON files).
- All agent communication and state updates are persisted in structured JSON (status, provenance).

## Implementation Status

### Completed Components

**Phase 1 - Data Models**: ✅ Complete
- models/lead.py: LeadProfile with full validation
- models/company.py: Company model

**Phase 2 - Tool Clients**: ✅ Complete
- tools/firecrawl_client.py: Search and batch scrape (v2 API)
- tools/crawl4ai_client.py: Async web crawling with fallback
- tools/llama_wrapper.py: Unified LLM interface (Ollama + llama-cpp-python)

**Phase 3 - Agent Classes**: ✅ Complete
- agents/orchestrator.py: Task decomposition and routing
- agents/web_navigator.py: Search + fetch with fallback logic
- agents/content_extractor.py: LLM-based entity extraction
- agents/lead_enricher.py: Field inference and deduplication
- agents/validator.py: Validation and normalization

**Phase 4 - Pipeline Integration**: ✅ Complete
- pipelines/b2b_lead_pipeline.py: Full workflow orchestration with CLI

**Phase 5 - Configuration**: ✅ Complete
- config/prompts/: All prompt templates created
- config/settings.yaml: Complete configuration
- Artifact persistence: Working

**Testing Phase**: ✅ Complete
- Test suite operational (unit, integration, E2E)
- 54% coverage across core modules

## Verified Data Flow

1. User query → Orchestrator (decompose_query)
2. TaskPlan → WebNavigator (search via Firecrawl → fetch via Crawl4AI with Firecrawl fallback)
3. Pages → ContentExtractor (LLM extraction using gpt-oss:20b-cloud)
4. Raw leads → LeadEnricher (inference using SmolLM3-3B-GGUF + deduplication)
5. Enriched leads → Validator (validation + normalization using SmolLM3-3B-GGUF)
6. Valid leads → Orchestrator (aggregation) → LeadBatch output

All steps persist artifacts to artifacts/ directory with timestamps and provenance.

## Production Readiness

- Core functionality: ✅ Verified
- Error handling: ✅ Implemented throughout
- Fallback mechanisms: ✅ Tested (Crawl4AI → Firecrawl, cloud → local models)
- Logging: ✅ Structured logging with context
- Testing: ⚠️ Needs coverage improvement (54% → 70%+)
- Deployment: ❌ Not yet configured
- Monitoring: ❌ Not yet implemented
