# B2B Lead Generation Pipeline

> An autonomous agentic pipeline that discovers, scrapes, and enriches high-quality B2B leads from LinkedIn and the web using AI-powered extraction.

## Why B2B Lead Generation Pipeline?

Finding qualified B2B leads manually is time-consuming and error-prone. This pipeline automates the entire process: it takes a natural language query, discovers relevant LinkedIn profiles, extracts structured contact information, and enriches leads with verified emails and company domains—delivering actionable sales intelligence in minutes instead of hours.

## Features

- **Natural Language Queries**: Search for leads using plain English like "CTO at fintech startups Berlin"
- **Multi-Source Discovery**: Combines Firecrawl search with Apify LinkedIn scraping for comprehensive results
- **AI-Powered Extraction**: Uses local LLMs to extract structured data from unstructured profiles
- **Automatic Enrichment**: Discovers company domains and contact emails automatically
- **Deduplication**: Intelligently merges duplicate leads based on email, LinkedIn URL, or name+company
- **Confidence Scoring**: Each lead comes with a quality score to prioritize follow-ups
- **Resilient Processing**: Handles failures gracefully with partial saving and retry logic

## Prerequisites

- Python 3.11 or higher
- [Ollama](https://ollama.com/) running locally (port 11434)
- Firecrawl API Key — Get yours at [firecrawl.dev](https://firecrawl.dev)
- Apify API Token — Get yours at [apify.com](https://apify.com)
- Supabase Account — For data persistence (optional for CLI-only use)

**Note**: This project follows a "Bring Your Own Key" (BYOK) model. All API keys and credentials are provided by you at runtime—no secrets are hardcoded in the repository.

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/oniwakaa/crawler_refactor.git
   cd crawler_refactor
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your API keys:
   ```env
   FIRECRAWL_API_KEY=your_firecrawl_api_key_here
   APIFY_API_TOKEN=your_apify_api_token_here
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your_supabase_anon_key_here
   SUPABASE_SERVICE_KEY=your_supabase_service_key_here
   ```

5. **Configure settings (optional)**

   Edit `config/settings.yaml` to customize:
   - LinkedIn profile URL to exclude (avoids self-scraping)
   - Model preferences (orchestrator, extractor, enricher)
   - Crawling concurrency and timeouts

6. **Run your first search**
   ```bash
   python pipelines/b2b_lead_pipeline.py "Marketing Directors in SaaS Berlin" --max-results 10
   ```

## Configuration Reference

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `FIRECRAWL_API_KEY` | Firecrawl API key for web search | Yes | None |
| `APIFY_API_TOKEN` | Apify token for LinkedIn scraping | Yes | None |
| `SUPABASE_URL` | Supabase project URL | Backend only | None |
| `SUPABASE_ANON_KEY` | Supabase anonymous key | Backend only | None |
| `SUPABASE_SERVICE_KEY` | Supabase service role key | Backend only | None |
| `OLLAMA_HOST` | Ollama server URL | No | `http://localhost:11434` |
| `ORCHESTRATOR_MODEL` | Model for query planning | No | `gpt-oss:120b-cloud` |
| `EXTRACTOR_MODEL` | Model for data extraction | No | `gpt-oss:20b-cloud` |
| `ENRICHER_MODEL` | Model for lead enrichment | No | `gpt-oss:20b-cloud` |
| `ALLOWED_ORIGINS` | CORS allowed origins | Backend only | None |
| `CRAWL4AI_HEADLESS` | Run browser headless | No | `true` |
| `CRAWL4AI_TIMEOUT` | Browser timeout seconds | No | `30` |
| `LOG_LEVEL` | Logging verbosity | No | `INFO` |

## Usage Examples

### Basic Search
```bash
python pipelines/b2b_lead_pipeline.py "CTO at fintech startups London"
```

### High Volume Search
Increase `max-results` for deeper discovery. The pipeline automatically fetches more candidates:
```bash
python pipelines/b2b_lead_pipeline.py "HR Managers in Germany" --max-results 50
```

### Custom Configuration
```bash
python pipelines/b2b_lead_pipeline.py "Sales Directors in fintech" \
    --settings config/custom_settings.yaml \
    --output results/custom_lead_batch.json \
    --verbose
```

### Backend API

Start the FastAPI server:
```bash
uvicorn server.api:app --reload
```

Submit a search job:
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "VP Engineering at SaaS companies", "max_results": 20, "user_id": "user_123"}'
```

Check job status:
```bash
curl http://localhost:8000/jobs/{job_id}
```

## Architecture

The pipeline uses a modular agent architecture:

1. **OrchestratorAgent** — Decomposes natural language queries into search strategies
2. **WebNavigatorAgent** — Discovers LinkedIn profiles via Firecrawl + Apify
3. **ContentExtractorAgent** — Extracts structured data from profiles using LLM
4. **LeadEnricherAgent** — Coordinates enrichment (LinkedIn, domain, email)
5. **ValidatorAgent** — Validates and normalizes lead data

For detailed architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Troubleshooting

**"LinkedIn session invalid"**
- LinkedIn scraping uses Apify—a valid Apify token is all you need
- No LinkedIn session cookies required

**"No leads extracted"**
- Verify your search query returns results on LinkedIn directly
- Check that FIRECRAWL_API_KEY and APIFY_API_TOKEN are set correctly
- Review `artifacts/` for partial logs and error details

**"Ollama connection refused"**
- Ensure Ollama is running: `ollama serve`
- Verify the model is pulled: `ollama pull gpt-oss:120b-cloud`
- Check `OLLAMA_HOST` matches your Ollama server

**"Supabase connection failed"**
- Verify `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_KEY` are correct
- Ensure your Supabase project has the required tables (see `server/schema.sql`)

## Testing

Run the test suite:
```bash
# Unit tests
pytest tests/unit

# Integration tests (requires API keys)
pytest tests/integration
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

Please ensure all new code includes appropriate tests and follows the existing code style.

## Security Note

**Never commit API keys, tokens, or credentials to the repository.**

- Use `.env` for local development (already in `.gitignore`)
- Use `frontend/.env.local` for frontend development (already in `.gitignore`)
- Reference `.env.example` and `frontend/.env.example` for required variables
- For production deployments, use secure secret management (Azure Key Vault, AWS Secrets Manager, etc.)

## License

MIT License — See [LICENSE](LICENSE) for details.