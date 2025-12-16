import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import structlog
import yaml

from models.lead import LeadProfile
from tools.llama_wrapper import LlamaWrapper
from tools.contact_data_extractor import ContactDataExtractor

logger = structlog.get_logger()

# Define project root
PROJECT_ROOT = Path(__file__).parent.parent

class ContentExtractorAgent:
    """
    Content Extractor agent responsible for extracting structured lead data from web content.
    Uses LlamaWrapper for LLM-based extraction with confidence scoring.
    """

    def __init__(self, settings_path: str = str(PROJECT_ROOT / "config/settings.yaml")):
        """
        Initialize ContentExtractorAgent.

        Args:
            settings_path: Path to settings YAML file
        """
        self.settings = self._load_settings(settings_path)
        self.llama_wrapper: Optional[LlamaWrapper] = None

        # Load configuration
        extraction_config = self.settings.get("extraction", {})
        self.confidence_threshold = extraction_config.get("confidence_threshold", 0.7)
        self.target_fields = extraction_config.get("fields", [])

        # Load all prompt templates for content-type-specific extraction
        self.prompts = self._load_all_prompts()

        # Model configuration
        models_config = self.settings.get("models", {})
        self.model_name = models_config.get("extractor", "gpt-oss:20b-cloud")

    def _load_settings(self, settings_path: str) -> Dict[str, Any]:
        """Load settings from YAML file"""
        try:
            with open(settings_path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Failed to load settings", error=str(e), path=settings_path)
            return {}

    def _load_all_prompts(self) -> Dict[str, str]:
        """Load all content-type-specific prompt templates"""
        prompt_files = {
            "profile": PROJECT_ROOT / "config/prompts/extractor_lead_profile.txt",
            "team_page": PROJECT_ROOT / "config/prompts/extractor_team_page.txt",
            "article": PROJECT_ROOT / "config/prompts/extractor_article.txt",
            "generic": PROJECT_ROOT / "config/prompts/extractor_generic.txt",
        }

        prompts = {}
        for content_type, file_path in prompt_files.items():
            try:
                with open(file_path, "r") as f:
                    prompts[content_type] = f.read()
                logger.debug(f"Loaded {content_type} prompt template")
            except Exception as e:
                logger.error(
                    f"Failed to load prompt template {file_path}", error=str(e)
                )
                prompts[content_type] = ""  # Fallback to empty string

        return prompts

    def detect_content_type(self, markdown: str, url: str = "") -> str:
        """
        Detect the type of content based on markdown and URL patterns.

        Args:
            markdown: Markdown content to analyze
            url: Source URL for additional context

        Returns:
            Content type: "profile", "team_page", "article", "job_board", or "unknown"
        """
        markdown_lower = markdown.lower()
        url_lower = url.lower()

        # Check for LinkedIn profile indicators FIRST (highest priority for detection)
        if "linkedin.com/in/" in url_lower:
            logger.info("Content type detected: profile", indicator="linkedin.com/in")
            return "profile"

        # Check for LinkedIn profile patterns in content (structured content)
        linkedin_indicators = [
            "experience:",
            "education:",
            "connections",
            "followers",
            "recommendations",
        ]

        for indicator in linkedin_indicators:
            if indicator in markdown_lower:
                logger.info("Content type detected: profile", indicator=indicator)
                return "profile"

        # Check for job board indicators (only if not already identified as LinkedIn profile)
        job_indicators = [
            "apply now",
            "submit resume",
            "job description",
            "salary range",
            "benefits package",
            "career opportunities",
            "hiring now",
            "we are hiring",
            "join our team",
            "employment",
            "work with us",
        ]

        for indicator in job_indicators:
            if indicator in markdown_lower:
                logger.info("Content type detected: job_board", indicator=indicator)
                return "job_board"

        # Check for LinkedIn profile patterns (structured content)
        linkedin_indicators = [
            "experience:",
            "education:",
            "connections",
            "followers",
            "recommendations",
        ]

        for indicator in linkedin_indicators:
            if indicator in markdown_lower:
                logger.info("Content type detected: profile", indicator=indicator)
                return "profile"

        # Check for team page indicators (require multiple context clues)
        team_indicators = [
            "meet the team",
            "about us",
            "team members",
            "management team",
            "leadership team",
            "our leadership",
        ]

        for indicator in team_indicators:
            if indicator in markdown_lower:
                logger.info("Content type detected: team_page", indicator=indicator)
                return "team_page"

        # Check for article indicators
        article_indicators = [
            "published on",
            "read more",
            "author:",
            "byline",
            "originally published",
            "updated:",
            "news",
            "press release",
            "interview with",
            "said",
            "told",
            "explained",
        ]

        content_length = len(markdown)
        for indicator in article_indicators:
            if indicator in markdown_lower:
                logger.info("Content type detected: article", indicator=indicator)
                return "article"

        # Content length heuristic: very long content likely articles
        if content_length > 15000:
            logger.info(
                "Content type detected: article (length heuristic)",
                length=content_length,
            )
            return "article"

        # Default to unknown
        logger.info("Content type detected: unknown", length=content_length)
        return "unknown"

    async def __aenter__(self):
        """Async context manager entry"""
        self.llama_wrapper = LlamaWrapper(
            ollama_host=self.settings.get("models", {}).get(
                "ollama_host", "http://localhost:11434"
            )
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Wrapper will be closed by its own context manager
        pass

    def _clean_markdown(self, markdown: str) -> str:
        """
        Clean markdown content by removing JSON blocks and metadata noise.
        For LinkedIn profiles, this now relies on _extract_linkedin_sections
        which is called from _select_extraction_strategy.
        
        This method serves as a general cleaner for non-profile content
        or as a fallback.
        
        Args:
            markdown: Raw markdown content
            
        Returns:
            Cleaned markdown content
        """
        if not markdown:
            return ""
            
        lines = markdown.split('\n')
        cleaned_lines = []
        
        # Patterns to identify JSON/metadata lines
        json_starts = ('{', '}', '[', ']', '`   {', '`   [', '` {', '` [')
        metadata_keys = (
            'request":', 'data":', 'included":', 'meta":', '$type":', 'urn:'
        )
        
        # Keywords that indicate noise
        noise_keywords = [
            "lixTracking", "chameleon", "voyager.dash.segments", "trackingItem"
        ]
        
        in_code_block = False
        
        for line in lines:
            stripped = line.strip()
            
            # Handle code blocks
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                continue
                
            # Skip empty lines
            if not stripped:
                continue
                
            # Check for noise
            if any(noise in stripped for noise in noise_keywords):
                continue
            
            # Skip image links that are likely tracking pixels or icons
            # But keep profile pictures (often have 'profile-displayphoto')
            if stripped.startswith('![') and 'licdn.com' in stripped:
                if 'shrink_' in stripped and 'profile-displayphoto' not in stripped:
                    continue
            
            # Decision logic for JSON/Metadata lines
            is_json_line = stripped.startswith(json_starts) or any(key in stripped for key in metadata_keys)
            
            if is_json_line:
                # In general cleaning, we drop JSON lines to reduce noise
                continue
                
            # If we are in a code block, we treat it similarly to JSON lines
            if in_code_block:
                continue
                
            # Regular text lines are kept
            cleaned_lines.append(line)
            
        return '\n'.join(cleaned_lines)

    def _extract_linkedin_sections(self, markdown: str) -> str:
        """
        Extract key sections from LinkedIn profile markdown.
        Produces a structured output with HEADER, ABOUT, and EXPERIENCE sections.
        
        Args:
            markdown: Raw markdown content (or fit_markdown)
            
        Returns:
            Structured text with labeled sections
        """
        if not markdown:
            return ""
            
        lines = markdown.split('\n')
        
        # Buffers for sections
        header_lines = []
        about_lines = []
        experience_lines = []
        education_lines = []
        
        # State tracking
        current_section = "header" # Start in header
        
        # Markers for section transitions
        # These are common headings in LinkedIn markdown
        section_markers = {
            "about": ["About", "Summary", "Overview", "Background", "Biography"],
            "experience": ["Experience", "Work Experience", "Career History", "Employment History"],
            "education": ["Education", "Academic Background"],
            "skills": ["Skills", "Endorsements", "Skills & Endorsements"],
            "recommendations": ["Recommendations"],
            "interests": ["Interests"],
            "languages": ["Languages"],
            "licenses": ["Licenses & certifications", "Certifications"],
            "projects": ["Projects"],
            "volunteering": ["Volunteering"]
        }
        
        # Helper to check if a line is a section header
        def detect_section(line):
            line_lower = line.lower().strip().replace('#', '').strip()
            for section, markers in section_markers.items():
                if line_lower in [m.lower() for m in markers]:
                    return section
            return None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
                
            # Check for section transition
            # Heuristic: Section headers are often short and match known markers
            if len(stripped) < 50:
                new_section = detect_section(stripped)
                if new_section:
                    current_section = new_section
                    continue # Skip the header line itself in the output? Or keep it? Let's skip to keep it clean.
            
            # Filter noise (JSON, tracking)
            if stripped.startswith(('{', '}', '[', ']')) or 'request":' in stripped or 'lixTracking' in stripped:
                continue
                
            # Add line to appropriate section buffer
            if current_section == "header":
                # Limit header to first 100 lines to avoid capturing too much nav junk
                if len(header_lines) < 100:
                    header_lines.append(stripped)
            elif current_section == "about":
                about_lines.append(stripped)
            elif current_section == "experience":
                experience_lines.append(stripped)
            elif current_section == "education":
                education_lines.append(stripped)
            # We ignore other sections (skills, etc) to keep it compact
            
        # Construct final output
        output_parts = []
        
        if header_lines:
            output_parts.append("HEADER:")
            output_parts.extend(header_lines)
            output_parts.append("") # Spacer
            
        if about_lines:
            output_parts.append("ABOUT:")
            output_parts.extend(about_lines)
            output_parts.append("")
            
        if experience_lines:
            output_parts.append("EXPERIENCE:")
            output_parts.extend(experience_lines)
            output_parts.append("")
            
        if education_lines:
            output_parts.append("EDUCATION:")
            output_parts.extend(education_lines)
            output_parts.append("")
            
        cleaned = '\n'.join(output_parts)
        logger.info(f"LinkedIn section extraction: {len(markdown)} -> {len(cleaned)} chars")
        return cleaned


    async def extract_entities(
        self, markdown: str, schema: Type[LeadProfile], url: str = ""
    ) -> Optional[LeadProfile]:
        """
        Extract structured lead data from markdown content with content-type-aware multi-layer fallback.

        Args:
            markdown: Markdown content to extract from
            schema: LeadProfile schema class
            url: Source URL for content type detection

        Returns:
            LeadProfile instance with extracted data, or None if extraction completely fails
        """
        log = logger.bind(markdown_length=len(markdown))

        # Step 1: Detect content type
        content_type = self.detect_content_type(markdown, url)
        log.info("Content type detection completed", content_type=content_type)

        # DEBUG: Save raw markdown for inspection (only if enabled)
        if self.settings.get("debug_markdown", False):
            try:
                timestamp = int(time.time())
                safe_url = url.replace("/", "_").replace(":", "").replace(".", "_")[-50:] if url else "no_url"
                filename = f"debug_data/markdown_{timestamp}_{content_type}_{safe_url}.md"
                
                # Ensure directory exists
                Path("debug_data").mkdir(exist_ok=True)
                
                with open(filename, "w") as f:
                    f.write(markdown)
                log.info("Saved raw markdown for debugging", filename=filename)
            except Exception as e:
                log.warning("Failed to save debug markdown", error=str(e))

        # Step 2: Skip job boards entirely
        if content_type == "job_board":
            log.info("Skipping job board content")
            return None

        # Step 3: Select appropriate prompt and truncation strategy
        prompt_template, truncated_markdown = self._select_extraction_strategy(
            markdown, content_type
        )

        try:
            # Use already-entered wrapper directly (entered in __aenter__)
            # Layer 1: Try structured extraction with content-specific prompt
            try:
                lead = await self.llama_wrapper.structured_extract(
                    prompt=prompt_template.format(markdown=truncated_markdown),
                    schema=schema,
                    model=self.model_name,
                    temperature=0.1,
                    max_tokens=4096,
                )

                # Handle team page array response
                if content_type == "team_page" and hasattr(lead, "__iter__"):
                    # For team pages, if we get an array, take the first valid lead
                    if isinstance(lead, list) and lead:
                        lead = lead[0]  # Use first lead from array
                    elif not lead:
                        raise ValueError("Team page extraction returned empty array")

                # Validate minimum required fields
                if not lead.name:
                    log.warning(
                        "Structured extraction missing required fields",
                        name=lead.name,
                        company=lead.company,
                    )
                    raise ValueError("Missing required field: name")

                if not lead.company:
                     log.info("Lead extracted without company name", name=lead.name)

                # Calculate confidence score based on content type
                confidence = self._calculate_confidence_based_on_type(
                    lead, markdown, content_type
                )
                lead.confidence_score = confidence

                # Extract emails from main profile content (Layer 2 support)
                profile_emails = ContactDataExtractor.extract_emails_from_text(markdown)
                if profile_emails:
                    if not lead.metadata:
                        lead.metadata = {}
                    lead.metadata["profile_emails"] = profile_emails
                    log.info("Extracted emails from profile content", count=len(profile_emails))

                log.info(
                    "Structured extraction successful",
                    content_type=content_type,
                    confidence=confidence,
                    fields_populated=self._count_populated_fields(lead),
                )

                return lead

            except Exception as e:
                log.warning(
                    f"Structured extraction failed for {content_type}, trying fallback",
                    error=str(e),
                )

                # Layer 2: Try minimal extraction (just name and company)
                minimal_lead = await self._extract_minimal_lead(
                    truncated_markdown, self.llama_wrapper
                )
                if minimal_lead:
                    log.info(
                        "Minimal extraction successful",
                        name=minimal_lead.name,
                        company=minimal_lead.company,
                        confidence=minimal_lead.confidence_score,
                    )
                    
                    # Extract emails from main profile content (Layer 2 support)
                    profile_emails = ContactDataExtractor.extract_emails_from_text(truncated_markdown)
                    if profile_emails:
                        if not minimal_lead.metadata:
                            minimal_lead.metadata = {}
                        minimal_lead.metadata["profile_emails"] = profile_emails
                        log.info("Extracted emails from minimal profile content", count=len(profile_emails))
                    
                        
                    return minimal_lead

                # Layer 3: Try regex-based role extraction if role is missing
                if minimal_lead and not minimal_lead.role:
                    log.info("Attempting regex-based role extraction fallback")
                    role_with_regex = self._extract_role_with_regex(truncated_markdown)
                    if role_with_regex:
                        minimal_lead.role = role_with_regex["role"]
                        minimal_lead.confidence_score = min(
                            minimal_lead.confidence_score + 0.1, 0.7
                        )  # Boost confidence but cap at 0.7 for regex
                        log.info(
                            "Regex role extraction successful",
                            role=role_with_regex["role"],
                            confidence=minimal_lead.confidence_score,
                            pattern=role_with_regex["pattern"],
                        )
                        return minimal_lead

                # Layer 4: Complete failure
                log.error("All extraction methods failed", content_type=content_type)
                return None

        except Exception as e:
            log.error(
                "Entity extraction failed completely",
                error=str(e),
                error_type=type(e).__name__,
            )
            return None


    def _select_extraction_strategy(
        self, markdown: str, content_type: str
    ) -> tuple[str, str]:
        """
        Select appropriate prompt template and truncation strategy based on content type.

        Args:
            markdown: Original markdown content
            content_type: Detected content type

        Returns:
            Tuple of (prompt_template, truncated_markdown)
        """
        # Get prompt template
        prompt_template = self.prompts.get(
            content_type, self.prompts.get("generic", "")
        )

        # Apply specific cleaning/extraction based on content type
        if content_type == "profile":
            # Use structured section extraction for LinkedIn profiles
            # This produces compact, labeled text (HEADER, ABOUT, EXPERIENCE)
            cleaned_markdown = self._extract_linkedin_sections(markdown)
            
            # Truncation strategy for profiles
            # Since we are now extracting specific sections, the content should be much smaller.
            # We can be generous with the limit, but still protect against huge outputs.
            max_length = 20000 
            if len(cleaned_markdown) > max_length:
                truncated_markdown = cleaned_markdown[:max_length]
                logger.info(
                    "Truncated large profile content",
                    original_length=len(cleaned_markdown),
                    truncated_length=len(truncated_markdown),
                    content_type=content_type,
                )
            else:
                truncated_markdown = cleaned_markdown
                
        else:
            # For other types, use general cleaning
            cleaned_markdown = self._clean_markdown(markdown)
            original_length = len(cleaned_markdown)

            if content_type == "team_page":
                # Team pages usually concise, keep full content up to 15KB
                max_length = 15000
                if original_length > max_length:
                    truncated_markdown = cleaned_markdown[:max_length]
                    logger.info(
                        "Truncated large team page",
                        original_length=original_length,
                        truncated_length=len(truncated_markdown),
                    )
                else:
                    truncated_markdown = cleaned_markdown

            elif content_type == "article":
                # Articles: intro usually has author info, truncate to first 8KB
                max_length = 8000
                truncated_markdown = cleaned_markdown[:max_length]
                if original_length > max_length:
                    logger.info(
                        "Truncated article content",
                        original_length=original_length,
                        truncated_length=len(truncated_markdown),
                    )

            else:  # unknown
                # Unknown content: be conservative, keep first 5KB
                max_length = 5000
                truncated_markdown = cleaned_markdown[:max_length]
                if original_length > max_length:
                    logger.info(
                        "Truncated unknown content",
                        original_length=original_length,
                        truncated_length=len(truncated_markdown),
                    )

        return prompt_template, truncated_markdown


    def _calculate_confidence_based_on_type(
        self, lead: LeadProfile, markdown: str, content_type: str
    ) -> float:
        """
        Calculate confidence score adjusted for content type.

        Args:
            lead: Extracted LeadProfile
            markdown: Original markdown content
            content_type: Detected content type

        Returns:
            Content-type-adjusted confidence score
        """
        base_confidence = self._calculate_confidence(lead, markdown)

        # Adjust confidence based on content type expectations
        if content_type == "profile":
            # Profiles should have high confidence due to structured data
            return min(base_confidence * 1.1, 1.0)  # 10% boost, cap at 1.0
        elif content_type == "team_page":
            # Team pages have minimal data but it's reliable
            return base_confidence  # No adjustment needed
        elif content_type == "article":
            # Articles are noisy, reduce confidence slightly
            return base_confidence * 0.9  # 10% reduction
        else:  # unknown
            # Unknown content gets confidence penalty
            return base_confidence * 0.8  # 20% reduction

    async def _extract_minimal_lead(
        self, markdown: str, wrapper: LlamaWrapper
    ) -> Optional[LeadProfile]:
        """
        Fallback: Extract only name and company with simple prompt.

        Args:
            markdown: Content to extract from
            wrapper: LlamaWrapper instance

        Returns:
            LeadProfile with minimal data or None
        """
        simple_prompt = f"""Extract just the person's name and company name from this content.
If you find a person's name and their company, return JSON in this exact format:
{{"name": "Person Name", "company": "Company Name"}}

If you cannot find both a person's name AND a company name, return:
{{"name": null, "company": null}}

Content:
{markdown[:1000]}

Return ONLY the JSON, no other text."""

        try:
            response = await wrapper.generate(
                prompt=simple_prompt,
                model=self.model_name,
                temperature=0.1,
                max_tokens=200,
            )

            # Parse JSON response
            import json
            import re

            # Clean response
            response = response.strip()

            # Try to extract JSON if wrapped in text
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            # Try to find JSON object
            json_match = re.search(r"\{.*?\}", response, re.DOTALL)
            if json_match:
                response = json_match.group(0)

            data = json.loads(response)

            # Validate we have required fields
            name = data.get("name")
            company = data.get("company")

            if not name or not company or name == "null" or company == "null":
                logger.debug("Minimal extraction found no valid data", data=data)
                return None

            # Create minimal lead
            return LeadProfile(
                name=name,
                company=company,
                confidence_score=0.35,  # Low confidence for minimal data
            )

        except Exception as e:
            logger.warning("Minimal extraction failed", error=str(e))
            return None

    async def batch_extract(self, pages: List[Dict[str, Any]]) -> List[LeadProfile]:
        """
        Extract leads from multiple pages concurrently.

        Args:
            pages: List of page dictionaries with markdown content

        Returns:
            List of LeadProfile instances (filtered by confidence threshold)
        """
        if not pages:
            logger.warning("No pages provided for batch extraction")
            return []

        log = logger.bind(page_count=len(pages))
        log.info("Starting batch extraction")

        start_time = time.time()

        # Process pages concurrently with semaphore for rate limiting
        semaphore = asyncio.Semaphore(5)  # Limit concurrent extractions

        async def extract_with_semaphore(page: Dict[str, Any]) -> Optional[LeadProfile]:
            async with semaphore:
                try:
                    # Prefer fit_markdown if available and not empty, otherwise use raw markdown
                    markdown = page.get("fit_markdown") or page.get("markdown", "")
                    
                    if not markdown:
                        logger.warning("Empty markdown content", url=page.get("url"))
                        return None
                    # Pass URL for content type detection
                    url = page.get("url", "")
                    lead = await self.extract_entities(markdown, LeadProfile, url)

                    # Handle None return
                    if lead is None:
                        return None

                    # Add source URL if available
                    if url:
                        lead.source_url = url

                    return lead

                except Exception as e:
                    log.warning(
                        "Extraction failed for page", url=page.get("url"), error=str(e)
                    )
                    return None

        # Run concurrent extractions
        tasks = [extract_with_semaphore(page) for page in pages]
        results = await asyncio.gather(*tasks)

        # Filter out None results
        valid_leads = [lead for lead in results if lead is not None]

        # Apply confidence threshold from configuration
        confidence_threshold = self.confidence_threshold
        filtered_leads = [
            lead
            for lead in valid_leads
            if lead.confidence_score >= confidence_threshold
        ]

        # Calculate statistics
        total_duration = time.time() - start_time
        avg_confidence = (
            sum(lead.confidence_score for lead in filtered_leads) / len(filtered_leads)
            if filtered_leads
            else 0.0
        )

        # Field coverage statistics
        field_coverage = self._calculate_field_coverage(filtered_leads)

        log.info(
            "Batch extraction completed",
            total_pages=len(pages),
            successful_extractions=len(valid_leads),
            high_confidence_leads=len(filtered_leads),
            avg_confidence=avg_confidence,
            duration=total_duration,
            field_coverage=field_coverage,
            threshold_used=confidence_threshold,
        )

        return filtered_leads

    def _calculate_confidence(self, lead: LeadProfile, markdown: str) -> float:
        """
        Calculate confidence score for extracted lead based on field completeness.
        Aligned with prompt scoring guidelines.

        Args:
            lead: Extracted LeadProfile
            markdown: Original markdown content

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Start with base score for having required fields
        confidence = 0.0

        # Required fields (name + company) = 0.35 base
        if lead.name and len(lead.name) > 1:
            confidence += 0.175
        if lead.company and len(lead.company) > 1:
            confidence += 0.175

        # Role field adds significant value = +0.2
        if lead.role and len(lead.role) > 1:
            confidence += 0.2

        # Contact fields (each worth 0.1)
        if lead.email and "@" in lead.email:
            confidence += 0.1
        if lead.linkedin and "linkedin.com/in/" in lead.linkedin:
            confidence += 0.1
        if lead.phone_number and len(lead.phone_number) > 5:
            confidence += 0.08
        if lead.company_domain and "." in lead.company_domain:
            confidence += 0.07

        # Content quality bonus (richer content = better extraction)
        if len(markdown) > 1000:
            confidence += 0.05
        elif len(markdown) > 500:
            confidence += 0.03

        # Cap at 1.0
        return min(confidence, 1.0)

    def _count_populated_fields(self, lead: LeadProfile) -> int:
        """Count number of populated fields in lead profile"""
        fields = [
            "name",
            "role",
            "linkedin",
            "company",
            "company_domain",
            "email",
            "phone_number",
        ]
        return sum(1 for field in fields if getattr(lead, field, None))

    def _calculate_field_coverage(self, leads: List[LeadProfile]) -> Dict[str, float]:
        """
        Calculate field coverage statistics.

        Args:
            leads: List of LeadProfile instances

        Returns:
            Dictionary with field coverage percentages
        """
        if not leads:
            return {}

        field_coverage = {}
        fields = [
            "name",
            "role",
            "linkedin",
            "company",
            "company_domain",
            "email",
            "phone_number",
        ]

        for field in fields:
            populated_count = sum(1 for lead in leads if getattr(lead, field, None))
            field_coverage[field] = populated_count / len(leads)

        return field_coverage

    def _handle_extraction_failure(
        self, page: Dict[str, Any], error: Exception
    ) -> None:
        """
        Handle extraction failure gracefully.

        Args:
            page: Page dictionary that failed extraction
            error: Exception that occurred
        """
        logger.warning(
            "Extraction failed for page",
            url=page.get("url"),
            error=str(error),
            markdown_length=len(page.get("markdown", "")),
        )

    def _extract_role_with_regex(self, text: str) -> Optional[Dict[str, str]]:
        """
        Extract role using regex patterns as fallback when LLM extraction fails.

        Args:
            text: Text content to search for roles

        Returns:
            Dictionary with role and pattern info, or None if no match found
        """
        text_lower = text.lower()

        # Comprehensive role patterns based on research from Context7
        role_patterns = [
            # C-level executives
            (
                r"\b(ceo|chief executive officer)\b.*?(?:at|@|of|for)\s+([^,\n.]{2,50})",
                "C-Level",
            ),
            (
                r"\b(cto|chief technology officer)\b.*?(?:at|@|of|for)\s+([^,\n.]{2,50})",
                "C-Level",
            ),
            (
                r"\b(cfo|chief financial officer)\b.*?(?:at|@|of|for)\s+([^,\n.]{2,50})",
                "C-Level",
            ),
            (
                r"\b(cmo|chief marketing officer)\b.*?(?:at|@|of|for)\s+([^,\n.]{2,50})",
                "C-Level",
            ),
            (
                r"\b(coo|chief operating officer)\b.*?(?:at|@|of|for)\s+([^,\n.]{2,50})",
                "C-Level",
            ),
            (
                r"\b(cso|chief security officer)\b.*?(?:at|@|of|for)\s+([^,\n.]{2,50})",
                "C-Level",
            ),
            (
                r"\b(cpo|chief product officer)\b.*?(?:at|@|of|for)\s+([^,\n.]{2,50})",
                "C-Level",
            ),
            # VP/Vice President roles
            (r"\b(vp|vice president)\s+([^,\n.]{2,30})\b", "VP"),
            (r"\bvice\s+president\s+of\s+([^,\n.]{2,30})\b", "VP"),
            (r"\bvice\s+president\s+([^,\n.]{2,30})\b", "VP"),
            # Director roles
            (r"\bdirector\s+of\s+([^,\n.]{2,30})\b", "Director"),
            (r"\bdirector\s+([^,\n.]{2,30})\b", "Director"),
            (r"\b(?:managing|executive)\s+director\b", "Director"),
            # Head of roles
            (r"\bhead\s+of\s+([^,\n.]{2,30})\b", "Head"),
            (r"\bhead\s+([^,\n.]{2,30})\b", "Head"),
            # Founder roles
            (r"\b(founder|co-?founder)\b", "Founder"),
            (r"\b(?:co\s*founder|co-founder)\b", "Founder"),
            # Manager roles
            (r"\b(?:general|senior)\s+manager\b", "Manager"),
            (r"\bmanager\s+of\s+([^,\n.]{2,30})\b", "Manager"),
            # Lead roles
            (r"\b(?:team|technical|product)\s+lead\b", "Lead"),
            (r"\blead\s+([^,\n.]{2,30})\b", "Lead"),
            # Senior roles
            (r"\bsenior\s+([^,\n.]{2,30})\b", "Senior"),
            (r"\bprincipal\s+([^,\n.]{2,30})\b", "Principal"),
            # Common tech roles
            (r"\b(?:software|senior|lead)\s+(?:engineer|developer)\b", "Engineer"),
            (r"\b(?:product|project)\s+manager\b", "Manager"),
            (r"\b(?:data|science)\s+(?:scientist|analyst)\b", "Data"),
        ]

        # Try each pattern
        for pattern, category in role_patterns:
            try:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    # For patterns with groups, extract the role
                    if isinstance(matches[0], tuple):
                        role_text = matches[0][0] if matches[0][0] else matches[0][1]
                    else:
                        role_text = matches[0]

                    # Clean up the role text
                    role_text = role_text.strip().title()

                    # Validate the role is reasonable
                    if len(role_text) >= 2 and len(role_text) <= 50:
                        logger.debug(
                            "Role extracted with regex",
                            role=role_text,
                            pattern=pattern,
                            category=category,
                        )
                        return {
                            "role": role_text,
                            "pattern": pattern,
                            "category": category,
                            "confidence": 0.5 if category == "C-Level" else 0.4,
                        }
            except Exception as e:
                logger.debug("Regex pattern failed", pattern=pattern, error=str(e))
                continue

        # Try simple role title patterns without company context
        simple_role_patterns = [
            r"\b(ceo|chief executive officer)\b",
            r"\b(cto|chief technology officer)\b",
            r"\b(cfo|chief financial officer)\b",
            r"\b(cmo|chief marketing officer)\b",
            r"\b(coo|chief operating officer)\b",
            r"\b(vp|vice president)\b",
            r"\bdirector\b",
            r"\bhead\s+of\b",
            r"\b(founder|co-?founder)\b",
            r"\bmanager\b",
            r"\blead\b",
        ]

        for pattern in simple_role_patterns:
            try:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    # Extract the matched role
                    match = re.search(pattern, text_lower, re.IGNORECASE)
                    role_text = match.group(0).strip().title()

                    # Clean up common variations
                    role_text = re.sub(r"\b(Vp)\b", "VP", role_text)
                    role_text = re.sub(
                        r"\b(Cto|Cfo|Cmo|Coo)\b",
                        lambda m: m.group(0).upper(),
                        role_text,
                    )

                    logger.debug(
                        "Simple role extracted with regex",
                        role=role_text,
                        pattern=pattern,
                    )
                    return {
                        "role": role_text,
                        "pattern": pattern,
                        "category": "Simple",
                        "confidence": 0.3,
                    }
            except Exception as e:
                logger.debug(
                    "Simple regex pattern failed", pattern=pattern, error=str(e)
                )
                continue
        logger.debug("No role found with regex patterns")
        return None


