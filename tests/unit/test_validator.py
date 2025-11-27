import pytest
from agents.validator import ValidatorAgent
from models.lead import LeadProfile

@pytest.fixture
def validator():
    return ValidatorAgent()

def test_phone_normalization_us(validator):
    lead = LeadProfile(
        name="Test User",
        role="CEO",
        company="Test Corp",
        phone_number="650-253-0000"  # Valid US number
    )
    normalized = validator.normalize_data(lead)
    assert normalized.phone_number == "+16502530000"

def test_phone_normalization_intl(validator):
    lead = LeadProfile(
        name="Test User",
        role="CEO",
        company="Test Corp",
        phone_number="+44 20 7123 1234"  # Valid UK number
    )
    normalized = validator.normalize_data(lead)
    assert normalized.phone_number == "+442071231234"

def test_phone_normalization_fallback(validator):
    lead = LeadProfile(
        name="Test User",
        role="CEO",
        company="Test Corp",
        phone_number="invalid-phone"
    )
    normalized = validator.normalize_data(lead)
    assert normalized.phone_number == "invalid-phone"

def test_validate_lead_valid(validator):
    lead = LeadProfile(
        name="Test User",
        role="CEO",
        company="Test Corp",
        email="test@gmail.com",  # Use real domain
        linkedin="https://linkedin.com/in/testuser",
        confidence_score=0.9
    )
    result = validator.validate_lead(lead)
    assert result.is_valid
    assert not result.errors

def test_validate_lead_invalid_email(validator):
    # Pydantic validates email format at instantiation
    from pydantic import ValidationError
    try:
        lead = LeadProfile(
            name="Test User",
            role="CEO",
            company="Test Corp",
            email="invalid-email",
            confidence_score=0.9
        )
        assert False, "Should have raised ValidationError"
    except ValidationError:
        assert True
