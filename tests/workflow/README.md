# Workflow Tests

This directory contains tests designed to provide a deep understanding of the agent system's workflow, facilitate debugging, and assist in prompt engineering.

## Goal

The primary goals of these tests are:
1.  **Debugging**: Isolate and verify each step of the pipeline (Decomposition, Search, Extraction, Enrichment, Validation).
2.  **Prompt Engineering**: Inspect the exact inputs (prompts) sent to the LLM and the raw outputs received. This allows for rapid iteration on prompt design.
3.  **System Understanding**: Document the flow of data through the system, clarifying inputs and outputs for each component.

## Test Structure

### `test_step_by_step.py`

This is the main test file. It executes the B2B Lead Generation pipeline components sequentially, but with manual orchestration to allow for detailed logging at each stage.

**Key Features:**
*   **Step-by-Step Execution**: Runs each agent explicitly and asserts the validity of intermediate outputs.
*   **Detailed Logging**: Prints formatted sections for each step, showing exactly what data went in and what came out.
*   **LLM Inspection**: Leverages the `LlamaWrapper`'s `last_interaction` feature to log:
    *   The model used.
    *   A preview of the raw prompt sent to the LLM.
    *   A preview of the raw response received.

## Usage

To run the step-by-step workflow test and see the detailed logs in your terminal:

```bash
python -m tests.workflow.test_step_by_step
```

To save the output to a file for easier analysis (recommended for long prompts):

```bash
python -m tests.workflow.test_step_by_step > workflow_log.txt 2>&1
```

## Workflow Steps Covered

1.  **Query Decomposition** (`OrchestratorAgent`): Converts a user query into a structured `TaskPlan`.
2.  **Web Search** (`WebNavigatorAgent`): Executes search queries and fetches web page content.
3.  **Content Extraction** (`ContentExtractorAgent`): Extracts structured `LeadProfile` objects from raw HTML/Markdown.
4.  **Enrichment** (`LeadEnricherAgent`): Enhances leads with missing data (e.g., via LinkedIn or company domain lookup).
5.  **Validation** (`ValidatorAgent`): Validates and normalizes the final lead data.
