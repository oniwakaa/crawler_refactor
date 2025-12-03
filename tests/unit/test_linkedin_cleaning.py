import pytest
from agents.content_extractor import ContentExtractorAgent

@pytest.fixture
def extractor():
    return ContentExtractorAgent()

def test_extract_linkedin_sections_basic(extractor):
    markdown = """
    John Doe
    Software Engineer at Tech Corp
    
    About
    Experienced developer...
    
    Experience
    Software Engineer
    Tech Corp
    2020 - Present
    
    Education
    University of Tech
    """
    
    sections = extractor._extract_linkedin_sections(markdown)
    
    assert "HEADER:" in sections
    assert "John Doe" in sections
    assert "ABOUT:" in sections
    assert "Experienced developer" in sections
    assert "EXPERIENCE:" in sections
    assert "Software Engineer" in sections
    assert "EDUCATION:" in sections
    assert "University of Tech" in sections

def test_extract_linkedin_sections_noise_filtering(extractor):
    markdown = """
    John Doe
    
    {
        "lixTracking": "some_data"
    }
    
    About
    Good summary.
    
    request": 123
    """
    
    sections = extractor._extract_linkedin_sections(markdown)
    
    assert "HEADER:" in sections
    assert "John Doe" in sections
    assert "ABOUT:" in sections
    assert "Good summary" in sections
    assert "lixTracking" not in sections
    assert "request\":" not in sections

def test_clean_markdown_fallback(extractor):
    # Test that _clean_markdown still works for non-profile content
    markdown = """
    Some content
    { "json": "data" }
    More content
    """
    
    cleaned = extractor._clean_markdown(markdown)
    
    assert "Some content" in cleaned
    assert "More content" in cleaned
    assert "json" not in cleaned # JSON should be removed by general cleaner
