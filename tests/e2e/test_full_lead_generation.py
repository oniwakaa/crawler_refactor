import pytest
import os
from pipelines.b2b_lead_pipeline import B2BLeadPipeline, PipelineConfig

@pytest.mark.asyncio
async def test_full_pipeline_execution():
    """
    E2E Test: Run the full B2B Lead Generation Pipeline.
    Uses real agents and tools.
    """
    if not os.getenv("FIRECRAWL_API_KEY"):
        pytest.skip("FIRECRAWL_API_KEY not set")

    config = PipelineConfig(
        query="AI startups in San Francisco",
        max_results=2,
        verbose=True
    )

    async with B2BLeadPipeline(config) as pipeline:
        result_batch = await pipeline.run_pipeline()
        
        assert result_batch is not None
        assert result_batch.query == config.query
        # We don't strictly assert leads > 0 because live search results vary,
        # but the pipeline should complete successfully.
        assert isinstance(result_batch.leads, list)
