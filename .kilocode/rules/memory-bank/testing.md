# Testing Principles

## Core Philosophy
- **No Mocks**: All tests must execute against actual implementations that will run in production.
- **Real Dependencies**: Use real Crawl4AI, Firecrawl API calls, Ollama models, and file I/O in tests.
- **Live Validation**: Tests should validate actual behavior, not simulated responses.

## Testing Strategy

### Unit Tests
- Test individual agent functions with real API calls (rate-limited/throttled as needed).
- Validate actual LLM outputs against expected schemas (Pydantic models).
- Use real markdown/HTML samples from target domains.

### Integration Tests
- Full pipeline tests: Firecrawl search → Crawl4AI fetch → LLM extraction → validation.
- Test fallback mechanisms with actual failure scenarios (e.g., blocked URLs triggering Firecrawl).
- Validate JSON artifact persistence and state recovery.

### End-to-End Tests
- Complete lead generation workflow from query to validated output.
- Real URL targets (use staging/test domains where possible).
- Measure actual performance metrics (latency, token usage, accuracy).

## Test Requirements

### Environment
- All tests run in isolated environments with access to:
  - Ollama instance (local or cloud)
  - Firecrawl API key (test account)
  - Crawl4AI dependencies
- Use `.env.test` for test-specific configurations.

### Data
- Real sample URLs and expected outputs in `tests/fixtures/`.
- No synthetic/mocked HTML; use archived real pages.
- Maintain ground truth datasets for lead extraction validation.

### Assertions
- Schema validation: All outputs must conform to Pydantic models.
- Business logic: Validate email formats, phone number normalization, LinkedIn URL patterns.
- Performance: Assert maximum latency thresholds for each agent.

## Test Structure

