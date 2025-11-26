"""
Extraction prompts for LangExtract operations.

This module contains optimized prompts for different extraction scenarios,
designed to work effectively with local models like SmolLM3-thinking.
"""

from typing import List, Dict, Any
from .schemas import CompanyProfile, PersonProfile


class ExtractionPrompts:
    """Collection of extraction prompts for different scenarios."""
    
    # Base prompt templates
    BASE_PROMPT_TEMPLATE = """
    You are a data extraction specialist. Extract structured information from the provided text.
    
    IMPORTANT RULES:
    - Extract ONLY information that is explicitly present in the text
    - Do NOT guess, infer, or make assumptions
    - Return None for uncertain information rather than guessing
    - Pay special attention to contact details and proper formatting
    
    CONTEXT: {context_hints}
    
    TEXT TO ANALYZE:
    {text_content}
    
    EXTRACTION TARGET: {extraction_type}
    {schema_description}
    
    OUTPUT FORMAT: Return a valid JSON object that matches the provided schema exactly.
    """
    
    # Company-specific enhancements
    COMPANY_ENHANCEMENT = """
    
    COMPANY-SPECIFIC GUIDELINES:
    - Look for official company name, not just domain name
    - Identify primary business description/mission statement
    - Extract tech stack from job postings, about pages, or tech blogs
    - Note funding information if mentioned (funding rounds, investors)
    - Company size indicators: "team of 50", "10 employees", "enterprise software"
    - Industry classification from about pages, press releases, or product descriptions
    """
    
    # Person-specific enhancements  
    PERSON_ENHANCEMENT = """
    
    PERSON-SPECIFIC GUIDELINES:
    - Full name (first and last name clearly identified)
    - Current job title and company association
    - Professional contact information (email, phone if personal page)
    - Location can be city/state or broader geographic area
    - LinkedIn and Twitter URLs if provided
    - Professional background from bios, about pages, or LinkedIn-style summaries
    - Skills and expertise from job descriptions or professional profiles
    """
    
    @classmethod
    def get_company_prompt(
        cls, 
        text_content: str, 
        context_hints: List[str] = None,
        custom_instructions: str = None
    ) -> str:
        """
        Generate optimized prompt for company extraction.
        
        Args:
            text_content: Text/HTML content to extract from
            context_hints: Additional context (e.g., "about page", "contact page")
            custom_instructions: Additional specific instructions
            
        Returns:
            Formatted extraction prompt
        """
        context_str = ", ".join(context_hints) if context_hints else "No specific context"
        
        schema_desc = f"""
        
        SCHEMA REQUIREMENTS for CompanyProfile:
        - company_name: Official business name (not domain)
        - website_url: Primary company website
        - description: Business mission, value proposition, or product description
        - industry: Primary business category (saas, fintech, healthcare, etc.)
        - company_size: startup(1-10), small(11-50), medium(51-200), large(201-1000), enterprise(1000+)
        - founded_year: Year company was established
        - headquarters_location: City, state/province, country
        - general_email: Contact email (info@, hello@, contact@, etc.)
        - general_phone: Main phone number in international format
        - key_personnel: Key executives mentioned on the site
        - linkedin_url: Company LinkedIn page URL
        - twitter_url: Company Twitter/X URL
        - tech_stack: Technologies, frameworks, or tools mentioned
        - funding_info: Investment rounds, valuation, or growth metrics
        """
        
        base = cls.BASE_PROMPT_TEMPLATE.format(
            context_hints=context_str,
            text_content=text_content[:4000],  # Limit input length
            extraction_type="company information",
            schema_description=schema_desc + cls.COMPANY_ENHANCEMENT
        )
        
        if custom_instructions:
            base += f"\n\nCUSTOM INSTRUCTIONS: {custom_instructions}"
            
        return base
    
    @classmethod
    def get_person_prompt(
        cls, 
        text_content: str, 
        context_hints: List[str] = None,
        custom_instructions: str = None
    ) -> str:
        """
        Generate optimized prompt for person extraction.
        
        Args:
            text_content: Text/HTML content to extract from
            context_hints: Additional context (e.g., "team page", "contact section")
            custom_instructions: Additional specific instructions
            
        Returns:
            Formatted extraction prompt
        """
        context_str = ", ".join(context_hints) if context_hints else "No specific context"
        
        schema_desc = f"""
        
        SCHEMA REQUIREMENTS for PersonProfile:
        - full_name: Complete first and last name
        - title: Current job title or role
        - company: Company name (if person works for a company)
        - email: Professional or personal email address
        - phone: Phone number in international format
        - location: City, state/province, country or broader geographic area
        - linkedin_url: LinkedIn profile URL
        - twitter_url: Twitter/X profile URL
        - bio: Professional biography or background description
        - years_experience: Years of professional experience (if mentioned)
        - skills: Professional skills or expertise areas
        - source_context: Where this person was found (e.g., "team page", "contact section")
        """
        
        base = cls.BASE_PROMPT_TEMPLATE.format(
            context_hints=context_str,
            text_content=text_content[:4000],  # Limit input length
            extraction_type="person information",
            schema_description=schema_desc + cls.PERSON_ENHANCEMENT
        )
        
        if custom_instructions:
            base += f"\n\nCUSTOM INSTRUCTIONS: {custom_instructions}"
            
        return base
    
    @classmethod
    def get_contact_focused_prompt(cls, text_content: str) -> str:
        """
        Generate prompt focused on contact information extraction.
        
        Optimized for extracting emails, phone numbers, and contact forms
        from contact pages or footer sections.
        """
        return cls.get_company_prompt(
            text_content=text_content,
            context_hints=["contact page", "contact information"],
            custom_instructions="PRIORITIZE contact information: emails, phone numbers, contact forms. Look for multiple contact methods."
        )
    
    @classmethod
    def get_team_focused_prompt(cls, text_content: str) -> str:
        """
        Generate prompt focused on team/people extraction.
        
        Optimized for extracting person information from team pages,
        about pages, or leadership sections.
        """
        return cls.get_person_prompt(
            text_content=text_content,
            context_hints=["team page", "about us", "leadership"],
            custom_instructions="PRIORITIZE person details: names, titles, roles, and any contact information for team members."
        )
    
    @classmethod
    def get_about_page_prompt(cls, text_content: str) -> str:
        """
        Generate prompt for about page content.
        
        Optimized for extracting company description, mission,
        values, and business information from about pages.
        """
        return cls.get_company_prompt(
            text_content=text_content,
            context_hints=["about page", "company description"],
            custom_instructions="PRIORITIZE company description, mission statement, values, founding story, and business information."
        )


class ValidationPrompts:
    """Prompts for data validation and enrichment."""
    
    EMAIL_VALIDATION_PROMPT = """
    Validate the following email address for business relevance:
    
    Email: {email}
    Context: {context}
    
    Consider:
    - Is this a valid email format?
    - Does it appear to be a business contact (not personal email like gmail.com)?
    - Is it appropriate for business outreach?
    
    Return: {{"valid": bool, "business_relevance": bool, "confidence": float}}
    """
    
    PHONE_VALIDATION_PROMPT = """
    Validate and format the following phone number:
    
    Phone: {phone}
    Context: {context}
    
    Consider:
    - Is this a valid phone number format?
    - Does it appear to be a business line?
    - Can it be formatted as international standard?
    
    Return: {{"valid": bool, "formatted": str, "business_line": bool, "confidence": float}}
    """
    
    COMPANY_SIZE_VALIDATION_PROMPT = """
    Estimate company size based on available information:
    
    Company: {company_name}
    Indicators: {indicators}
    Website content: {content}
    
    Consider:
    - Team size mentions
    - Job posting volume
    - Company description and maturity
    - Office locations and scale
    
    Return: {{"size_estimate": "startup|small|medium|large|enterprise", "confidence": float, "reasoning": str}}
    """


# Prompt configuration for different model types
MODEL_PROMPT_CONFIGS = {
    "smollm3-thinking": {
        "max_tokens": 1500,
        "temperature": 0.1,
        "system_prompt": "You are a precise data extraction assistant. Extract only explicit information with high accuracy."
    },
    "llama3.1": {
        "max_tokens": 2000,
        "temperature": 0.05,
        "system_prompt": "You are an expert data extraction specialist focusing on accuracy and completeness."
    }
}


def get_optimized_prompt(
    extraction_type: str,
    text_content: str, 
    context_hints: List[str] = None,
    model_name: str = "smollm3-thinking",
    custom_instructions: str = None
) -> Dict[str, Any]:
    """
    Get optimized prompt configuration for extraction.
    
    Args:
        extraction_type: Type of extraction ("company" or "person")
        text_content: Content to extract from
        context_hints: Context hints for better extraction
        model_name: Target model for optimization
        custom_instructions: Additional instructions
        
    Returns:
        Dictionary with prompt configuration
    """
    # Get base prompt based on extraction type
    if extraction_type == "company":
        prompt = ExtractionPrompts.get_company_prompt(
            text_content, context_hints, custom_instructions
        )
    elif extraction_type == "person":
        prompt = ExtractionPrompts.get_person_prompt(
            text_content, context_hints, custom_instructions
        )
    else:
        raise ValueError(f"Unknown extraction type: {extraction_type}")
    
    # Get model-specific configuration
    model_config = MODEL_PROMPT_CONFIGS.get(model_name, MODEL_PROMPT_CONFIGS["smollm3-thinking"])
    
    return {
        "prompt": prompt,
        "max_tokens": model_config["max_tokens"],
        "temperature": model_config["temperature"],
        "system_prompt": model_config["system_prompt"],
        "model": model_name
    }