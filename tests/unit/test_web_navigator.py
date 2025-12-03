import pytest
from agents.web_navigator import WebNavigatorAgent

class TestWebNavigatorFiltering:
    
    @pytest.fixture
    def navigator(self):
        return WebNavigatorAgent()
        
    def test_filter_valid_profiles(self, navigator):
        urls = [
            "https://www.linkedin.com/in/john-doe/",
            "https://linkedin.com/in/jane-smith",
            "https://www.linkedin.com/in/carlo-bizzaro-123456/"
        ]
        expected = [
            "https://www.linkedin.com/in/john-doe/",
            "https://www.linkedin.com/in/jane-smith",
            "https://www.linkedin.com/in/carlo-bizzaro-123456/"
        ]
        filtered = navigator._filter_linkedin_profile_urls(urls)
        assert len(filtered) == 3
        assert sorted(filtered) == sorted(expected)
        
    def test_filter_excluded_pages(self, navigator):
        urls = [
            "https://www.linkedin.com/jobs/view/123456",
            "https://www.linkedin.com/company/google",
            "https://www.linkedin.com/posts/john-doe_activity-123456",
            "https://www.linkedin.com/feed/update/urn:li:activity:123456",
            "https://www.linkedin.com/learning/python-course"
        ]
        filtered = navigator._filter_linkedin_profile_urls(urls)
        assert len(filtered) == 0
        
    def test_filter_mixed_urls(self, navigator):
        urls = [
            "https://www.linkedin.com/in/john-doe/",
            "https://www.linkedin.com/jobs/view/123456",
            "https://www.google.com",  # Non-LinkedIn URL should be kept
            "https://www.linkedin.com/company/google"
        ]
        filtered = navigator._filter_linkedin_profile_urls(urls)
        assert len(filtered) == 2
        assert "https://www.linkedin.com/in/john-doe/" in filtered
        assert "https://www.google.com" in filtered
        
    def test_filter_profile_subpages(self, navigator):
        urls = [
            "https://www.linkedin.com/in/john-doe/details/experience/", # Should be kept or handled? Requirement says exclude posts/jobs. 
                                                                        # Implementation excludes /detail/
            "https://www.linkedin.com/in/john-doe/recent-activity/",    # Excluded
            "https://www.linkedin.com/in/john-doe/posts/"               # Excluded
        ]
        # Based on implementation:
        # /details/ -> excluded
        # /recent-activity/ -> excluded
        # /posts/ -> excluded
        filtered = navigator._filter_linkedin_profile_urls(urls)
        assert len(filtered) == 0
        
    def test_filter_query_params(self, navigator):
        urls = [
            "https://www.linkedin.com/in/john-doe?trk=public_profile_browsemap",
            "https://www.linkedin.com/in/jane-smith/?originalSubdomain=de"
        ]
        filtered = navigator._filter_linkedin_profile_urls(urls)
        assert len(filtered) == 2
