from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator

class Company(BaseModel):
    """
    Represents a company profile for enrichment context.
    """
    name: str = Field(..., description="Company name")
    domain: str = Field(..., description="Company domain name")
    industry: Optional[str] = Field(None, description="Industry sector")
    size: Optional[str] = Field(None, description="Company size range")
    location: Optional[str] = Field(None, description="Headquarters location")
    description: Optional[str] = Field(None, description="Brief company description")
    website: Optional[str] = Field(None, description="Full website URL")

    @field_validator('domain')
    @classmethod
    def validate_domain(cls, v: str) -> str:
        if not v:
            raise ValueError("Domain is required")
        domain = v.lower().strip()
        domain = domain.replace("https://", "").replace("http://", "").replace("www.", "")
        return domain.split("/")[0]

    @field_validator('website')
    @classmethod
    def validate_website(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        # Basic check to ensure it looks like a URL if provided
        if not v.startswith(("http://", "https://")):
             return f"https://{v}"
        return v
