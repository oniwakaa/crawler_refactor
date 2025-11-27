"""
Pytest configuration and fixtures for B2B Lead Generation tests.
"""
import pytest
import asyncio
import os
import json
from pathlib import Path
from typing import List, Dict, Any

# Set up test environment
from dotenv import load_dotenv
load_dotenv()

os.environ.setdefault("FIRECRAWL_API_KEY", "test_key_placeholder")

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_artifacts_dir(tmp_path):
    """Create temporary artifacts directory for tests."""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    return artifacts_dir

@pytest.fixture
def sample_urls():
    """Load sample URLs from fixtures."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_urls.json"
    with open(fixture_path, 'r') as f:
        return json.load(f)

@pytest.fixture
def expected_leads():
    """Load expected leads from fixtures."""
    fixture_path = Path(__file__).parent / "fixtures" / "expected_leads.json"
    with open(fixture_path, 'r') as f:
        return json.load(f)

@pytest.fixture
def sample_markdown_dir():
    """Path to sample markdown fixtures."""
    return Path(__file__).parent / "fixtures" / "sample_markdown"

@pytest.fixture
def sample_about_page(sample_markdown_dir):
    """Load sample about page markdown."""
    with open(sample_markdown_dir / "about_page.md", 'r') as f:
        return f.read()

@pytest.fixture
def sample_team_page(sample_markdown_dir):
    """Load sample team page markdown."""
    with open(sample_markdown_dir / "team_page.md", 'r') as f:
        return f.read()

@pytest.fixture
def sample_minimal_page(sample_markdown_dir):
    """Load sample minimal page markdown."""
    with open(sample_markdown_dir / "minimal_page.md", 'r') as f:
        return f.read()

@pytest.fixture
def mock_page_results():
    """Create mock page fetch results."""
    return [
        {
            "url": "https://example.com/about",
            "markdown": "# Team\\n\\nJohn Smith - CTO at Example Corp\\nemail: john@example.com",
            "html": "<html>...</html>",
            "fetch_status": "success",
            "method_used": "crawl4ai",
            "timestamp": 1234567890.0
        },
        {
            "url": "https://example.com/team",
            "markdown": "# Leadership\\n\\nMaria Garcia - CEO\\nlinkedin.com/in/maria",
            "html": "<html>...</html>",
            "fetch_status": "success",
            "method_used": "crawl4ai",
            "timestamp": 1234567891.0
        }
    ]

@pytest.fixture
def sample_lead_profile():
    """Create a sample lead profile for testing."""
    from models.lead import LeadProfile
    return LeadProfile(
        name="John Smith",
        role="CTO",
        linkedin="https://linkedin.com/in/johnsmith",
        company="Example Corp",
        company_domain="example.com",
        email="john@example.com",
        phone_number="+491234567890",
        confidence_score=0.9
    )

@pytest.fixture
def sample_partial_lead():
    """Create a partial lead profile for enrichment testing."""
    from models.lead import LeadProfile
    return LeadProfile(
        name="Maria Garcia",
        role="CEO",
        company="Tech Startup GmbH",
        confidence_score=0.7
    )

@pytest.fixture
def settings_path():
    """Path to test settings file."""
    return "config/settings.yaml"

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (may require network)"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test (requires full setup)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )

@pytest.fixture(autouse=True)
def cleanup_artifacts():
    """Clean up artifacts after each test."""
    yield
    # Cleanup code runs after test
    artifacts_dir = Path("artifacts")
    if artifacts_dir.exists():
        # Keep artifacts for debugging, just log
        pass
