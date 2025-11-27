import re
import time
from typing import List, Dict, Any, Optional
import structlog
from pathlib import Path
import yaml
import phonenumbers
from phonenumbers import NumberParseException
from email_validator import validate_email, EmailNotValidError
from pydantic import BaseModel, Field

from models.lead import LeadProfile

logger = structlog.get_logger()

class ValidationResult(BaseModel):
    """Validation result for a lead"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    normalized_lead: Optional[LeadProfile] = None
    quality_score: float = 0.0

class ValidatorAgent:
    """
    Validator agent responsible for validating and normalizing lead data.
    Uses regex patterns, phonenumbers library, and email-validator for validation.
    """
    
    def __init__(self, settings_path: str = "config/settings.yaml"):
        """
        Initialize ValidatorAgent.
        
        Args:
            settings_path: Path to settings YAML file
        """
        self.settings = self._load_settings(settings_path)
        
        # Load configuration
        validation_config = self.settings.get("validation", {})
        self.email_validation = validation_config.get("email_validation", True)
        self.phone_validation = validation_config.get("phone_validation", True)
        self.url_validation = validation_config.get("url_validation", True)
        
        # Confidence threshold from extraction config (lowered from 0.7 to 0.5 for more lenient validation)
        extraction_config = self.settings.get("extraction", {})
        self.confidence_threshold = extraction_config.get("confidence_threshold", 0.5)
        
        # Quality score thresholds
        self.min_quality_threshold = 0.3  # Minimum quality to accept leads
        
    def _load_settings(self, settings_path: str) -> Dict[str, Any]:
        """Load settings from YAML file"""
        try:
            with open(settings_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Failed to load settings", error=str(e), path=settings_path)
            return {}
            
    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        pass
            
    def validate_lead(self, lead: LeadProfile) -> ValidationResult:
        """
        Validate a lead profile and return validation result.
        
        Args:
            lead: LeadProfile to validate
            
        Returns:
            ValidationResult with validation status and errors
        """
        log = logger.bind(lead_name=lead.name, lead_company=lead.company)
        log.info("Validating lead")
        
        errors = []
        warnings = []
        
        # Validate required fields (make role optional for more lenient validation)
        if not lead.name or len(lead.name.strip()) < 2:
            errors.append("Name is missing or too short")
            
        if not lead.company or len(lead.company.strip()) < 2:
            errors.append("Company is missing or too short")
            
        # Role is now optional - just add warning if missing
        if not lead.role or len(lead.role.strip()) < 2:
            warnings.append("Role is missing or too short")
            
        # Validate email (but don't fail if email validation fails)
        if lead.email and self.email_validation:
            try:
                validate_email(lead.email)
            except EmailNotValidError as e:
                warnings.append(f"Email format may be invalid: {str(e)}")
                
        # Validate phone number (more lenient - just normalize, don't fail)
        if lead.phone_number and self.phone_validation:
            try:
                # Try multiple region defaults for international numbers
                parsed = None
                for region in ["US", "DE", "GB", "FR", None]:
                    try:
                        parsed = phonenumbers.parse(lead.phone_number, region)
                        if phonenumbers.is_valid_number(parsed):
                            break
                    except NumberParseException:
                        continue
                        
                if not parsed or not phonenumbers.is_valid_number(parsed):
                    warnings.append("Phone number format is unusual but will be normalized")
            except Exception:
                warnings.append("Could not parse phone number format")
                
        # Validate LinkedIn URL
        if lead.linkedin and self.url_validation:
            if "linkedin.com/in/" not in lead.linkedin.lower():
                errors.append("Invalid LinkedIn URL format. Must contain 'linkedin.com/in/'")
                
        # Validate company domain
        if lead.company_domain and self.url_validation:
            if not self._is_valid_domain(lead.company_domain):
                errors.append("Invalid company domain format")
                
        # Check confidence score
        if lead.confidence_score < self.confidence_threshold:
            warnings.append(f"Low confidence score: {lead.confidence_score:.2f} < {self.confidence_threshold}")
            
        # Determine validity
        is_valid = len(errors) == 0
        
        log.info(
            "Validation completed",
            is_valid=is_valid,
            error_count=len(errors),
            warning_count=len(warnings)
        )
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            normalized_lead=None,  # Will be set after normalization
        )
        
    def normalize_data(self, lead: LeadProfile) -> LeadProfile:
        """
        Normalize lead data (capitalization, whitespace, URL formats).
        
        Args:
            lead: LeadProfile to normalize
            
        Returns:
            Normalized LeadProfile
        """
        log = logger.bind(lead_name=lead.name)
        log.info("Normalizing lead data")
        
        # Create a copy to avoid modifying original
        normalized = lead.model_copy(deep=True)
        
        # Normalize name
        if normalized.name:
            normalized.name = self._normalize_name(normalized.name)
            
        # Normalize role
        if normalized.role:
            normalized.role = self._normalize_role(normalized.role)
            
        # Normalize company
        if normalized.company:
            normalized.company = self._normalize_company(normalized.company)
            
        # Normalize email
        if normalized.email:
            normalized.email = normalized.email.lower().strip()
            
        # Normalize domain
        if normalized.company_domain:
            normalized.company_domain = self._normalize_domain(normalized.company_domain)
            
        # Normalize phone
        if normalized.phone_number:
            normalized.phone_number = self._normalize_phone(normalized.phone_number)
            
        # Normalize LinkedIn
        if normalized.linkedin:
            normalized.linkedin = self._normalize_linkedin(normalized.linkedin)
            
        log.info("Data normalization completed")
        return normalized
        
    def calculate_quality_score(self, lead: LeadProfile) -> float:
        """
        Calculate overall quality score for a lead.
        
        Args:
            lead: LeadProfile to score
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        # Field completeness (40% weight)
        fields = ["name", "role", "linkedin", "company", "company_domain", "email", "phone_number"]
        populated_fields = sum(1 for field in fields if getattr(lead, field, None))
        completeness_score = populated_fields / len(fields)
        
        # Validation pass rate (30% weight)
        validation_result = self.validate_lead(lead)
        validation_score = 1.0 if validation_result.is_valid else 0.0
        
        # Confidence score (30% weight)
        confidence_score = lead.confidence_score
        
        # Calculate weighted score (rebalanced to weight confidence_score more heavily)
        quality_score = (
            completeness_score * 0.3 +  # Reduced from 0.4
            validation_score * 0.2 +    # Reduced from 0.3
            confidence_score * 0.5      # Increased from 0.3
        )
        
        return quality_score
        
    def validate_and_normalize_batch(self, leads: List[LeadProfile]) -> List[LeadProfile]:
        """
        Validate and normalize a batch of leads.
        
        Args:
            leads: List of LeadProfile instances
            
        Returns:
            List of validated and normalized leads
        """
        if not leads:
            logger.warning("No leads provided for validation")
            return []
            
        log = logger.bind(total_leads=len(leads))
        log.info("Starting batch validation")
        
        start_time = time.time()
        
        validated_leads = []
        validation_stats = {
            "total": len(leads),
            "valid": 0,
            "invalid": 0,
            "low_confidence": 0,
            "avg_quality_score": 0.0
        }
        
        for lead in leads:
            # Validate
            validation_result = self.validate_lead(lead)
            
            if not validation_result.is_valid:
                validation_stats["invalid"] += 1
                log.warning(
                    "Lead validation failed",
                    lead_name=lead.name,
                    errors=validation_result.errors
                )
                continue
                
            # Check confidence threshold
            if lead.confidence_score < self.confidence_threshold:
                validation_stats["low_confidence"] += 1
                log.warning(
                    "Lead below confidence threshold",
                    lead_name=lead.name,
                    confidence=lead.confidence_score,
                    threshold=self.confidence_threshold
                )
                continue
                
            # Normalize
            normalized_lead = self.normalize_data(lead)
            
            # Calculate quality score
            quality_score = self.calculate_quality_score(normalized_lead)
            normalized_lead.confidence_score = quality_score  # Update confidence with quality score
            
            validated_leads.append(normalized_lead)
            validation_stats["valid"] += 1
            
        # Calculate average quality score
        if validated_leads:
            validation_stats["avg_quality_score"] = sum(
                lead.confidence_score for lead in validated_leads
            ) / len(validated_leads)
            
        total_duration = time.time() - start_time
        
        log.info(
            "Batch validation completed",
            valid_count=validation_stats["valid"],
            invalid_count=validation_stats["invalid"],
            low_confidence_count=validation_stats["low_confidence"],
            avg_quality_score=validation_stats["avg_quality_score"],
            duration=total_duration
        )
        
        return validated_leads
        
    def _normalize_name(self, name: str) -> str:
        """Normalize name (title case)"""
        return " ".join(word.capitalize() for word in name.split())
        
    def _normalize_role(self, role: str) -> str:
        """Normalize role (title case, remove extra spaces)"""
        return " ".join(word.capitalize() for word in role.split())
        
    def _normalize_company(self, company: str) -> str:
        """Normalize company (title case, remove legal suffixes)"""
        company = company.strip()
        suffixes = ["inc", "ltd", "llc", "gmbh", "corp", "corporation", "limited"]
        for suffix in suffixes:
            company = company.replace(f" {suffix}", "").replace(f" {suffix}.", "")
        return " ".join(word.capitalize() for word in company.split())
        
    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain (lowercase, remove protocol and www)"""
        domain = domain.lower().strip()
        domain = domain.replace("https://", "").replace("http://", "").replace("www.", "")
        return domain.split("/")[0]
        
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone to E.164 format"""
        try:
            # Try with US default
            parsed = phonenumbers.parse(phone, "US")
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                
            # Try without region
            parsed = phonenumbers.parse(phone, None)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                
            return phone
        except NumberParseException:
            # Return original if parsing fails
            return phone
            
    def _normalize_linkedin(self, linkedin: str) -> str:
        """Normalize LinkedIn URL (ensure https protocol)"""
        linkedin = linkedin.strip()
        if not linkedin.startswith("http"):
            linkedin = "https://" + linkedin
        return linkedin
        
    def _is_valid_domain(self, domain: str) -> bool:
        """Validate domain format"""
        # Basic domain pattern
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, domain))