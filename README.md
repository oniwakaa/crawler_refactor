# B2B Lead Generation Multi-Agent System

## Overview
This project implements a multi-agent system for B2B lead generation, leveraging AI agents to automate the process of finding, extracting, enriching, and validating business leads.

## Architecture
The system consists of the following agents:
- **Orchestrator**: Manages the overall workflow and coordinates other agents.
- **Web Navigator**: Searches and navigates the web to find relevant sources.
- **Content Extractor**: Extracts structured data from web pages.
- **Lead Enricher**: Enriches lead data with additional information.
- **Validator**: Validates the quality and accuracy of the leads.

## Setup

### Prerequisites
- Python 3.10+
- `pip`

### Installation
1. Clone the repository.
2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   - Copy `.env.template` to `.env`
   - Fill in your API keys.

## Usage
Run the main pipeline:
```bash
python pipelines/b2b_lead_pipeline.py
```

## Testing
Run tests using pytest:
```bash
pytest tests/
```

## Agents
See `AGENTS.md` for detailed agent documentation.
