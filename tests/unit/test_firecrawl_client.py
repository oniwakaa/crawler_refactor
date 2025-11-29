import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tools.firecrawl_client import FirecrawlClient

@pytest.fixture
def firecrawl_client():
    return FirecrawlClient(api_key="test_key")

@pytest.mark.asyncio
async def test_batch_scrape_payload(firecrawl_client):
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        firecrawl_client.client = mock_client
        
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "test_job_id"}
        mock_client.request.return_value = mock_response
        
        # Mock poll response
        mock_poll_response = MagicMock()
        mock_poll_response.json.return_value = {
            "status": "completed",
            "data": [{"url": "http://example.com", "markdown": "content"}]
        }
        # First call returns job id, second call (poll) returns result
        mock_client.request.side_effect = [mock_response, mock_poll_response]
        
        await firecrawl_client.batch_scrape(["http://example.com"])
        
        # Verify payload structure
        call_args = mock_client.request.call_args_list[0]
        method, url = call_args[0]
        kwargs = call_args[1]
        
        assert method == "POST"
        assert url.endswith("/batch/scrape")
        assert "formats" in kwargs["json"]
