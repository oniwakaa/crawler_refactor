import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel, Field

from models.lead import LeadProfile
from tools.firecrawl_client import FirecrawlClient
from tools.linkedin_contact_url_builder import LinkedInContactURLBuilder
from tools.contact_data_extractor import ContactDataExtractor
from tools.llama_wrapper import LlamaWrapper

logger = structlog.get_logger()

# Define project root
PROJECT_ROOT = Path(__file__).parent.parent

class EmailMatchModel(BaseModel):
    email: Optional[str] = Field(None, description="The best matching email address")
    confidence_score: float = Field(
        ..., description="Confidence score between 0.0 and 1.0"
    )
    reasoning: str = Field(..., description="Reasoning for the selection")


class EmailDiscoveryAgent:
    """
    Agent responsible for discovering contact emails through a multi-layer strategy.
    
    Layers (in order of priority):
    1. LinkedIn Contact Info (confidence: 0.9) - Highest confidence
    2. LinkedIn Profile Content (confidence: 0.8) - High confidence
    3. Company Website (confidence: 0.7) - Medium confidence
    4. Email Pattern Generation (confidence: 0.3) - Fallback
    """

    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.firecrawl_client: Optional[FirecrawlClient] = None
        self.llama_wrapper: Optional[LlamaWrapper] = None

        models_config = self.settings.get("models", {})
        self.model_name = models_config.get(
            "enricher", "hf.co/unsloth/SmolLM3-3B-GGUF:Q4_K_M"
        )
        self.ollama_host = models_config.get("ollama_host", "http://localhost:11434")
        
        # Email discovery configuration
        email_config = self.settings.get("email_discovery", {})
        self.layers_config = email_config.get("layers", {})
        self.enabled_layers = email_config.get("enabled_layers", [1, 2, 3, 4])

    async def __aenter__(self):
        self.firecrawl_client = FirecrawlClient()
        self.llama_wrapper = LlamaWrapper(ollama_host=self.ollama_host)
        self.llama_wrapper = LlamaWrapper(ollama_host=self.ollama_host)
        await self.firecrawl_client.__aenter__()
        await self.llama_wrapper.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.firecrawl_client:
            await self.firecrawl_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.llama_wrapper:
            await self.llama_wrapper.__aexit__(exc_type, exc_val, exc_tb)

    async def discover_email(self, lead: LeadProfile) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Multi-layer email discovery strategy.
        
        Args:
            lead: LeadProfile to discover email for
            
        Returns:
            Tuple of (email, metadata_dict) where metadata contains:
            - source: Which layer found the email (1-4)
            - confidence: Confidence score (0.0-1.0)
            - layer: Layer number (1-4)
            - layers_attempted: List of layers that were tried
        """
        log = logger.bind(name=lead.name)
        log.info("Starting multi-layer email discovery", 
                 company=lead.company, 
                 linkedin_url=lead.linkedin,
                 company_domain=lead.company_domain)
        
        metadata = {
            "status": "failed",
            "layers_attempted": [],
            "stopping_layer": None
        }
        
        # Layer 1: LinkedIn Contact Info (highest confidence)
        if 1 in self.enabled_layers and lead.linkedin:
            log.info("Attempting Layer 1: LinkedIn Contact Info", layer=1, confidence=0.9)
            metadata["layers_attempted"].append(1)
            
            result = await self._discover_from_linkedin_contact(lead)
            if result.get("status") == "success" and result.get("email"):
                log.info("✓ Email found via Layer 1 (LinkedIn Contact)", 
                        email=result.get("email"), confidence=0.9)
                return result.get("email"), {
                    "status": "success",
                    "source": "linkedin_contact",
                    "confidence": 0.9,
                    "layer": 1,
                    "layers_attempted": [1],
                    "stopping_layer": 1
                }
        
        # Layer 2: LinkedIn Profile Content (high confidence)
        if 2 in self.enabled_layers and lead.linkedin:
            log.info("Attempting Layer 2: LinkedIn Profile Content", layer=2, confidence=0.8)
            metadata["layers_attempted"].append(2)
            
            result = self._discover_from_linkedin_profile_content(lead)
            if result.get("status") == "success" and result.get("email"):
                log.info(f"✓ Email found via Layer 2 (Profile Content): {result.get('email')}", confidence=0.8)
                return result.get("email"), {
                    "status": "success",
                    "source": "linkedin_profile",
                    "confidence": 0.8,
                    "layer": 2,
                    "layers_attempted": metadata["layers_attempted"],
                    "stopping_layer": 2
                }
            
            log.info("No email found in LinkedIn profile content", layer=2)
        
        # Layer 3: Company Website (medium confidence)
        if 3 in self.enabled_layers and lead.company_domain:
            log.info("Attempting Layer 3: Company Website", layer=3, confidence=0.7)
            metadata["layers_attempted"].append(3)
        
            result = await self._discover_from_company_website(lead)
            if result.get("status") == "success" and result.get("email"):
                confidence = result.get("confidence", 0.7)  # Default layer 3 confidence
                log.info(f"✓ Email found via Layer 3 (Company Website): {result.get('email')}", confidence=confidence)
                return result.get("email"), {
                        "status": "success",
                        "source": "company_website",
                        "confidence": confidence,
                        "layer": 3,
                        "layers_attempted": metadata["layers_attempted"], # Use current list
                        "stopping_layer": 3
                    }
        
        # Layer 4: Email Pattern Generation (fallback - lowest confidence)
        if 4 in self.enabled_layers and lead.company_domain and lead.name:
            log.info("Attempting Layer 4: Email Pattern Generation", layer=4, confidence=0.3)
            metadata["layers_attempted"].append(4)
        
            result = self._discover_via_pattern_generation(lead)
            
            if result.get("status") == "success" and result.get("email"):
                log.info(f"✓ Email generated via Layer 4 (Pattern): {result.get('email')} (VERIFICATION NEEDED)", 
                        confidence=0.3, warning="GENERATED - REQUIRES VERIFICATION")
                return result.get("email"), {
                    "status": "success",
                    "source": "pattern_generated",
                    "confidence": 0.3,
                    "layer": 4,
                    "layers_attempted": metadata["layers_attempted"],
                    "stopping_layer": 4,
                    "warning": "GENERATED - REQUIRES MANUAL VERIFICATION"
                }
        
        # All layers failed
        log.info(
            "✗ Email discovery failed - all layers exhausted", 
            layers_attempted=metadata["layers_attempted"]
        )
        metadata["status"] = "failed"
        metadata["reason"] = "all_layers_exhausted"
        return None, metadata
    
    async def _discover_from_linkedin_contact(self, lead: LeadProfile) -> Dict[str, Any]:
        """
        Layer 1: Discover email from LinkedIn contact info overlay.
        
        Args:
            lead: LeadProfile with LinkedIn URL
            
        Returns:
            Dict with status and email if found
        """
        log = logger.bind(linkedin_url=lead.linkedin)
        
        # Check if we already have emails from ContentExtractor (Phase 3 integration)
        if lead.metadata and lead.metadata.get("all_emails"):
            emails = lead.metadata.get("all_emails")
            log.info("Using cached emails from LinkedIn contact info", count=len(emails), emails=emails)
            return {"status": "success", "email": emails[0]}
        
        try:
            # Build contact info URL
            contact_url = LinkedInContactURLBuilder.build_contact_info_url(lead.linkedin)
            if not contact_url:
                log.warning("Could not build contact info URL")
                return {"status": "failed", "email": None, "reason": "invalid_url"}
            
            log.info("Scraping LinkedIn contact info page", contact_url=contact_url)
            
            log.info("Skipping legacy contact info scraping (auth required)")
            return {"status": "skipped", "email": None, "reason": "legacy_auth_removed"}
                
        except Exception as e:
            log.error("LinkedIn contact scraping failed", error=str(e))
            return {"status": "failed", "email": None, "reason": str(e)}
    
    def _discover_from_linkedin_profile_content(self, lead: LeadProfile) -> Dict[str, Any]:
        """
        Layer 2: Extract email from LinkedIn profile markdown content.
        
        Args:
            lead: LeadProfile with raw_markdown content
            
        Returns:
            Dict with status and email if found
        """
        log = logger.bind(linkedin_url=lead.linkedin)
        
        # Check if we already have emails from ContentExtractor (Layer 2 support)
        if lead.metadata and lead.metadata.get("profile_emails"):
            emails = lead.metadata.get("profile_emails")
            log.info("Using cached emails from LinkedIn profile content", count=len(emails), emails=emails)
            return {"status": "success", "email": emails[0]}
        
        try:
            # Check if profile content is available
            if not hasattr(lead, 'raw_markdown') or not lead.raw_markdown:
                log.info("No profile content available for email extraction")
                return {"status": "skipped", "email": None, "reason": "no_content"}
            
            # Extract emails from profile content
            emails = ContactDataExtractor.extract_emails_from_text(lead.raw_markdown)
            if not emails:
                log.info("No emails found in LinkedIn profile content")
                return {"status": "failed", "email": None, "reason": "no_emails"}
            
            log.info("Found emails in LinkedIn profile content", count=len(emails), emails=emails)
            return {"status": "success", "email": emails[0]}
            
        except Exception as e:
            log.error("Email extraction from profile failed", error=str(e))
            return {"status": "failed", "email": None, "reason": str(e)}
    
    async def _discover_from_company_website(self, lead: LeadProfile) -> Dict[str, Any]:
        """
        Layer 3: Discover email from company website contact pages.
        
        Args:
            lead: LeadProfile with company_domain
            
        Returns:
            Dict with status, email, and confidence if found
        """
        log = logger.bind(company=lead.company, domain=lead.company_domain)
        
        try:
            # Find contact pages via search
            pages_to_scrape = await self._find_contact_pages(
                lead.company, lead.company_domain
            )
            
            if not pages_to_scrape:
                log.warning("No contact pages found via search")
                return {"status": "failed", "email": None, "reason": "no_contact_pages"}
            
            # Scrape found pages using Firecrawl
            results = await self.firecrawl_client.batch_scrape(pages_to_scrape)
            
            # Extract emails and phones from content
            all_emails = set()
            all_phones = set()
            
            for result in results:
                if result.get("markdown"):
                    content = result.get("markdown", "")
                    # Extract emails
                    emails = self._extract_emails_from_text(content)
                    all_emails.update(emails)
                    # Extract phones
                    phones = self._extract_phones_from_text(content)
                    all_phones.update(phones)
            
            log.info(
                "Website scrape completed",
                email_count=len(all_emails),
                phone_count=len(all_phones)
            )
            
            if not all_emails:
                log.info("No emails found on website")
                return {"status": "failed", "email": None, "reason": "no_emails"}
            
            # Match email to lead
            best_email, confidence, reasoning = await self._match_email(
                lead, list(all_emails)
            )
            
            if best_email and confidence >= 0.3:  # Layer 3 minimum confidence
                log.info("Email matched to lead from website", 
                        email=best_email, match_confidence=confidence)
                return {
                    "status": "success",
                    "email": best_email,
                    "confidence": confidence
                }
            else:
                log.info("No matching email found with acceptable confidence")
                return {"status": "failed", "email": None, "reason": "low_confidence"}
                
        except Exception as e:
            log.error("Company website email discovery failed", error=str(e))
            return {"status": "failed", "email": None, "reason": str(e)}
    
    def _discover_via_pattern_generation(self, lead: LeadProfile) -> Dict[str, Any]:
        """
        Layer 4: Generate email using common patterns as fallback.
        
        Args:
            lead: LeadProfile with name and company_domain
            
        Returns:
            Dict with status and generated email
        """
        log = logger.bind(name=lead.name, company_domain=lead.company_domain)
        
        try:
            if not lead.name or not lead.company_domain:
                log.warning("Cannot generate email - missing name or domain")
                return {"status": "failed", "email": None, "reason": "missing_data"}
            
            # Extract first name and last name
            name_parts = lead.name.split()
            if len(name_parts) < 2:
                log.warning(f"Name '{lead.name}' doesn't appear to have both first and last name")
                return {"status": "failed", "email": None, "reason": "invalid_name_format"}
            
            first_name = name_parts[0]
            last_name = name_parts[-1]  # Use last part as last name
            
            # Clean domain
            domain = lead.company_domain
            if domain.startswith("http"):
                domain = domain.split("/")[2]  # Extract domain from URL
            if domain.startswith("www."):
                domain = domain[4:]  # Remove www.
            
            # Common email patterns (in order of likelihood)
            patterns = [
                f"{first_name}.{last_name}@{domain}",  # john.doe@company.com
                f"{first_name}{last_name}@{domain}",    # johndoe@company.com
                f"{first_name[0]}.{last_name}@{domain}",  # j.doe@company.com
                f"{first_name[0]}{last_name}@{domain}",    # jdoe@company.com
                f"{first_name}_{last_name}@{domain}",      # john_doe@company.com
                f"{first_name}-{last_name}@{domain}",      # john-doe@company.com
                f"{first_name[:3]}.{last_name}@{domain}",  # joh.doe@company.com (if long first name)
            ]
            
            # Convert to lowercase
            patterns = [pattern.lower() for pattern in patterns]
            
            log.info("Generated email patterns", count=len(patterns), patterns=patterns[:3])
        
            # For now, return the first pattern
            # In a production system, you might want to:
            # 1. Try to verify against the company's email server
            # 2. Use an email validation API
            # 3. Track which patterns are most successful
            generated_email = patterns[0]
            
            log.warning(
                f"GENERATED EMAIL (REQUIRES MANUAL VERIFICATION): {generated_email}",
                warning="THIS EMAIL IS GENERATED, NOT DISCOVERED - VERIFY BEFORE USE"
            )
            
            return {
                "status": "success",
                "email": generated_email,
                "warning": "GENERATED_PATTERN_REQUIRES_VERIFICATION"
            }
        
        except Exception as e:
            log.error("Pattern generation failed", error=str(e))
        return {"status": "failed", "email": None, "reason": str(e)}

    async def _find_contact_pages(self, company_name: str, domain: str) -> List[str]:
        """
        Find contact pages using improved Firecrawl search patterns.
        Uses multiple search strategies for better coverage.
        """
        log = logger.bind(company_name=company_name, domain=domain)
        log.info("Finding contact pages with improved search patterns")
        
        all_urls = []
        
        # Strategy 1: Domain-specific contact page search
        domain_clean = (
            domain.replace("https://", "")
            .replace("http://", "")
            .replace("www.", "")
            .split("/")[0]
        )
        
        # Try primary domain-specific search queries
        domain_queries = [
            f"site:{domain_clean} contact",
            f"site:{domain_clean} about",
            f"site:{domain_clean} impressum",  # German legal pages
        ]
        
        for query in domain_queries:
            try:
                urls = await self.firecrawl_client.search(query, max_results=2)
                all_urls.extend(urls)
                log.debug("Domain search results", query=query, urls_found=len(urls))
                
                # Early exit if we found enough relevant URLs
                if len(all_urls) >= 3:
                    break
            except Exception as e:
                log.warning("Domain search failed", query=query, error=str(e))
        
        # Only try company queries if we have few results
        if len(all_urls) < 2:
            # Strategy 2: Company name + contact keywords
            company_queries = [
                f"{company_name} contact email",
                f"{company_name} team",
            ]
            
            for query in company_queries:
                try:
                    urls = await self.firecrawl_client.search(query, max_results=2)
                    all_urls.extend(urls)
                    log.debug("Company search results", query=query, urls_found=len(urls))
                    if len(all_urls) >= 4:
                        break
                except Exception as e:
                    log.warning("Company search failed", query=query, error=str(e))
        
        # Strategy 3: Filter and prioritize URLs
        relevant_urls = []
        seen_urls = set()
        
        # Contact page keywords
        contact_keywords = [
            "contact", "about", "team", "impressum", "imprint",
            "support", "help", "reach", "get-in-touch", "connect"
        ]
        
        for url in all_urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            url_lower = url.lower()
            
            # High priority: URLs on company domain with contact keywords
            if domain_clean in url_lower and any(kw in url_lower for kw in contact_keywords):
                relevant_urls.insert(0, url)  # Insert at beginning
            # Medium priority: URLs on company domain
            elif domain_clean in url_lower:
                relevant_urls.append(url)
            # Low priority: URLs with contact keywords (might be directories)
            elif any(kw in url_lower for kw in contact_keywords):
                relevant_urls.append(url)
        
        # Always include homepage as fallback if not already included
        homepage = domain if domain.startswith("http") else f"https://{domain}"
        if homepage not in seen_urls:
            relevant_urls.insert(0, homepage)
        
        # Remove duplicates and limit to top 5
        final_urls = []
        for url in relevant_urls:
            if url not in final_urls:
                final_urls.append(url)
            if len(final_urls) >= 5:
                break
        
        log.info("Contact pages found", total_urls=len(final_urls), urls=final_urls)
        return final_urls

    def _extract_emails_from_text(self, text: str) -> List[str]:
        """Extract emails using regex with support for obfuscated patterns."""
        # PHASE 3: Preprocess text to handle obfuscated emails
        # Common obfuscation patterns:
        # - "contact [at] company [dot] com"
        # - "contact(at)company(dot)com"
        # - "contact @ company . com"

        original_length = len(text)

        # Replace obfuscated @ symbols
        text = text.replace("[at]", "@")
        text = text.replace("(at)", "@")
        text = text.replace(" at ", "@")
        text = text.replace(" AT ", "@")

        # Replace obfuscated dots
        text = text.replace("[dot]", ".")
        text = text.replace("(dot)", ".")
        text = text.replace(" dot ", ".")
        text = text.replace(" DOT ", ".")

        # Improved email regex
        pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        matches = re.findall(pattern, text)

        logger.debug(
            "Email extraction", text_length=original_length, matches_found=len(matches)
        )

        # Filter out common junk
        junk = [
            "example.com",
            "domain.com",
            "email.com",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            "wixpress.com",
            "sentry.io",
            "u.s.",
            "yourcompany.com",
            "name@",
        ]
        valid_emails = []

        for email in matches:
            email = email.lower()
            # Basic validation
            if len(email) < 6 or len(email) > 100:
                continue
            if any(j in email for j in junk):
                continue
            valid_emails.append(email)

        logger.info(
            "Emails extracted",
            total_matches=len(matches),
            valid_emails=len(valid_emails),
            emails=valid_emails[:5],
        )  # Log first 5 for debugging

        return valid_emails

    def _extract_phones_from_text(self, text: str) -> List[str]:
        """Extract phone numbers using regex."""
        # Regex for international and local formats
        # Matches: +49 123 456789, 030 123456, (030) 123456, etc.
        # Be careful not to match dates or other numbers

        phones = set()

        # Pattern 1: International E.164-ish (e.g., +49 30 123456)
        # + followed by 1-3 digits (country code), then space/dash, then digits
        pattern_intl = r"\+(?:[0-9] ?){6,14}[0-9]"
        matches_intl = re.findall(pattern_intl, text)
        for p in matches_intl:
            phones.add(p.strip())

        # Pattern 2: German/Local formats (e.g., 030/123456 or 030-123456)
        # Must start with 0, followed by digits, separator, digits. Min length 8.
        pattern_local = r"\b0[1-9][0-9]{1,4}[-/ ][0-9]{3,}"
        matches_local = re.findall(pattern_local, text)
        for p in matches_local:
            # Filter out likely dates (e.g. 01/01/2023)
            if re.match(r"\d{2}/\d{2}/\d{4}", p):
                continue
            phones.add(p.strip())

        return list(phones)

    async def _match_email(
        self, lead: LeadProfile, emails: List[str]
    ) -> Tuple[Optional[str], float, str]:
        """Match discovered emails to the lead using LLM."""
        prompt_path = PROJECT_ROOT / "config/prompts/enricher_email_discovery.txt"
        if not prompt_path.exists():
            # Fallback prompt if file missing
            system_prompt = "You are an expert at matching emails to people."
        else:
            with open(prompt_path, "r") as f:
                system_prompt = f.read()

        match_prompt = f"""{system_prompt}

Task: Identify the best email address for the lead from the list of discovered emails.

Lead Information:
Name: {lead.name}
Role: {lead.role}
Company: {lead.company}

Discovered Emails:
{json.dumps(emails, indent=2)}

Instructions:
1. Look for emails that match the lead's name (e.g., firstname.lastname@, f.lastname@).
2. If no personal email is found, look for a role-based email that fits (e.g., press@ for a PR person).
3. If only generic emails (info@, contact@) are found, select the most relevant one but with lower confidence.
4. Return null if no plausible match is found.

Return JSON with:
- email: The selected email or null
- confidence_score: 0.0 to 1.0 (High > 0.8 for name match, Medium > 0.5 for role match, Low < 0.4 for generic)
- reasoning: Brief explanation

JSON Response:"""

        try:
            result = await self.llama_wrapper.structured_extract(
                prompt=match_prompt,
                schema=EmailMatchModel,
                model=self.model_name,
                temperature=0.1,
            )
            return result.email, result.confidence_score, result.reasoning
        except Exception as e:
            logger.error("Email matching failed", error=str(e))
            return None, 0.0, str(e)
    
    def _extract_emails_from_linkedin_profile(self, linkedin_url: str) -> List[str]:
        """
        Extract emails directly from LinkedIn profile text using regex patterns.
        This is a fallback method for when contact page search fails.
        
        Args:
            linkedin_url: LinkedIn profile URL
            
        Returns:
            List of email addresses found in the profile
        """
        log = logger.bind(linkedin_url=linkedin_url)
        log.info("Extracting emails from LinkedIn profile")
        
        try:
            # Fetch the LinkedIn profile content
            # Note: This would require the LinkedIn profile to be already scraped
            # For now, we'll implement the regex extraction logic
            # In practice, this would be called with the profile content
            
            # This method assumes the profile content is available
            # In a real implementation, you might need to fetch the profile first
            return []
            
        except Exception as e:
            log.error("Failed to extract emails from LinkedIn profile", error=str(e))
            return []
    
    def _extract_emails_from_text_content(self, text_content: str) -> List[str]:
        """
        Enhanced email extraction from text content with better pattern recognition.
        
        Args:
            text_content: Text content to search for emails
            
        Returns:
            List of email addresses found
        """
        if not text_content:
            return []
            
        # Enhanced email patterns based on Context7 research
        email_patterns = [
            # Standard email pattern
            r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
            # Emails with subdomains
            r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\.[a-zA-Z]{2,}\b',
            # Emails with common TLDs
            r'\b[a-zA-Z0-9._%+-]+@(?:[a-zA-Z0-9-]+\.)+(?:com|org|net|edu|gov|mil|io|co|de|uk|fr|de|us|ca|au)\b',
        ]
        
        all_emails = set()
        
        for pattern in email_patterns:
            try:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                for email in matches:
                    email_lower = email.lower()
                    
                    # Enhanced filtering
                    if self._is_valid_email(email_lower):
                        all_emails.add(email_lower)
                        
            except Exception as e:
                logger.debug("Email pattern failed", pattern=pattern, error=str(e))
                continue
        
        return list(all_emails)
    
    def _is_valid_email(self, email: str) -> bool:
        """
        Enhanced email validation with better filtering.
        
        Args:
            email: Email address to validate
            
        Returns:
            True if email appears valid
        """
        # Basic length checks
        if len(email) < 6 or len(email) > 100:
            return False
            
        # Must contain @ and at least one dot after @
        if '@' not in email or '.' not in email.split('@')[-1]:
            return False
            
        # Filter out common junk patterns
        junk_patterns = [
            'example.com', 'domain.com', 'email.com', 'test.com',
            'yourcompany.com', 'company.com', 'placeholder',
            'wixpress.com', 'sentry.io', 'u.s.',
            'png', 'jpg', 'jpeg', 'gif', 'svg',
            'name@', 'user@', 'admin@', 'webmaster@'
        ]
        
        for junk in junk_patterns:
            if junk in email:
                return False
                
        # Check for reasonable structure
        local_part, domain = email.split('@', 1)
        
        # Local part should have at least one character before any special chars
        if len(local_part) < 1:
            return False
            
        # Domain should have reasonable structure
        if len(domain) < 4:
            return False
            
        # No consecutive dots
        if '..' in email:
            return False
            
        return True
