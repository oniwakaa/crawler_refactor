import asyncio
import structlog
import re
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
from pydantic import BaseModel, Field

from tools.firecrawl_client import FirecrawlClient
from tools.llama_wrapper import LlamaWrapper

logger = structlog.get_logger()

# Define project root
PROJECT_ROOT = Path(__file__).parent.parent

class DomainValidationModel(BaseModel):
    confidence_score: float = Field(..., description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(..., description="Reasoning for the score")

class CompanyDomainAgent:
    """
    Agent responsible for discovering company domains.
    Searches for company website and validates the match.
    """
    
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self.firecrawl_client: Optional[FirecrawlClient] = None
        self.llama_wrapper: Optional[LlamaWrapper] = None
        
        models_config = self.settings.get("models", {})
        self.model_name = models_config.get("enricher", "hf.co/unsloth/SmolLM3-3B-GGUF:Q4_K_M")
        self.ollama_host = models_config.get("ollama_host", "http://localhost:11434")
        
        # Domain cache to avoid repeated lookups
        self._domain_cache: Dict[str, Tuple[str, float, Dict[str, Any]]] = {}
        
    async def __aenter__(self):
        self.firecrawl_client = FirecrawlClient()
        self.llama_wrapper = LlamaWrapper(ollama_host=self.ollama_host)
        await self.firecrawl_client.__aenter__()
        await self.llama_wrapper.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.firecrawl_client:
            await self.firecrawl_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.llama_wrapper:
            await self.llama_wrapper.__aexit__(exc_type, exc_val, exc_tb)
            
    async def find_company_domain(self, company_name: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Find the official website domain for a company using extended timeout and LLM fallback.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Tuple of (domain, metadata)
        """
        if not company_name or company_name.lower() in ["unknown", "unknown company", "none"]:
            return None, {"status": "skipped", "reason": "invalid_company_name"}
            
        # Check cache first
        cache_key = company_name.lower().strip()
        if cache_key in self._domain_cache:
            cached_domain, cached_score, cached_metadata = self._domain_cache[cache_key]
            logger.info("Domain found in cache", domain=cached_domain, score=cached_score)
            return cached_domain, {
                "status": "success",
                "method": "cache",
                "confidence": cached_score,
                **cached_metadata
            }
            
        log = logger.bind(company_name=company_name)
        log.info("Searching for company domain with extended timeout")
        
        metadata = {
            "status": "failed",
            "stages": [],
            "candidates": [],
            "method": "unknown"
        }
        
        try:
            # Stage 1: Extended Firecrawl Search (Primary)
            log.info("Stage 1: Extended Firecrawl search")
            try:
                async with asyncio.timeout(30):  # Reduced timeout to 30 seconds
                    query = f"{company_name} official website"
                    urls = await self.firecrawl_client.search_for_domain(query)
                    metadata["stages"].append("firecrawl_search")
                    
                    if urls:
                        # Take top 3 candidates
                        candidates = urls[:3]
                        best_domain = None
                        best_score = 0.0
                        best_metadata = {}
                        
                        # Validate candidates
                        for url in candidates:
                            try:
                                from urllib.parse import urlparse
                                domain = urlparse(url).netloc
                                if not domain:
                                    domain = url
                                    
                                # Fetch homepage content for validation
                                content_result = await self.firecrawl_client.fetch_homepage(url)
                                content_excerpt = content_result.get("markdown", "")[:500]
                                title = content_result.get("metadata", {}).get("title", "")
                                
                                score, reasoning = await self._validate_domain(company_name, url, title, content_excerpt)
                                
                                candidate_metadata = {
                                    "url": url,
                                    "score": score,
                                    "reasoning": reasoning
                                }
                                metadata["candidates"].append(candidate_metadata)
                                
                                if score > best_score:
                                    best_score = score
                                    best_domain = domain
                                    best_metadata = candidate_metadata
                                    
                            except Exception as e:
                                log.warning("Failed to validate candidate", url=url, error=str(e))
                                continue
                        
                        if best_score > 0.7:
                            # Cache the successful result
                            self._domain_cache[cache_key] = (best_domain, best_score, best_metadata)
                            
                            log.info("Domain found via Firecrawl", domain=best_domain, score=best_score)
                            metadata.update({
                                "status": "success",
                                "method": "firecrawl_search",
                                "selected_domain": best_domain,
                                "confidence": best_score,
                                "best_candidate": best_metadata
                            })
                            return best_domain, metadata
                        else:
                            log.info("Firecrawl search: No domain met confidence threshold", best_score=best_score)
                            metadata["firecrawl_best_score"] = best_score
                    else:
                        log.warning("Firecrawl search: No URLs found")
                        metadata["firecrawl_reason"] = "no_search_results"
                        
            except TimeoutError:
                log.warning("Firecrawl search timed out after 30 seconds, attempting LLM fallback")
                metadata["firecrawl_reason"] = "timeout"
            except Exception as e:
                log.warning("Firecrawl search failed", error=str(e))
                metadata["firecrawl_reason"] = "error"
                metadata["firecrawl_error"] = str(e)
            
            # Stage 2: LLM-Based Domain Inference (Fallback)
            log.info("Stage 2: LLM-based domain inference fallback")
            try:
                inferred_domain, inference_confidence = await self._infer_domain_from_company_name(company_name)
                metadata["stages"].append("llm_inference")
                
                if inferred_domain and inference_confidence > 0.5:
                    # Cache the inferred result with lower confidence
                    self._domain_cache[cache_key] = (inferred_domain, inference_confidence, {"method": "llm_inference"})
                    
                    log.info("Domain inferred via LLM", domain=inferred_domain, confidence=inference_confidence)
                    metadata.update({
                        "status": "success",
                        "method": "llm_inference",
                        "selected_domain": inferred_domain,
                        "confidence": inference_confidence,
                        "reasoning": f"LLM-inferred domain with {inference_confidence:.2f} confidence"
                    })
                    return inferred_domain, metadata
                else:
                    log.info("LLM inference: No confident domain found", confidence=inference_confidence)
                    metadata["llm_reason"] = "low_confidence"
                    metadata["llm_confidence"] = inference_confidence
                    
            except Exception as e:
                log.error("LLM domain inference failed", error=str(e))
                metadata["llm_reason"] = "error"
                metadata["llm_error"] = str(e)
            
            # Stage 3: Complete failure
            log.error("All domain discovery methods failed")
            metadata.update({
                "status": "failed",
                "reason": "all_methods_failed",
                "final_reason": "No confident domain found via Firecrawl search or LLM inference"
            })
            return None, metadata
                
        except Exception as e:
            log.error("Domain discovery failed with unexpected error", error=str(e))
            metadata.update({
                "status": "failed",
                "reason": "unexpected_error",
                "error": str(e)
            })
            return None, metadata
            
    async def _validate_domain(self, company_name: str, url: str, title: str, content: str) -> Tuple[float, str]:
        """Validate if a domain matches the company using LLM."""
        prompt_path = PROJECT_ROOT / "config/prompts/enricher_domain_validation.txt"
        if not prompt_path.exists():
            return 0.0, "Prompt missing"
            
        with open(prompt_path, 'r') as f:
            system_prompt = f.read()
            
        validation_prompt = f"""{system_prompt}

Company Name: {company_name}
URL: {url}
Page Title: {title}
Content Excerpt: {content}

Validate this match.
JSON Response:"""

        try:
            result = await self.llama_wrapper.structured_extract(
                prompt=validation_prompt,
                schema=DomainValidationModel,
                model=self.model_name,
                temperature=0.1,
                max_tokens=1024  # Ensure sufficient tokens for validation
            )
            return result.confidence_score, result.reasoning
        except Exception as e:
            logger.error("Validation failed", error=str(e))
            return 0.0, str(e)
    
    async def _infer_domain_from_company_name(self, company_name: str) -> Tuple[Optional[str], float]:
        """
        Infer domain from company name using LLM when Firecrawl search fails.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Tuple of (inferred_domain, confidence_score)
        """
        log = logger.bind(company_name=company_name)
        log.info("Inferring domain from company name")
        
        # Create inference prompt
        inference_prompt = f"""Given the company name "{company_name}", infer the most likely official website domain.

Rules:
1. Convert company name to a realistic domain name
2. Use .com as default TLD unless the company name suggests otherwise (e.g., German company -> .de)
3. Remove common legal suffixes (GmbH, Inc, Ltd, Corp, etc.)
4. Handle spaces and special characters appropriately
5. Return only the domain name (e.g., "techcorp.com"), not the full URL

Examples:
- "TechCorp GmbH" -> "techcorp.de"
- "Global Solutions Inc" -> "globalsolutions.com"
- "Berlin Startups" -> "berlinstartups.com"

Company: "{company_name}"
Domain:"""

        try:
            response = await self.llama_wrapper.generate(
                prompt=inference_prompt,
                model=self.model_name,
                temperature=0.2,
                max_tokens=1024  # Increased from 256 to prevent truncation
            )
            
            # Clean and validate the response
            domain = response.strip().lower()
            
            # Remove common prefixes if present
            if domain.startswith("www."):
                domain = domain[4:]
            if domain.startswith("https://"):
                domain = domain[8:]
            if domain.startswith("http://"):
                domain = domain[7:]
            if domain.endswith("/"):
                domain = domain[:-1]
                
            # Basic domain validation
            if self._is_valid_domain_format(domain):
                # Apply heuristics for confidence scoring
                confidence = self._calculate_inference_confidence(company_name, domain)
                log.info("Domain inferred successfully", domain=domain, confidence=confidence)
                return domain, confidence
            else:
                log.warning("LLM inferred invalid domain format", domain=domain)
                return None, 0.0
                
        except Exception as e:
            log.error("LLM domain inference failed", error=str(e))
            return None, 0.0
    
    def _is_valid_domain_format(self, domain: str) -> bool:
        """
        Validate basic domain format using regex.
        
        Args:
            domain: Domain string to validate
            
        Returns:
            True if domain format is valid
        """
        if not domain or len(domain) < 4 or len(domain) > 63:
            return False
            
        # Basic domain pattern: letters, numbers, hyphens, dots
        # Must contain at least one dot and end with a TLD
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        
        # Additional check for TLD
        if '.' not in domain:
            return False
            
        return bool(re.match(pattern, domain))
    
    def _calculate_inference_confidence(self, company_name: str, domain: str) -> float:
        """
        Calculate confidence score for LLM-inferred domain based on heuristics.
        
        Args:
            company_name: Original company name
            domain: Inferred domain
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.6  # Base confidence for LLM inference
        
        # Boost for exact name match
        company_clean = re.sub(r'[^a-zA-Z0-9]', '', company_name.lower())
        domain_clean = re.sub(r'[^a-zA-Z0-9]', '', domain.split('.')[0].lower())
        
        if company_clean in domain_clean or domain_clean in company_clean:
            confidence += 0.1
            
        # Boost for common TLDs
        common_tlds = ['.com', '.de', '.org', '.net', '.io']
        if any(domain.endswith(tld) for tld in common_tlds):
            confidence += 0.05
            
        # Penalty for very generic domains
        generic_terms = ['company', 'business', 'corp', 'corporation', 'service', 'services']
        if any(term in domain_clean for term in generic_terms):
            confidence -= 0.1
            
        # Penalty for very short or very long domains
        if len(domain) < 8 or len(domain) > 30:
            confidence -= 0.05
            
        return min(max(confidence, 0.3), 0.8)  # Clamp between 0.3 and 0.8