import os
import json
import time
from typing import Optional, Type, Any, Dict, List
from pydantic import BaseModel
import structlog
import httpx

logger = structlog.get_logger()

class LlamaWrapper:
    """
    Unified wrapper for Ollama cloud models and local GGUF models via llama-cpp-python.
    Supports both structured output and regular text generation.
    """
    
    def __init__(self, ollama_host: str = "http://localhost:11434"):
        """
        Initialize LlamaWrapper.
        
        Args:
            ollama_host: Ollama server host URL
        """
        self.ollama_host = ollama_host
        self.ollama_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
        self.loaded_models: Dict[str, Any] = {}  # Cache for loaded models
        self.model_stats: Dict[str, Dict[str, Any]] = {}  # Track usage stats
        
    async def __aenter__(self):
        """Async context manager entry."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.ollama_client.aclose()
        
    async def generate(
        self, 
        prompt: str, 
        model: str, 
        temperature: float = 0.7, 
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """
        Generate text using specified model.
        
        Args:
            prompt: Input prompt
            model: Model name (e.g., "gpt-oss:120b-cloud" or local GGUF path)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text response
        """
        log = logger.bind(model=model, prompt_length=len(prompt))
        start_time = time.time()
        
        try:
            if self._is_local_gguf(model):
                response = await self._generate_local(prompt, model, temperature, max_tokens, **kwargs)
            else:
                response = await self._generate_ollama(prompt, model, temperature, max_tokens, **kwargs)
                
            duration = time.time() - start_time
            self._update_stats(model, duration, len(prompt), len(response))
            
            log.info("Generation completed", duration=duration, response_length=len(response))
            return response
            
        except Exception as e:
            log.error("Generation failed", error=str(e))
            raise
            
    async def structured_extract(
        self,
        prompt: str,
        schema: Type[BaseModel],
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        **kwargs
    ) -> BaseModel:
        """
        Extract structured data using specified model and schema.
        
        Args:
            prompt: Input prompt with extraction instructions
            schema: Pydantic model class for structured output
            model: Model name
            temperature: Sampling temperature (lower for structured output)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional generation parameters
            
        Returns:
            Instance of the schema model with extracted data
        """
        log = logger.bind(model=model, schema=schema.__name__)
        start_time = time.time()
        
        try:
            if self._is_local_gguf(model):
                # Local models may not support native structured output
                response = await self._extract_with_prompt_engineering(
                    prompt, schema, model, temperature, max_tokens, **kwargs
                )
            else:
                # Try Ollama native structured output first
                try:
                    response = await self._extract_ollama_structured(
                        prompt, schema, model, temperature, max_tokens, **kwargs
                    )
                except Exception as e:
                    log.warning("Ollama structured output failed, falling back to prompt engineering", error=str(e))
                    response = await self._extract_with_prompt_engineering(
                        prompt, schema, model, temperature, max_tokens, **kwargs
                    )
                    
            duration = time.time() - start_time
            # Handle case where response might be a model instance
            if hasattr(response, 'model_dump'):
                response_data = response.model_dump()
                output_length = len(str(response_data))
            else:
                output_length = len(str(response))
                
            self._update_stats(model, duration, len(prompt), output_length)
            
            log.info("Structured extraction completed", duration=duration)
            return response
            
        except Exception as e:
            log.error("Structured extraction failed", error=str(e))
            raise
            
    def _is_local_gguf(self, model: str) -> bool:
        """
        Check if model is a local GGUF file path.
        
        Args:
            model: Model name or path
            
        Returns:
            True if local GGUF model
        """
        # Check if it's a HuggingFace model ID
        if "hf.co/" in model or "huggingface.co/" in model:
            return False
            
        # Check for GGUF extension
        if model.endswith(('.gguf', '.GGUF')):
            return True
            
        # Check if it's a path to an existing file
        if (os.path.sep in model or '/' in model) and os.path.exists(model):
            return True
            
        return False
        
    async def _generate_ollama(
        self, 
        prompt: str, 
        model: str, 
        temperature: float, 
        max_tokens: int,
        **kwargs
    ) -> str:
        """
        Generate text using Ollama API.
        
        Args:
            prompt: Input prompt
            model: Ollama model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            Generated text
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                **kwargs
            },
            "stream": False
        }
        
        # Ensure client is active
        if self.ollama_client.is_closed:
            self.ollama_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))

        response = await self.ollama_client.post(
            f"{self.ollama_host}/api/generate",
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        return result.get("response", "")
        
    async def _generate_local(
        self, 
        prompt: str, 
        model_path: str, 
        temperature: float, 
        max_tokens: int,
        **kwargs
    ) -> str:
        """
        Generate text using local GGUF model via llama-cpp-python.
        
        Args:
            prompt: Input prompt
            model_path: Path to GGUF model file
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            Generated text
        """
        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError("llama-cpp-python not installed. Install with: pip install llama-cpp-python")
            
        # Load or get cached model
        if model_path not in self.loaded_models:
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found: {model_path}")
                
            logger.info("Loading local model", model_path=model_path)
            self.loaded_models[model_path] = Llama(
                model_path=model_path,
                n_ctx=2048,
                verbose=False
            )
            
        model = self.loaded_models[model_path]
        
        # Generate response
        output = model(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        return output["choices"][0]["text"]
        
    async def _extract_ollama_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> BaseModel:
        """
        Extract structured data using Ollama's native structured output.
        
        Args:
            prompt: Input prompt
            schema: Pydantic model class
            model: Ollama model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            Instance of schema model
        """
        # Convert schema to JSON schema
        schema_dict = schema.model_json_schema()
        
        payload = {
            "model": model,
            "prompt": prompt,
            "format": schema_dict,  # Ollama structured output format
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                **kwargs
            },
            "stream": False
        }
        
        response = await self.ollama_client.post(
            f"{self.ollama_host}/api/generate",
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        response_text = result.get("response", "")
        
        # Parse JSON response
        try:
            # Handle potential markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
                
            data = json.loads(response_text)
            return schema(**data)
        except json.JSONDecodeError as e:
            # Try to find JSON object if mixed with text
            try:
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    return schema(**data)
            except Exception:
                pass
                
            logger.error("Failed to parse structured response", error=str(e), response=response_text)
            raise
            
    async def _extract_with_prompt_engineering(
        self,
        prompt: str,
        schema: Type[BaseModel],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> BaseModel:
        """
        Extract structured data using prompt engineering for models without native structured output.
        
        Args:
            prompt: Input prompt
            schema: Pydantic model class
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            Instance of schema model
        """
        # Get schema fields and descriptions
        schema_info = []
        for field_name, field in schema.model_fields.items():
            description = field.description or field_name
            field_type = str(field.annotation)
            schema_info.append(f'"{field_name}": {field_type} - {description}')
            
        schema_str = "{\n" + ",\n".join(schema_info) + "\n}"
        
        # Enhanced prompt for structured extraction
        enhanced_prompt = f"""{prompt}

Extract the information in the following JSON format. Only include fields that are explicitly found in the content. If a field is not available, use null or an empty string.

Schema:
{schema_str}

Return ONLY valid JSON, no additional text or explanations.

JSON Response:"""
        
        # Generate response
        if self._is_local_gguf(model):
            response_text = await self._generate_local(enhanced_prompt, model, temperature, max_tokens, **kwargs)
        else:
            response_text = await self._generate_ollama(enhanced_prompt, model, temperature, max_tokens, **kwargs)
            
        # Clean response text
        response_text = response_text.strip()
        
        # Try to extract JSON if wrapped in code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        # Parse JSON response
        try:
            data = json.loads(response_text)
            return schema(**data)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse structured response from prompt engineering",
                error=str(e),
                response=response_text[:500]  # Log first 500 chars
            )
            raise
            
    def _update_stats(self, model: str, duration: float, input_tokens: int, output_tokens: int):
        """
        Update model usage statistics.
        
        Args:
            model: Model name
            duration: Generation duration in seconds
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        if model not in self.model_stats:
            self.model_stats[model] = {
                "total_calls": 0,
                "total_duration": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0
            }
            
        stats = self.model_stats[model]
        stats["total_calls"] += 1
        stats["total_duration"] += duration
        stats["total_input_tokens"] += input_tokens
        stats["total_output_tokens"] += output_tokens
        
    def get_stats(self, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Get model usage statistics.
        
        Args:
            model: Specific model name, or None for all models
            
        Returns:
            Dictionary with usage statistics
        """
        if model:
            return self.model_stats.get(model, {})
        return self.model_stats
        
    def clear_cache(self):
        """Clear loaded model cache."""
        self.loaded_models.clear()
        logger.info("Cleared model cache")