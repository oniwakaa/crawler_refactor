# B2B Lead Generation Pipeline

> An autonomous agentic pipeline for discovering, scraping, and enriching high-quality B2B leads from LinkedIn and the web.

**Current Version:** 2.0 (Refactor)
**Status:** 🟢 Active / Testing

## 🚀 Project Overview

This pipeline automates the process of finding business professionals. It takes a natural language query (e.g., *"Sales Managers in Italian food companies"*), discovers relevant LinkedIn profiles using Firecrawl, scrapes them using an authenticated browser, extracts structured data using local LLMs, and enriches the leads with emails and domains.

**Key Capabilities:**
- **Smart Discovery:** Uses a 3-step search strategy to find diverse profiles.
- **Deep Extraction:** Parses LinkedIn profiles to extract experience, role, and company.
- **Enrichment:** Automatically discovers company domains and contact emails.
- **Resilience:** robust error handling, anti-detection, and partial saving.

---

## ⚡ Quick Start

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/) running locally (port 11434)
- Firecrawl API Key
- A valid LinkedIn account (for authenticated scraping)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/oniwakaa/crawler_refactor.git
    cd crawler_refactor
    ```

2.  **Install dependencies:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    playwright install chromium
    ```

3.  **Configure Environment:**
    Create a `.env` file:
    ```bash
    FIRECRAWL_API_KEY=your_key_here
    ```

4.  **Configure Settings:**
    Edit `config/settings.yaml` to set your LinkedIn profile URL (to avoid self-scraping) and adjust model preferences.

### First Run

Run the pipeline with a simple query:

```bash
python pipelines/b2b_lead_pipeline.py "Marketing Directors in SaaS Berlin" --max-results 10
```

### Expected Output
The pipeline will log its progress and save the final result to the `artifacts/` directory:
- `artifacts/pipeline_{timestamp}_complete.json`

---

## 📖 Usage Examples

### Basic Search
```bash
python pipelines/b2b_lead_pipeline.py "CTO at fintech startups London"
```

### High Volume Search (Deep Discovery)
Increase `max-results` to process more leads. The discovery phase will automatically fetch more candidates.
```bash
python pipelines/b2b_lead_pipeline.py "HR Managers in Germany" --max-results 50
```

### Verbose Mode (Debugging)
See detailed logs about every decision the agents make.
```bash
python pipelines/b2b_lead_pipeline.py "Leads request" -v
```

---

## 🔧 Configuration Summary

The `config/settings.yaml` file is the central control panel.

| Setting | Default | Description |
| :--- | :--- | :--- |
| `crawling.max_concurrent` | `10` | Number of simultaneous browser tabs. |
| `linkedin.auth_enabled` | `true` | Whether to use your session cookie. |
| `extraction.confidence_threshold` | `0.5` | Minimum score to consider a lead valid. |
| `models.orchestrator` | `gpt-oss:120b-cloud` | LLM used for planning. |

*See [ARCHITECTURE.md](ARCHITECTURE.md) for full configuration details.*

---

## 🛠️ Troubleshooting

**Common Issues:**

1.  **"LinkedIn session invalid"**:
    - Your cookie might have expired.
    - Run `python scripts/setup_linkedin_auth.py` (if available) or update `.auth/storage_states/*.json` manually.

2.  **"No leads extracted"**:
    - Check if the search query is returning results manually.
    - Verify Firecrawl API key is active.
    - Check `artifacts/` for partial logs.

3.  **"Ollama connection refused"**:
    - Ensure Ollama is running (`ollama serve`).

**Logs:**
Logs are printed to stdout. Use `-v` for detailed debug information.

---

## 📚 Documentation

For a deep dive into the system architecture, component interactions, and data flow, please refer to:

👉 **[ARCHITECTURE.md](ARCHITECTURE.md)**

---

## 🧪 Testing

Run the test suite to verify system integrity:

```bash
# Run unit tests
pytest tests/unit

# Run integration tests (requires API keys)
pytest tests/integration
```
