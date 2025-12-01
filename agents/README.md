# Agents Documentation

This directory contains the autonomous agents that power the lead generation and crawling system. Each agent has a specific responsibility and interacts with others to discover, extract, enrich, and validate lead data.

## Agents and Roles

### Core Agents

1.  **OrchestratorAgent** (`orchestrator.py`)
    *   **Role**: The central coordinator of the system. It acts as the "brain" that manages the entire lifecycle of a user request.
    *   **Responsibilities**:
        *   Decomposes natural language user queries into actionable `TaskPlan`s.
        *   Routes tasks to appropriate sub-agents based on the current state.
        *   Aggregates results from multiple agents into a final `LeadBatch`.
        *   Manages shared state and artifacts.

2.  **LeadEnricherAgent** (`lead_enricher.py`)
    *   **Role**: Manages the enrichment pipeline to enhance lead data quality and completeness.
    *   **Responsibilities**:
        *   Coordinates specialized enrichment sub-agents (LinkedIn, Domain, Email).
        *   Infers missing fields using LLM-based logic.
        *   Deduplicates leads based on email, LinkedIn URL, or name/company combinations.

### specialized Agents

3.  **WebNavigatorAgent** (`web_navigator.py`)
    *   **Role**: Responsible for exploring the web to find relevant content.
    *   **Responsibilities**:
        *   Executes search queries using Firecrawl.
        *   Fetches web page content using Crawl4AI (primary) with Firecrawl fallback.
        *   Optimizes search queries to target leads and exclude irrelevant pages (via `QueryBuilderAgent`).

4.  **ContentExtractorAgent** (`content_extractor.py`)
    *   **Role**: Extracts structured data from unstructured web content.
    *   **Responsibilities**:
        *   Detects content type (Profile, Team Page, Article, etc.).
        *   Uses LLM-based extraction with content-aware prompts.
        *   Calculates confidence scores for extracted data.

5.  **CompanyDomainAgent** (`company_domain_agent.py`)
    *   **Role**: Discovers the official website for a given company name.
    *   **Responsibilities**:
        *   Searches for company domains.
        *   Validates found domains against the company name using LLM.

6.  **EmailDiscoveryAgent** (`email_discovery_agent.py`)
    *   **Role**: Finds contact information for a lead.
    *   **Responsibilities**:
        *   Identifies contact pages on a company domain.
        *   Scrapes pages for email addresses and phone numbers.
        *   Matches discovered emails to the specific lead using LLM logic.

7.  **LinkedInProfileEnricherAgent** (`linkedin_profile_enricher.py`)
    *   **Role**: Enriches lead profiles using LinkedIn data.
    *   **Responsibilities**:
        *   Fetches LinkedIn profile content.
        *   Extracts structured data (current role, company, contact info) to update the lead profile.

### Helper Agents

8.  **ValidatorAgent** (`validator.py`)
    *   **Role**: Ensures data quality and consistency.
    *   **Responsibilities**:
        *   Validates fields (email format, phone format, domain validity).
        *   Normalizes data (capitalization, URL formatting).
        *   Calculates an overall quality score for each lead.

9.  **QueryBuilderAgent** (`query_builder.py`)
    *   **Role**: Optimizes search queries.
    *   **Responsibilities**:
        *   Rewrites user queries to include positive keywords (e.g., "profile", "CTO") and exclude negative ones (e.g., "jobs", "hiring").
        *   Adds domain filtering parameters.

## Agent Interactions

The agents interact in a sequential pipeline orchestrated by the **OrchestratorAgent**:

1.  **Planning**: `OrchestratorAgent` receives a user query and creates a `TaskPlan`.
2.  **Discovery**: `OrchestratorAgent` calls `WebNavigatorAgent` to search and fetch relevant web pages.
    *   `WebNavigatorAgent` uses `QueryBuilderAgent` to optimize the search.
3.  **Extraction**: `OrchestratorAgent` passes fetched content to `ContentExtractorAgent` to parse out initial `LeadProfile` objects.
4.  **Enrichment**: `OrchestratorAgent` passes leads to `LeadEnricherAgent`.
    *   `LeadEnricherAgent` calls `LinkedInProfileEnricherAgent` if a LinkedIn URL is present.
    *   `LeadEnricherAgent` calls `CompanyDomainAgent` to find missing domains.
    *   `LeadEnricherAgent` calls `EmailDiscoveryAgent` to find missing emails.
    *   `LeadEnricherAgent` performs LLM inference for any remaining gaps.
5.  **Validation**: `OrchestratorAgent` passes enriched leads to `ValidatorAgent` for final checking and scoring.
6.  **Aggregation**: `OrchestratorAgent` collects all valid leads into the final output.

## Desired Output

The primary output of the agent interactions is a **`LeadBatch`** object (serialized to JSON), which contains:

*   **`leads`**: A list of fully enriched and validated `LeadProfile` objects. Each profile includes:
    *   Name
    *   Role
    *   Company
    *   Company Domain
    *   Email
    *   Phone Number
    *   LinkedIn URL
    *   Confidence Score
    *   Metadata (source URL, extraction timestamp)
*   **`metadata`**: Aggregate statistics about the batch, including:
    *   Total leads processed
    *   Success rate
    *   Average confidence score
    *   Agent execution stats

This output is saved to the `artifacts/` directory as `final_output_{timestamp}.json`.
