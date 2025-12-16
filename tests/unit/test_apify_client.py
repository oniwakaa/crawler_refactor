import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from tools.apify_client import ApifyScraperClient
import os

class TestApifyScraperClient:
    @pytest.fixture
    def mock_settings(self):
        return {
            "apify": {
                "actor_id": "test_actor_id",
                "batch_size": 2,
                "timeout_seconds": 60,
                "retries": 1
            }
        }

    @pytest.fixture
    def client(self, mock_settings):
        with patch.dict(os.environ, {"APIFY_API_TOKEN": "test_token"}):
            return ApifyScraperClient(settings=mock_settings)

    @patch("tools.apify_client.ApifyClient")
    def test_initialization(self, mock_apify, mock_settings):
        with patch.dict(os.environ, {"APIFY_API_TOKEN": "test_token"}):
            client = ApifyScraperClient(settings=mock_settings)
            
        mock_apify.assert_called_with(token="test_token")
        assert client.actor_id == "test_actor_id"
        assert client.batch_size == 2

    def test_run_actor_success(self, client):
        # Mock the internal ApifyClient instance
        client.client = MagicMock()
        
        # Setup mock actor run
        mock_actor_client = MagicMock()
        client.client.actor.return_value = mock_actor_client
        mock_actor_client.call.return_value = {"defaultDatasetId": "dataset_123"}
        
        # Setup mock dataset items
        mock_dataset_client = MagicMock()
        client.client.dataset.return_value = mock_dataset_client
        mock_dataset_client.list_items.return_value.items = [
            {
                "url": "https://linkedin.com/in/user1",
                "fullName": "User One",
                "headline": "Developer",
                "success": True
            },
            {
                "url": "https://linkedin.com/in/user2",
                "fullName": "User Two",
                "headline": "Manager",
                "success": True
            }
        ]
        
        urls = ["https://linkedin.com/in/user1", "https://linkedin.com/in/user2"]
        results = client.scrape_profiles(urls)
        
        assert len(results) == 2
        assert results[0]["url"] == "https://linkedin.com/in/user1"
        assert "formatted_text" in results[0]
        assert "Name: User One" in results[0]["formatted_text"]
        
        # Check raw_data for original fields
        assert results[0]["raw_data"]["fullName"] == "User One"
        
        mock_actor_client.call.assert_called()
        client.client.dataset.assert_called_with("dataset_123")

    def test_transform_to_text(self, client):
        data = {
            "fullName": "John Doe",
            "headline": "Software Engineer",
            "location": {"short": "New York"},
            "summary": "Building things.",
            "email": "john@example.com",
            "experience": [
                {
                    "title": "Senior Dev",
                    "company": "Tech Corp",
                    "duration": "2020 - Present",
                    "description": "Coding."
                }
            ],
            "education": [
                {
                    "schoolName": "MIT",
                    "degree": "BS CS"
                }
            ]
        }
        
        text = client._transform_to_text(data)
        
        assert "Name: John Doe" in text
        assert "Headline: Software Engineer" in text
        assert "Email: john@example.com" in text
        assert "# Experience" in text
        assert "Title: Senior Dev" in text
        assert "Company: Tech Corp" in text
        assert "# Education" in text
        assert "School: MIT" in text

    @patch("tools.apify_client.ApifyClient")
    def test_batching_logic(self, mock_apify, client):
        # Client batch size is 2 (from fixture)
        urls = ["u1", "u2", "u3", "u4", "u5"]
        
        # Mock _run_actor to just return empty list to avoid complex mocking
        # But we need to keep scrape_profiles logic intact.
        # So we can patch _run_actor on the instance
        
        with patch.object(client, "_run_actor", return_value=[]) as mock_run_actor:
            client.scrape_profiles(urls)
            
            assert mock_run_actor.call_count == 3  # Batches of 2: [u1,u2], [u3,u4], [u5]
            mock_run_actor.assert_any_call(["u1", "u2"])
            mock_run_actor.assert_any_call(["u3", "u4"])
            mock_run_actor.assert_any_call(["u5"])
