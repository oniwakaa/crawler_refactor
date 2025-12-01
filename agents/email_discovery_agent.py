import asyncio
import structlog
import json
import re
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from pydantic import BaseModel, Field

from tools.crawl4ai_client import Crawl4AIClient
from tools.firecrawl_client import FirecrawlClient
from tools.llama_wrapper import LlamaWrapper
from models.lead import LeadProfile

logger = structlog.get_logger()

class EmailMatchModel(BaseModel):
    email: Optional[str] = Field(None, description="The best matching email address")
    confidence_score: float = Field(..., description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(..., description="Reasoning for the selection")

class EmailDiscoveryAgent:
    """
    Agent responsible for discovering contact emails.
    Scrapes company website contact pages and extracts emails.
    """
    
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.crawl4ai_client: Optional[Crawl4AIClient] = None
        self.firecrawl_client: Optional[FirecrawlClient] = None
        self.llama_wrapper: Optional[LlamaWrapper] = None
        
        models_config = self.settings.get("models", {})
        self.model_name = models_config.get("enricher", "hf.co/unsloth/SmolLM3-3B-GGUF:Q4_K_M")
        self.ollama_host = models_config.get("ollama_host", "http://localhost:11434")
        
    async def __aenter__(self):
        self.crawl4ai_client = Crawl4AIClient()
        self.firecrawl_client = FirecrawlClient()
        self.llama_wrapper = LlamaWrapper(ollama_host=self.ollama_host)
        await self.crawl4ai_client.__aenter__()
        await self.firecrawl_client.__aenter__()
        await self.llama_wrapper.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.crawl4ai_client:
            await self.crawl4ai_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.firecrawl_client:
            await self.firecrawl_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.llama_wrapper:
            await self.llama_wrapper.__aexit__(exc_type, exc_val, exc_tb)
            
    async def discover_email(self, lead: LeadProfile) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Discover email and phone for a lead.
        
        Args:
            lead: LeadProfile with company_domain
            
        Returns:
            Tuple of (email, metadata)
        """
        if not lead.company_domain:
            return None, {"status": "skipped", "reason": "no_domain"}
            
        log = logger.bind(lead_name=lead.name, domain=lead.company_domain)
        log.info("Starting contact discovery")
        
        metadata = {
            "status": "failed",
            "stages": [],
            "found_emails": [],
            "found_phones": []
        }
        
        try:
            # 1. Find contact pages via search
            pages_to_scrape = await self._find_contact_pages(lead.company, lead.company_domain)
            
            if not pages_to_scrape:
                log.warning("No contact pages found via search")
                metadata["reason"] = "no_contact_pages"
                return None, metadata
                
            # 2. Scrape found pages
            results = await self.crawl4ai_client.batch_fetch(pages_to_scrape)
            metadata["stages"].append("scrape")
            
            # 3. Extract emails and phones from content
            all_emails = set()
            all_phones = set()
            
            for result in results:
                if result.get("fetch_status") == "success":
                    content = result.get("markdown", "")
                    # Extract emails
                    emails = self._extract_emails_from_text(content)
                    all_emails.update(emails)
                    # Extract phones
                    phones = self._extract_phones_from_text(content)
                    all_phones.update(phones)
            
            metadata["found_emails"] = list(all_emails)
            metadata["found_phones"] = list(all_phones)
            
            # Update lead with found phone numbers (side effect, but useful)
            if all_phones and not lead.phone_number:
                # Pick the most likely main number (e.g., landline over mobile if for company)
                # For now, just pick the first one
                lead.phone_number = list(all_phones)[0]
                log.info("Phone number discovered", phone=lead.phone_number)

            if not all_emails:
                log.info("No emails found on website")
                metadata["reason"] = "no_emails_found"
                return None, metadata
                
            # 3. Match email to lead
            best_email, score, reasoning = await self._match_email(lead, list(all_emails))
            metadata["stages"].append("match")
            
            if best_email and score > 0.7:
                log.info("Email discovered", email=best_email, score=score)
                metadata["status"] = "success"
                metadata["confidence"] = score
                metadata["reasoning"] = reasoning
                return best_email, metadata
            else:
                log.info("No matching email found with high confidence")
                metadata["reason"] = "low_confidence_match"
                return None, metadata
                
        except Exception as e:
            log.error("Contact discovery failed", error=str(e))
            metadata["error"] = str(e)
            return None, metadata
            
    async def _find_contact_pages(self, company_name: str, domain: str) -> List[str]:
        """
        Find contact pages using Firecrawl search.
        Replaces blind URL guessing with targeted search.
        """
        query = f"{company_name} contact email phone support"
        urls = await self.firecrawl_client.search(query, max_results=5)
        
        # Filter URLs to ensure they belong to the domain (or are relevant social/directory if needed, but let's stick to domain for now)
        # Actually, we want to find pages ON the domain that look like contact pages.
        # But search might return other sites.
        # Let's filter for the company domain if possible, or just take the best ones.
        
        # Better strategy: Search specifically for pages on the domain?
        # "site:domain.com contact" might be better if supported.
        # Firecrawl search supports general queries.
        
        # Let's try to filter the results to match the domain loosely
        # or just trust the search relevance for "{Company} contact"
        
        relevant_urls = []
        domain_clean = domain.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
        
        keywords = ["contact", "about", "team", "impressum", "imprint", "support", "help"]
        
        for url in urls:
            # Prioritize URLs on the company domain
            if domain_clean in url:
                relevant_urls.append(url)
            # Also include if it looks like a contact page and we don't have many
            elif any(k in url.lower() for k in keywords):
                relevant_urls.append(url)
                
        # Always include the homepage as fallback
        homepage = domain if domain.startswith("http") else f"https://{domain}"
        if homepage not in relevant_urls:
            relevant_urls.insert(0, homepage)
            
        return relevant_urls[:5]
        
    def _extract_emails_from_text(self, text: str) -> List[str]:
        """Extract emails using regex with support for obfuscated patterns."""
        # PHASE 3: Preprocess text to handle obfuscated emails
        # Common obfuscation patterns:
        # - "contact [at] company [dot] com"
        # - "contact(at)company(dot)com"
        # - "contact @ company . com"
        
        original_length = len(text)
        
        # Replace obfuscated @ symbols
        text = text.replace('[at]', '@')
        text = text.replace('(at)', '@')
        text = text.replace(' at ', '@')
        text = text.replace(' AT ', '@')
        
        # Replace obfuscated dots
        text = text.replace('[dot]', '.')
        text = text.replace('(dot)', '.')
        text = text.replace(' dot ', '.')
        text = text.replace(' DOT ', '.')
        
        # Improved email regex
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        matches = re.findall(pattern, text)
        
        logger.debug("Email extraction", 
                    text_length=original_length,
                    matches_found=len(matches))
        
        # Filter out common junk
        junk = [
            "example.com", "domain.com", "email.com", ".png", ".jpg", ".jpeg", ".gif", 
            "wixpress.com", "sentry.io", "u.s.", "yourcompany.com", "name@"
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
        
        logger.info("Emails extracted", 
                   total_matches=len(matches),
                   valid_emails=len(valid_emails),
                   emails=valid_emails[:5])  # Log first 5 for debugging
            
        return valid_emails

    def _extract_phones_from_text(self, text: str) -> List[str]:
        """Extract phone numbers using regex."""
        # Regex for international and local formats
        # Matches: +49 123 456789, 030 123456, (030) 123456, etc.
        # Be careful not to match dates or other numbers
        
        phones = set()
        
        # Pattern 1: International E.164-ish (e.g., +49 30 123456)
        # + followed by 1-3 digits (country code), then space/dash, then digits
        pattern_intl = r'\+(?:[0-9] ?){6,14}[0-9]'
        matches_intl = re.findall(pattern_intl, text)
        for p in matches_intl:
            phones.add(p.strip())
            
        # Pattern 2: German/Local formats (e.g., 030/123456 or 030-123456)
        # Must start with 0, followed by digits, separator, digits. Min length 8.
        pattern_local = r'\b0[1-9][0-9]{1,4}[-/ ][0-9]{3,}'
        matches_local = re.findall(pattern_local, text)
        for p in matches_local:
            # Filter out likely dates (e.g. 01/01/2023)
            if re.match(r'\d{2}/\d{2}/\d{4}', p):
                continue
            phones.add(p.strip())
            
        return list(phones)
        
    async def _match_email(self, lead: LeadProfile, emails: List[str]) -> Tuple[Optional[str], float, str]:
        """Match discovered emails to the lead using LLM."""
        prompt_path = Path("config/prompts/enricher_email_discovery.txt")
        if not prompt_path.exists():
            # Fallback prompt if file missing
            system_prompt = "You are an expert at matching emails to people."
        else:
            with open(prompt_path, 'r') as f:
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
                temperature=0.1
            )
            return result.email, result.confidence_score, result.reasoning
        except Exception as e:
            logger.error("Email matching failed", error=str(e))
            return None, 0.0, str(e)
