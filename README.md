# B2B Lead Generation Multi-Agent System

## Overview
This project implements a sophisticated multi-agent system for B2B lead generation. It leverages a combination of local LLMs (via Ollama) and powerful web scraping tools (Firecrawl, Crawl4AI) to automate the entire lead discovery pipeline:

1.  **Discovery**: Finding potential leads based on user queries.
2.  **Extraction**: Parsing structured data (names, emails, companies) from unstructured web content.
3.  **Enrichment**: Enhancing lead profiles with additional details (LinkedIn, company domains).
4.  **Validation**: Verifying contact information and data integrity.

## Repository Structure
```
.
├── agents/                 # AI Agents (Orchestrator, Web Navigator, Extractor, etc.)
├── config/                 # Configuration files (settings.yaml, prompts)
├── models/                 # Pydantic data models (Lead, Company, etc.)
├── pipelines/              # Execution pipelines (e.g., b2b_lead_pipeline.py)
├── tests/                  # Unit and integration tests
├── tools/                  # Tool wrappers (Llama, Firecrawl, Crawl4AI)
├── .env.template           # Template for environment variables
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Tools & Setup

### 1. Ollama (Local LLM)
The system uses Ollama to run LLMs locally for reasoning and extraction.
-   **Install Ollama**: Download from [ollama.com](https://ollama.com).
-   **Run Ollama**: Ensure the server is running:
    ```bash
    ollama serve
    ```
-   **Pull Models**: The system defaults to `gpt-oss:120b-cloud` and `gpt-oss:20b-cloud`. You may need to pull the specific models defined in `config/settings.yaml`.

### 2. Firecrawl (Web Search & Scraping)
Used for high-quality web search and scraping, especially when local methods fail.
-   **Get API Key**: Sign up at [firecrawl.dev](https://firecrawl.dev).
-   **Configure**: Add your API key to `.env`:
    ```env
    FIRECRAWL_API_KEY=your_api_key_here
    ```

### 3. Crawl4AI (Local Crawling)
A powerful local crawler used for efficient batch processing.
-   **Install**: Included in `requirements.txt`.
-   **Setup**: After installing dependencies, install the necessary browsers:
    ```bash
    playwright install
    ```

## Installation
1.  Clone the repository.
2.  Create a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    playwright install
    ```
4.  Setup Environment:
    -   Copy `.env.template` to `.env` (create it if missing).
    -   Add `FIRECRAWL_API_KEY` if using Firecrawl.
    -   Update `config/settings.yaml` with your preferred models and settings.

## Usage
Run the main B2B lead generation pipeline:
```bash
python pipelines/b2b_lead_pipeline.py
```

## Testing
Run tests using pytest:
```bash
pytest tests/
```

## Configuration & Optimization

### Firecrawl Search
The pipeline uses an optimized Firecrawl search configuration that requests only URLs (metadata) to minimize bandwidth and latency.
- **Search Mode**: URLs only (no markdown).
- **Performance**: ~0.8s response time (vs ~2s default).

### Enrichment Timeouts
Strict time budgets are enforced to keep pipeline execution efficient:
- **Domain Search**: 15s timeout.
- **Email Discovery**: 20s timeout.
- **LLM Inference**: 15s timeout.
- **Total Per Lead**: Target < 45s.
