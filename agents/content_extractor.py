import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import structlog
import yaml

from models.lead import LeadProfile
from tools.llama_wrapper import LlamaWrapper

logger = structlog.get_logger()


class ContentExtractorAgent:
    """
    Content Extractor agent responsible for extracting structured lead data from web content.
    Uses LlamaWrapper for LLM-based extraction with confidence scoring.
    """

    def __init__(self, settings_path: str = "config/settings.yaml"):
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
            "profile": "config/prompts/extractor_lead_profile.txt",
            "team_page": "config/prompts/extractor_team_page.txt",
            "article": "config/prompts/extractor_article.txt",
            "generic": "config/prompts/extractor_generic.txt",
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

        # Check for job board indicators first (highest priority for exclusion)
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

        # Check for LinkedIn profile indicators (most specific)
        if "linkedin.com/in/" in url_lower:
            logger.info("Content type detected: profile", indicator="linkedin.com/in")
            return "profile"

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
                if not lead.name or not lead.company:
                    log.warning(
                        "Structured extraction missing required fields",
                        name=lead.name,
                        company=lead.company,
                    )
                    raise ValueError("Missing required fields: name and company")

                # Calculate confidence score based on content type
                confidence = self._calculate_confidence_based_on_type(
                    lead, markdown, content_type
                )
                lead.confidence_score = confidence

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
                    return minimal_lead

                # Layer 3: Complete failure
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

        original_length = len(markdown)

        # Apply intelligent truncation based on content type
        if content_type == "profile":
            # Truncate large profiles (>15KB) to keep critical first sections
            # LinkedIn profiles: first 10KB contains name, headline, current role, contact
            max_length = 10000
            if original_length > 15000:
                truncated_markdown = markdown[:max_length]
                logger.info(
                    "Truncated large profile content",
                    original_length=original_length,
                    truncated_length=len(truncated_markdown),
                    content_type=content_type,
                )
            else:
                truncated_markdown = markdown

        elif content_type == "team_page":
            # Team pages usually concise, keep full content up to 15KB
            max_length = 15000
            if original_length > max_length:
                truncated_markdown = markdown[:max_length]
                logger.info(
                    "Truncated large team page",
                    original_length=original_length,
                    truncated_length=len(truncated_markdown),
                )
            else:
                truncated_markdown = markdown

        elif content_type == "article":
            # Articles: intro usually has author info, truncate to first 8KB
            max_length = 8000
            truncated_markdown = markdown[:max_length]
            if original_length > max_length:
                logger.info(
                    "Truncated article content",
                    original_length=original_length,
                    truncated_length=len(truncated_markdown),
                )

        else:  # unknown
            # Unknown content: be conservative, keep first 5KB
            max_length = 5000
            truncated_markdown = markdown[:max_length]
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
                    markdown = page.get("markdown", "")
                    if not markdown:
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
