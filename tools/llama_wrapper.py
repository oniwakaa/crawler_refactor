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
        # Ensure client is ready
        if self.ollama_client.is_closed:
            self.ollama_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
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
        max_retries: int = 2,
        **kwargs
    ) -> BaseModel:
        """
        Extract structured data using specified model and schema with retry logic.
        
        Args:
            prompt: Input prompt with extraction instructions
            schema: Pydantic model class for structured output
            model: Model name
            temperature: Sampling temperature (lower for structured output)
            max_tokens: Maximum tokens to generate
            max_retries: Maximum number of retry attempts (default: 2)
            **kwargs: Additional generation parameters
            
        Returns:
            Instance of the schema model with extracted data
        """
        log = logger.bind(model=model, schema=schema.__name__)
        start_time = time.time()
        last_error = None
        
        # Retry loop - attempt extraction up to max_retries times
        for attempt in range(max_retries):
            try:
                # Modify prompt on retry to emphasize requirements
                current_prompt = prompt
                if attempt > 0:
                    retry_reminder = "\n\nIMPORTANT: You MUST return valid JSON with at least 'name' and 'company' fields. Do not return empty responses."
                    current_prompt = prompt + retry_reminder
                    log.info("Retrying extraction", attempt=attempt + 1, max_retries=max_retries)
                
                if self._is_local_gguf(model):
                    # Local models may not support native structured output
                    response = await self._extract_with_prompt_engineering(
                        current_prompt, schema, model, temperature, max_tokens, **kwargs
                    )
                else:
                    # Try Ollama native structured output first
                    try:
                        response = await self._extract_ollama_structured(
                            current_prompt, schema, model, temperature, max_tokens, **kwargs
                        )
                    except Exception as e:
                        log.warning("Ollama structured output failed, falling back to prompt engineering", 
                                  error=str(e), attempt=attempt + 1)
                        response = await self._extract_with_prompt_engineering(
                            current_prompt, schema, model, temperature, max_tokens, **kwargs
                        )
                
                # Success! Log and return
                duration = time.time() - start_time
                if hasattr(response, 'model_dump'):
                    response_data = response.model_dump()
                    output_length = len(str(response_data))
                else:
                    output_length = len(str(response))
                    
                self._update_stats(model, duration, len(prompt), output_length)
                
                if attempt > 0:
                    log.info("Extraction succeeded on retry", attempt=attempt + 1, duration=duration)
                else:
                    log.info("Structured extraction completed", duration=duration)
                return response
                
            except (ValueError, json.JSONDecodeError) as e:
                # Retryable errors: empty response, JSON parsing failure
                last_error = e
                error_type = type(e).__name__
                log.warning(
                    "Extraction attempt failed with retryable error",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error_type=error_type,
                    error_msg=str(e)[:200]
                )
                
                # If this was the last attempt, we'll raise the error below
                if attempt == max_retries - 1:
                    break
                    
                # Otherwise, continue to next retry
                continue
                
            except Exception as e:
                # Non-retryable errors (network, HTTP, etc.) - fail immediately
                last_error = e
                log.error(
                    "Extraction failed with non-retryable error",
                    attempt=attempt + 1,
                    error_type=type(e).__name__,
                    error=str(e)[:200]
                )
                raise
        
        # All retries exhausted
        duration = time.time() - start_time
        log.error(
            "All extraction attempts failed",
            total_attempts=max_retries,
            duration=duration,
            final_error=str(last_error)[:200]
        )
        raise last_error
            
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
        
        # Client is managed by context manager (__aenter__/__aexit__)
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
        
    def clean_json_response(self, response_text: str) -> str:
        """
        Clean LLM response to ensure valid JSON.
        
        Args:
            response_text: Raw response from LLM
            
        Returns:
            Cleaned JSON string
        """
        # Strip whitespace
        response_text = response_text.strip()
        
        # Handle markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        # Find JSON object or array
        # Look for first { or [ and last } or ]
        start_brace = response_text.find('{')
        start_bracket = response_text.find('[')
        
        start_index = -1
        if start_brace != -1 and start_bracket != -1:
            start_index = min(start_brace, start_bracket)
        elif start_brace != -1:
            start_index = start_brace
        elif start_bracket != -1:
            start_index = start_bracket
            
        if start_index != -1:
            response_text = response_text[start_index:]
            
        # Find end
        end_brace = response_text.rfind('}')
        end_bracket = response_text.rfind(']')
        
        end_index = -1
        if end_brace != -1 and end_bracket != -1:
            end_index = max(end_brace, end_bracket)
        elif end_brace != -1:
            end_index = end_brace
        elif end_bracket != -1:
            end_index = end_bracket
            
        if end_index != -1:
            response_text = response_text[:end_index+1]
            
        # Remove newlines and normalize whitespace
        response_text = response_text.replace('\n', ' ').replace('\r', ' ')
        response_text = ' '.join(response_text.split())
        
        return response_text

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
        
        # Log extraction attempt
        logger.debug("Calling Ollama structured extraction", 
                    model=model, 
                    prompt_length=len(prompt), 
                    prompt_preview=prompt[:300])
        
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
        
        # Enhanced logging to diagnose empty responses
        logger.debug("Ollama API response received", 
                    response_keys=list(result.keys()),
                    response_length=len(response_text),
                    response_preview=response_text[:300] if response_text else "<EMPTY>")
        
        # Check for empty response before processing
        if not response_text or response_text.strip() == "":
            logger.error(
                "LLM returned empty response",
                model=model,
                prompt_preview=prompt[:200],
                full_api_response=result
            )
            raise ValueError("LLM returned empty response - no text generated")
        
        # Parse JSON response
        try:
            # Clean response text
            response_text = self.clean_json_response(response_text)
            
            # Check if cleaning resulted in empty string
            if not response_text or response_text.strip() == "":
                logger.error("JSON cleaning resulted in empty string", original_response=result.get("response", "")[:500])
                raise ValueError("No valid JSON found in response after cleaning")
            
            data = json.loads(response_text)
            return schema(**data)
        except json.JSONDecodeError as e:
            # Try to find JSON object if mixed with text (fallback)
            try:
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0).replace('\n', ' ').replace('\r', ' ')
                    json_str = ' '.join(json_str.split())  # Normalize whitespace
                    data = json.loads(json_str)
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

Extract the information in the following JSON format. 
- If a field is not found in the content, use null (not empty string)
- Do NOT return null for name or company - these are required fields
- If you cannot find name AND company, return an empty object: {{}}

Schema:
{schema_str}

Return ONLY valid JSON, no additional text or explanations.

JSON Response:"""
        
        # Generate response
        if self._is_local_gguf(model):
            response_text = await self._generate_local(enhanced_prompt, model, temperature, max_tokens, **kwargs)
        else:
            response_text = await self._generate_ollama(enhanced_prompt, model, temperature, max_tokens, **kwargs)
        
        # Check for empty response immediately
        if not response_text or response_text.strip() == "":
            logger.error(
                "LLM returned empty response in prompt engineering mode",
                model=model,
                prompt_preview=prompt[:200]
            )
            raise ValueError("LLM returned empty response - no text generated")
            
        # Log raw response
        logger.debug("Prompt engineering response received", 
                    response_length=len(response_text),
                    response_preview=response_text[:300])
            
        # Clean response text
        response_text = self.clean_json_response(response_text)
        
        # Check if cleaning resulted in empty
        if not response_text or response_text.strip() == "":
            logger.error("JSON cleaning resulted in empty string in prompt engineering mode")
            raise ValueError("No valid JSON found in response after cleaning")
        
        # Log after cleaning
        logger.debug("Parsing JSON response", 
                    cleaned_response_preview=response_text[:300])
            
        # Parse JSON response
        try:
            # Clean up any Python code artifacts
            response_text = self._clean_python_code(response_text)
            
            data = json.loads(response_text)
            
            # Check if response is empty (LLM couldn't find required fields)
            if not data or (isinstance(data, dict) and len(data) == 0):
                logger.warning("LLM returned empty JSON object - no data found")
                raise ValueError("No data extracted")
            
            # Attempt to create instance
            try:
                return schema(**data)
            except Exception as validation_error:
                logger.warning(
                    "Validation error creating schema instance",
                    error=str(validation_error),
                    data_preview=str(data)[:200]
                )
                raise
                
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse structured response from prompt engineering",
                error=str(e),
                response=response_text[:500]  # Log first 500 chars
            )
            raise
            
    def _clean_python_code(self, response_text: str) -> str:
        """Clean up Python code artifacts from LLM responses"""
        # NOTE: Minimal cleaning to avoid breaking valid JSON
        # The LLM should return valid JSON with null values per our prompt
        import re
        
        # Only remove datetime.datetime() calls if present (shouldn't be with new prompt)
        response_text = re.sub(r'datetime\.datetime\([^)]+\)', 'null', response_text)
        
        # DO NOT replace null with empty strings - null is valid JSON!
        # The old line below was breaking extraction:
        # response_text = response_text.replace('null', '""')
        
        return response_text
            
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