"""
LangExtract schemas for B2B lead generation.

This module defines the Pydantic schemas used by LangExtract for structured
extraction of company and person information from HTML text.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from enum import Enum


class CompanySize(str, Enum):
    """Company size categories."""
    STARTUP = "startup"  # 1-10 employees
    SMALL = "small"      # 11-50 employees  
    MEDIUM = "medium"    # 51-200 employees
    LARGE = "large"      # 201-1000 employees
    ENTERPRISE = "enterprise"  # 1000+ employees


class Industry(str, Enum):
    """Industry categories for classification."""
    SAAS = "saas"
    FINTECH = "fintech"
    HEALTHCARE = "healthcare"
    ECOMMERCE = "ecommerce"
    AI_ML = "ai_ml"
    BLOCKCHAIN = "blockchain"
    CYBERSECURITY = "cybersecurity"
    MARKETING = "marketing"
    EDUCATION = "education"
    PRODUCTIVITY = "productivity"
    INFRASTRUCTURE = "infrastructure"
    OTHER = "other"


class CompanyProfile(BaseModel):
    """
    Schema for company information extraction.
    
    This is the target schema for LangExtract when extracting company data
    from scraped HTML/text content.
    """
    
    # Core identification
    company_name: Optional[str] = Field(
        None, 
        description="Official company name as displayed on the website"
    )
    
    website_url: Optional[HttpUrl] = Field(
        None, 
        description="Primary website URL"
    )
    
    # Business information
    description: Optional[str] = Field(
        None, 
        description="Company description, mission, or value proposition"
    )
    
    industry: Optional[Industry] = Field(
        None, 
        description="Primary industry category"
    )
    
    company_size: Optional[CompanySize] = Field(
        None, 
        description="Estimated company size category"
    )
    
    founded_year: Optional[int] = Field(
        None, 
        description="Year company was founded"
    )
    
    # Location information
    headquarters_location: Optional[str] = Field(
        None, 
        description="City, state/province, country of headquarters"
    )
    
    # Contact information
    general_email: Optional[EmailStr] = Field(
        None, 
        description="General contact email (info@, hello@, contact@)"
    )
    
    general_phone: Optional[str] = Field(
        None, 
        description="General phone number in international format"
    )
    
    # Key personnel (extracted if prominently displayed)
    key_personnel: List["PersonProfile"] = Field(
        default_factory=list,
        description="Key executives or contacts listed on the site"
    )
    
    # Social and additional links
    linkedin_url: Optional[HttpUrl] = Field(
        None, 
        description="Company LinkedIn page URL"
    )
    
    twitter_url: Optional[HttpUrl] = Field(
        None, 
        description="Company Twitter/X URL"
    )
    
    # Technology stack indicators
    tech_stack: List[str] = Field(
        default_factory=list,
        description="Technologies, frameworks, or tools mentioned"
    )
    
    # Funding and business metrics (if publicly available)
    funding_info: Optional[str] = Field(
        None, 
        description="Funding rounds, valuation, or growth metrics"
    )
    
    # Extraction metadata
    source_url: Optional[HttpUrl] = Field(
        None, 
        description="URL from which this data was extracted"
    )
    
    extraction_confidence: float = Field(
        0.0, 
        ge=0.0, 
        le=1.0,
        description="Confidence score of the extraction (0-1)"
    )


class PersonProfile(BaseModel):
    """
    Schema for person information extraction.
    
    This is the target schema for LangExtract when extracting individual
    person data from profiles, team pages, or contact sections.
    """
    
    # Basic identification
    full_name: Optional[str] = Field(
        None, 
        description="Full name of the person"
    )
    
    title: Optional[str] = Field(
        None, 
        description="Job title or role"
    )
    
    # Company association
    company: Optional[str] = Field(
        None, 
        description="Company name (if person is associated with one)"
    )
    
    # Contact information
    email: Optional[EmailStr] = Field(
        None, 
        description="Personal or professional email address"
    )
    
    phone: Optional[str] = Field(
        None, 
        description="Phone number in international format"
    )
    
    # Location
    location: Optional[str] = Field(
        None, 
        description="City, state/province, country"
    )
    
    # Professional links
    linkedin_url: Optional[HttpUrl] = Field(
        None, 
        description="LinkedIn profile URL"
    )
    
    twitter_url: Optional[HttpUrl] = Field(
        None, 
        description="Twitter/X profile URL"
    )
    
    # Bio and background
    bio: Optional[str] = Field(
        None, 
        description="Professional biography or description"
    )
    
    # Experience indicators
    years_experience: Optional[int] = Field(
        None, 
        description="Years of professional experience (if mentioned)"
    )
    
    # Skills and expertise
    skills: List[str] = Field(
        default_factory=list,
        description="Skills, expertise, or specializations"
    )
    
    # Extraction metadata
    source_context: Optional[str] = Field(
        None, 
        description="Context where this person was found (e.g., 'team page', 'contact section')"
    )
    
    extraction_confidence: float = Field(
        0.0, 
        ge=0.0, 
        le=1.0,
        description="Confidence score of the extraction (0-1)"
    )


# Update forward references
CompanyProfile.model_rebuild()
PersonProfile.model_rebuild()


class ExtractionRequest(BaseModel):
    """
    Request schema for LangExtract extraction operations.
    
    This encapsulates the input to LangExtract along with extraction parameters.
    """
    
    text_content: str = Field(
        description="Raw HTML or text content to extract from"
    )
    
    extraction_type: str = Field(
        description="Type of extraction: 'company' or 'person'"
    )
    
    source_url: Optional[str] = Field(
        None,
        description="Original URL where content was sourced from"
    )
    
    context_hints: Optional[List[str]] = Field(
        default_factory=list,
        description="Additional context to help extraction (e.g., 'contact page', 'about us')"
    )


class ExtractionResult(BaseModel):
    """
    Result schema for LangExtract extraction operations.
    
    This wraps the extraction results with metadata about the process.
    """
    
    success: bool = Field(
        description="Whether extraction was successful"
    )
    
    data: Optional[CompanyProfile | PersonProfile] = Field(
        None,
        description="Extracted structured data"
    )
    
    error_message: Optional[str] = Field(
        None,
        description="Error message if extraction failed"
    )
    
    extraction_method: str = Field(
        description="Method used: 'local_model', 'ollama_cloud', or 'firecrawl'"
    )
    
    confidence_score: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in extraction quality"
    )
    
    processing_time_ms: Optional[int] = Field(
        None,
        description="Processing time in milliseconds"
    )