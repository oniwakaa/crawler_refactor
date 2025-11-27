import pytest
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.append(str(Path(__file__).parent.parent.parent))

def test_imports():
    """Test that all modules can be imported."""
    from agents.orchestrator import OrchestratorAgent
    from tools.firecrawl_client import FirecrawlClient
    from models.lead import LeadProfile
    assert True

def test_simple_math():
    """Basic test to verify pytest works."""
    assert 1 + 1 == 2
