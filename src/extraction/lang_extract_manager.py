"""
LangExtract manager for structured data extraction.

This module provides the core LangExtract integration layer that handles
extraction requests with fallback strategies between local and cloud models.
"""

import asyncio
import time
from typing import Optional, Dict, Any
import logging
from dataclasses import dataclass
from enum import Enum

import langextract
from langextract import ExtractionResult
from pydantic import ValidationError

from .schemas import (
    CompanyProfile, 
    PersonProfile, 
    ExtractionRequest, 
    ExtractionResult as AppExtractionResult
)

logger = logging.getLogger(__name__)


class ExtractionMethod(Enum):
    """Extraction method types."""
    LOCAL_MODEL = "local_model"
    OLLAMA_CLOUD = "ollama_cloud"
    FIRECRAWL = "firecrawl"


@dataclass
class ModelConfig:
    """Configuration for extraction models."""
    local_model: str = "smollm3-thinking"  # Local Ollama model
    cloud_model: str = "llama3.1"  # Ollama Cloud model
    temperature: float = 0.1
    max_tokens: int = 2000
    timeout_seconds: int = 30


class LangExtractManager:
    """
    Manages LangExtract operations with fallback strategies.
    
    This class handles the extraction pipeline:
    1. Primary: Local model via Ollama/llama.cpp
    2. Fallback 1: Ollama Cloud models
    3. Fallback 2: Firecrawl API
    """
    
    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or ModelConfig()
        self._ensure_models_available()
        
    def _ensure_models_available(self):
        """Ensure required models are available."""
        # Check if local model is available
        try:
            import ollama
            models = ollama.list()
            available_models = [model['name'] for model in models['models']]
            
            if self.config.local_model not in available_models:
                logger.warning(f"Local model {self.config.local_model} not found. Available: {available_models}")
                # Could trigger auto-download here if desired
                
        except ImportError:
            logger.warning("Ollama not available - local models will not work")
        except Exception as e:
            logger.error(f"Error checking Ollama models: {e}")
    
    async def extract_company_data(
        self, 
        text_content: str, 
        source_url: Optional[str] = None,
        context_hints: Optional[list] = None
    ) -> AppExtractionResult:
        """
        Extract company information using LangExtract with fallback strategy.
        
        Args:
            text_content: Raw HTML or text content to extract from
            source_url: Original URL where content was sourced from
            context_hints: Additional context to help extraction
            
        Returns:
            AppExtractionResult with extracted company data
        """
        request = ExtractionRequest(
            text_content=text_content,
            extraction_type="company",
            source_url=source_url,
            context_hints=context_hints or []
        )
        
        return await self._extract_with_fallback(request, CompanyProfile)
    
    async def extract_person_data(
        self, 
        text_content: str, 
        source_url: Optional[str] = None,
        context_hints: Optional[list] = None
    ) -> AppExtractionResult:
        """
        Extract person information using LangExtract with fallback strategy.
        
        Args:
            text_content: Raw HTML or text content to extract from
            source_url: Original URL where content was sourced from
            context_hints: Additional context to help extraction
            
        Returns:
            AppExtractionResult with extracted person data
        """
        request = ExtractionRequest(
            text_content=text_content,
            extraction_type="person",
            source_url=source_url,
            context_hints=context_hints or []
        )
        
        return await self._extract_with_fallback(request, PersonProfile)
    
    async def _extract_with_fallback(
        self, 
        request: ExtractionRequest, 
        target_schema: type
    ) -> AppExtractionResult:
        """
        Execute extraction with multi-tier fallback strategy.
        
        Args:
            request: Extraction request
            target_schema: Target Pydantic schema class
            
        Returns:
            AppExtractionResult with extracted data or error info
        """
        start_time = time.time()
        
        # Tier 1: Local model (primary)
        try:
            result = await self._extract_with_local_model(request, target_schema)
            if result.success:
                return result
        except Exception as e:
            logger.warning(f"Local model extraction failed: {e}")
        
        # Tier 2: Ollama Cloud fallback
        try:
            result = await self._extract_with_cloud_model(request, target_schema)
            if result.success:
                return result
        except Exception as e:
            logger.warning(f"Cloud model extraction failed: {e}")
        
        # Tier 3: Firecrawl fallback (returns structured, but less detailed)
        try:
            result = await self._extract_with_firecrawl(request, target_schema)
            if result.success:
                return result
        except Exception as e:
            logger.warning(f"Firecrawl extraction failed: {e}")
        
        # All methods failed
        processing_time = int((time.time() - start_time) * 1000)
        return AppExtractionResult(
            success=False,
            error_message="All extraction methods failed",
            extraction_method="none",
            confidence_score=0.0,
            processing_time_ms=processing_time
        )
    
    async def _extract_with_local_model(
        self, 
        request: ExtractionRequest, 
        target_schema: type
    ) -> AppExtractionResult:
        """Extract using local Ollama model."""
        start_time = time.time()
        
        try:
            # Configure LangExtract for local model
            extraction_config = {
                "model": self.config.local_model,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "provider": "ollama"
            }
            
            # Build the extraction prompt
            prompt = self._build_extraction_prompt(request, target_schema)
            
            # Execute extraction
            result = langextract.extract(
                text=request.text_content,
                schema=target_schema,
                prompt=prompt,
                **extraction_config
            )
            
            # Process result
            processed_data = self._process_langextract_result(result, target_schema)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return AppExtractionResult(
                success=True,
                data=processed_data,
                extraction_method=ExtractionMethod.LOCAL_MODEL.value,
                confidence_score=self._calculate_confidence(processed_data),
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            return AppExtractionResult(
                success=False,
                error_message=f"Local model error: {str(e)}",
                extraction_method=ExtractionMethod.LOCAL_MODEL.value,
                confidence_score=0.0,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
    
    async def _extract_with_cloud_model(
        self, 
        request: ExtractionRequest, 
        target_schema: type
    ) -> AppExtractionResult:
        """Extract using Ollama Cloud model."""
        start_time = time.time()
        
        try:
            # Configure LangExtract for cloud model
            extraction_config = {
                "model": self.config.cloud_model,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "provider": "ollama_cloud"
            }
            
            prompt = self._build_extraction_prompt(request, target_schema)
            
            result = langextract.extract(
                text=request.text_content,
                schema=target_schema,
                prompt=prompt,
                **extraction_config
            )
            
            processed_data = self._process_langextract_result(result, target_schema)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return AppExtractionResult(
                success=True,
                data=processed_data,
                extraction_method=ExtractionMethod.OLLAMA_CLOUD.value,
                confidence_score=self._calculate_confidence(processed_data),
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            return AppExtractionResult(
                success=False,
                error_message=f"Cloud model error: {str(e)}",
                extraction_method=ExtractionMethod.OLLAMA_CLOUD.value,
                confidence_score=0.0,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
    
    async def _extract_with_firecrawl(
        self, 
        request: ExtractionRequest, 
        target_schema: type
    ) -> AppExtractionResult:
        """Extract using Firecrawl as fallback."""
        start_time = time.time()
        
        try:
            # This would integrate with Firecrawl API for structured extraction
            # For now, return a placeholder that indicates Firecrawl would be used
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return AppExtractionResult(
                success=False,  # Firecrawl integration not implemented yet
                error_message="Firecrawl fallback not implemented",
                extraction_method=ExtractionMethod.FIRECRAWL.value,
                confidence_score=0.0,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            return AppExtractionResult(
                success=False,
                error_message=f"Firecrawl error: {str(e)}",
                extraction_method=ExtractionMethod.FIRECRAWL.value,
                confidence_score=0.0,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
    
    def _build_extraction_prompt(self, request: ExtractionRequest, target_schema: type) -> str:
        """
        Build extraction prompt based on schema and context.
        
        Args:
            request: Extraction request
            target_schema: Target schema class
            
        Returns:
            Formatted extraction prompt
        """
        schema_name = target_schema.__name__
        
        base_prompt = f"""
        Extract {schema_name.lower()} information from the following text.
        
        Context hints: {', '.join(request.context_hints) if request.context_hints else 'None'}
        
        Extract ONLY information that is explicitly present in the text. Do not guess or infer.
        For uncertain information, return None rather than making assumptions.
        
        Pay special attention to:
        - Contact information (emails, phone numbers)
        - Company names and website URLs
        - Job titles and names for person profiles
        - Location information
        
        Return the information in the exact JSON format specified by the schema.
        """
        
        return base_prompt
    
    def _process_langextract_result(self, result, target_schema: type) -> Optional[Any]:
        """
        Process LangExtract result into target schema.
        
        Args:
            result: LangExtract result object
            target_schema: Target schema class
            
        Returns:
            Instantiated schema object or None
        """
        try:
            if hasattr(result, 'data'):
                data = result.data
            elif hasattr(result, 'text'):
                # Parse JSON from text result
                import json
                data = json.loads(result.text)
            else:
                return None
            
            # Validate against target schema
            return target_schema(**data)
            
        except (ValidationError, json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error processing LangExtract result: {e}")
            return None
    
    def _calculate_confidence(self, data: Any) -> float:
        """
        Calculate confidence score based on extracted data completeness.
        
        Args:
            data: Extracted schema object
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not data:
            return 0.0
        
        # Count non-null fields
        total_fields = len(data.model_fields)
        filled_fields = 0
        
        for field_name, field_info in data.model_fields.items():
            value = getattr(data, field_name, None)
            if value is not None:
                if isinstance(value, (list, str)):
                    if isinstance(value, list):
                        filled_fields += len(value)
                    else:
                        filled_fields += 1
                else:
                    filled_fields += 1
        
        # Base confidence on field completeness
        base_confidence = min(filled_fields / total_fields, 1.0)
        
        # Boost confidence for critical fields
        critical_fields = ['company_name', 'full_name', 'email', 'website_url']
        critical_filled = sum(1 for field in critical_fields 
                            if hasattr(data, field) and getattr(data, field, None))
        
        critical_bonus = (critical_filled / len(critical_fields)) * 0.3
        
        return min(base_confidence + critical_bonus, 1.0)


# Global instance for use across the application
lang_extract_manager = LangExtractManager()