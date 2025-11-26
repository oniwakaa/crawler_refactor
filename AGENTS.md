# Agent System Documentation

## Overview
This project implements a multi-agent system for B2B lead generation using Agno framework, Crawl4AI, Firecrawl, and Ollama LLMs.

## Agent Team

### 1. Orchestrator Agent
**Model**: Ollama `gpt-oss:120b-cloud`  
**Role**: Task decomposition, strategy planning, workflow routing  
**Responsibilities**:
- Parse user queries into actionable search strategies
- Decompose complex requests into agent-specific subtasks
- Route tasks to appropriate specialized agents
- Aggregate final results and handle error recovery

**Key Functions**:
- `decompose_query(user_input: str) -> TaskPlan`
- `route_task(task: Task) -> Agent`
- `aggregate_results(agent_outputs: List[Dict]) -> LeadBatch`

---

### 2. Web Navigator Agent
**Model**: N/A (API-driven: Firecrawl + Crawl4AI)  
**Role**: Web search and content fetching  
**Responsibilities**:
- Execute search queries via Firecrawl API
- Collect relevant URLs matching lead criteria
- Batch-fetch page content using Crawl4AI (headless)
- Trigger fallback to Firecrawl for bulk/directory scraping

**Key Functions**:
- `search_web(query: str, max_results: int) -> List[str]`
- `batch_fetch_content(urls: List[str]) -> List[PageContent]`
- `fallback_scrape(urls: List[str]) -> List[Markdown]`

---

### 3. Content Extractor Agent
**Model**: Ollama `gpt-oss:20b-cloud` (mid-complexity)  
**Role**: Structured data extraction from markdown/HTML  
**Responsibilities**:
- Parse markdown into structured lead entities (Pydantic schemas)
- Extract: Name, Role, LinkedIn, Company, Domain, Email, Phone
- Handle partial/missing data gracefully
- Tag extraction confidence scores

**Key Functions**:
- `extract_entities(markdown: str, schema: Type[BaseModel]) -> Dict`
- `parse_contact_info(text: str) -> ContactInfo`
- `confidence_score(extraction: Dict) -> float`

---

### 4. Lead Enricher Agent
**Model**: Ollama `hf.co/unsloth/SmolLM3-3B-GGUF:Q4_K_M` (specialized, low-complexity)  
**Role**: Data enrichment and inference  
**Responsibilities**:
- Infer missing fields (e.g., domain from company name)
- Deduplicate leads across batches
- Enrich with public data sources (LinkedIn profiles, company websites)
- Normalize variations (company name standardization)

**Key Functions**:
- `infer_domain(company_name: str) -> str`
- `deduplicate_leads(leads: List[Lead]) -> List[Lead]`
- `enrich_from_linkedin(profile_url: str) -> Dict`

---

### 5. Validator & Normalizer Agent
**Model**: Ollama `hf.co/unsloth/SmolLM3-3B-GGUF:Q4_K_M` + Regex/Validators  
**Role**: Final validation and quality assurance  
**Responsibilities**:
- Validate email formats, phone number formats (international)
- Normalize data (capitalization, whitespace, URL formats)
- Flag low-confidence or incomplete leads
- Generate final quality score

**Key Functions**:
- `validate_email(email: str) -> bool`
- `normalize_phone(phone: str, country: str) -> str`
- `validate_schema(lead: Lead) -> ValidationResult`
- `quality_score(lead: Lead) -> float`

---

## Agent Communication

### Shared Memory/Artifact Store
All agents communicate through a centralized artifact store (JSON-based):
- **Location**: `artifacts/` directory
- **Format**: Structured JSON with metadata (timestamp, agent, status, provenance)
- **Persistence**: All intermediate results saved for debugging/recovery

### Message Protocol
