"""
Gemini 2.5 Flash Preview client via OpenRouter

Handles AI-powered data extraction with:
- OpenRouter API integration
- Gemini 2.5 Flash Preview model
- Token and cost tracking
- Error handling and retries
- Context truncation
"""

import json
import logging
from typing import Dict, Optional
from openai import OpenAI
import asyncio

from ..utils.retry import retry_with_backoff
from ..utils.api_exceptions import (
    APIBudgetError,
    APIRateLimitError,
    detect_api_error_type
)

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Client for Gemini 2.5 Flash Preview via OpenRouter.

    Uses OpenAI-compatible API through OpenRouter.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "google/gemini-2.5-flash-preview-09-2025",
        temperature: float = 0.1,
        max_tokens: int = 8000,
        timeout: int = 60
    ):
        """
        Initialize Gemini client.

        Args:
            api_key: OpenRouter API key
            model: Model identifier
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum output tokens
            timeout: Request timeout in seconds
        """
        if not api_key:
            raise ValueError("OpenRouter API key is required")

        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        # Initialize OpenAI client with OpenRouter base URL
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=timeout
        )

        logger.info(f"Initialized Gemini client: model={model}, temperature={temperature}")

    @retry_with_backoff(max_attempts=3, base_delay=2.0, exponential_base=2.0)
    async def extract_data(
        self,
        markdown: str,
        practice_data: Dict,
        prompt_template: str,
        max_context_chars: int = 800000
    ) -> Dict:
        """
        Extract structured data from markdown using AI.

        Args:
            markdown: Markdown content to analyze
            practice_data: Existing practice data (for context)
            prompt_template: Prompt template with {markdown}, {practice_name}, etc.
            max_context_chars: Max characters to send (for 1M token context)

        Returns:
            Extracted data as dict with fields

        Raises:
            Exception: If extraction fails
        """
        try:
            # Truncate markdown if needed
            if len(markdown) > max_context_chars:
                logger.warning(
                    f"Markdown too long ({len(markdown)} chars), truncating to {max_context_chars}"
                )
                markdown = markdown[:max_context_chars] + "\n\n... (truncated)"

            # Build location context for multi-location awareness
            city = practice_data.get('address_city', '')
            state = practice_data.get('address_state', '')
            street = practice_data.get('address_street', '')

            if street and city and state:
                location_context = f"{street}, {city}, {state}"
            elif city and state:
                location_context = f"{city}, {state}"
            elif state:
                location_context = state
            else:
                location_context = "Location not specified"

            # Build prompt
            prompt = prompt_template.format(
                markdown=markdown,
                practice_name=practice_data.get('practice_name', ''),
                website_url=practice_data.get('website_url', ''),
                practice_id=practice_data.get('practice_id', ''),
                location_context=location_context
            )

            logger.debug(f"Sending {len(prompt)} chars to Gemini for extraction")

            # Call API (sync in async context)
            response = await asyncio.to_thread(
                self._make_api_call,
                prompt
            )

            # Parse response
            content = response.choices[0].message.content

            # Try to parse as JSON
            try:
                extracted = json.loads(content)
            except json.JSONDecodeError:
                # Sometimes model wraps JSON in markdown code blocks
                content = content.strip()
                if content.startswith('```json'):
                    content = content[7:]  # Remove ```json
                if content.startswith('```'):
                    content = content[3:]  # Remove ```
                if content.endswith('```'):
                    content = content[:-3]  # Remove ```
                extracted = json.loads(content.strip())

            # Add metadata
            extracted['_enrichment_metadata'] = {
                'llm_model': self.model,
                'llm_cost': self._calculate_cost(response.usage),
                'llm_tokens_input': response.usage.prompt_tokens,
                'llm_tokens_output': response.usage.completion_tokens,
                'llm_tokens_total': response.usage.total_tokens,
                'markdown_chars': len(markdown),
                'prompt_chars': len(prompt),
            }

            logger.info(
                f"Extracted data: {response.usage.total_tokens} tokens, "
                f"${extracted['_enrichment_metadata']['llm_cost']:.4f}"
            )

            return extracted

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from AI response: {e}")
            logger.error(f"Response content: {content[:500]}...")
            raise Exception(f"Invalid JSON from AI: {e}")

        except Exception as e:
            # Check if this is a budget or rate limit error
            error_type = detect_api_error_type(e, 'OpenRouter')

            if error_type == 'budget':
                raise APIBudgetError(
                    api_name='OpenRouter',
                    message=f"API budget/credits exhausted: {str(e)}",
                    original_error=e
                )
            elif error_type == 'rate_limit':
                raise APIRateLimitError(
                    api_name='OpenRouter',
                    message=f"API rate limit hit: {str(e)}",
                    original_error=e
                )
            else:
                logger.error(f"Gemini extraction failed: {e}")
                raise

    def _make_api_call(self, prompt: str):
        """Make synchronous API call (to be run in thread)"""
        return self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a data extraction expert for healthcare practices. "
                        "Extract structured information accurately and comprehensively. "
                        "Return ONLY valid JSON with no additional text or explanations."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"}  # Force JSON response
        )

    def _calculate_cost(self, usage) -> float:
        """
        Calculate cost based on token usage.

        Gemini 2.5 Flash Preview pricing:
        - Input: $0.30 per 1M tokens
        - Output: $2.50 per 1M tokens
        """
        input_cost = (usage.prompt_tokens / 1_000_000) * 0.30
        output_cost = (usage.completion_tokens / 1_000_000) * 2.50
        return input_cost + output_cost

    def get_model_info(self) -> Dict:
        """
        Get information about current model configuration.

        Returns:
            Dict with model details
        """
        return {
            'model': self.model,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'timeout': self.timeout,
            'context_window': '1M tokens (~800k characters)',
            'pricing': {
                'input': '$0.30/M tokens',
                'output': '$2.50/M tokens',
            }
        }

    async def test_connection(self) -> bool:
        """
        Test API connection with simple request.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            logger.info("API connection test successful")
            return True

        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False
