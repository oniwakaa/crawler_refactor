import pytest
from tools.linkedin_search_builder import LinkedInPeopleSearchBuilder

class TestLinkedInSearchBuilder:
    
    def test_build_simple_url(self):
        url = LinkedInPeopleSearchBuilder.build_people_search_url(role="CTO")
        assert "keywords=CTO" in url
        assert "origin=GLOBAL_SEARCH_HEADER" in url
        
    def test_build_with_location(self):
        url = LinkedInPeopleSearchBuilder.build_people_search_url(role="CTO", location="Berlin")
        assert "CTO" in url
        assert "Berlin" in url
        
    def test_build_with_company(self):
        url = LinkedInPeopleSearchBuilder.build_people_search_url(role="Developer", company="Google")
        assert "Developer" in url
        assert "Google" in url
        
    def test_build_full(self):
        url = LinkedInPeopleSearchBuilder.build_people_search_url(
            role="Manager", 
            location="London", 
            company="Amazon",
            keywords="AWS"
        )
        # URL encoded check
        assert "Manager" in url
        assert "London" in url
        assert "Amazon" in url
        assert "AWS" in url
        
    def test_empty_terms(self):
        with pytest.raises(ValueError):
            LinkedInPeopleSearchBuilder.build_people_search_url(role="")
