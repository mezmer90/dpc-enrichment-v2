"""
Smart URL Selector using Gemini

Uses Gemini 2.5 Flash to intelligently select which pages to scrape
from a practice website based on relevance to DPC practice information.

This is smarter than keyword matching - Gemini understands context.
"""

import os
import logging
from typing import List, Dict, Optional
from openai import AsyncOpenAI
import json

logger = logging.getLogger(__name__)


class SmartURLSelector:
    """Uses Gemini to select relevant URLs to scrape."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize with OpenRouter API.

        Args:
            api_key: OpenRouter API key (if None, reads from environment)
        """
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment")

        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )

        # Use Gemini 2.5 Flash (cheap and fast)
        self.model = "google/gemini-2.5-flash-preview-09-2025"

    async def select_urls(
        self,
        base_url: str,
        all_urls: List[str],
        max_pages: int = 15
    ) -> Dict:
        """
        Use Gemini to select the most relevant URLs to scrape.

        Args:
            base_url: Homepage URL
            all_urls: List of all URLs found on homepage
            max_pages: Maximum pages to select

        Returns:
            dict with 'selected_urls', 'reasoning', 'cost'
        """
        if not all_urls:
            return {
                'selected_urls': [],
                'reasoning': 'No URLs provided',
                'cost': 0.0
            }

        # Limit to first 100 URLs for API efficiency
        urls_to_analyze = all_urls[:100]

        prompt = f"""You are analyzing a Direct Primary Care (DPC) practice website to select the most relevant pages to scrape.

**Website**: {base_url}

**Available URLs** ({len(urls_to_analyze)} total):
{chr(10).join(f"{i+1}. {url}" for i, url in enumerate(urls_to_analyze))}

**Task**: Select the {max_pages} MOST RELEVANT pages that would contain information about:
1. **Services offered** (primary care services, lab work, procedures)
2. **Pricing/membership** (monthly fees, enrollment costs)
3. **Team/providers** (doctors, nurse practitioners)
4. **About/philosophy** (DPC model, practice philosophy)
5. **Contact/location** (phone, address, hours)
6. **Patient info** (enrollment process, FAQs)

**IMPORTANT**:
- Homepage is ALWAYS included (don't select it again)
- Prioritize pages with clear DPC-related content
- Avoid: blog posts, news, careers, general wellness articles
- Select diverse page types (don't pick 5 blog posts)
- Maximum {max_pages} pages total

**Output Format** (JSON only):
```json
{{
  "selected_urls": [
    "https://example.com/services",
    "https://example.com/pricing",
    ...
  ],
  "reasoning": "Brief explanation of why these pages were selected"
}}
```

Return ONLY the JSON, no other text."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent selection
                max_tokens=1000
            )

            # Extract response
            content = response.choices[0].message.content.strip()

            # Parse JSON from response - handle markdown code blocks
            # Gemini often wraps JSON in markdown, e.g.: ```json\n{...}\n```
            json_content = content

            # Try to extract JSON from markdown code block
            if '```json' in content:
                # Find the JSON block
                start_marker = '```json'
                end_marker = '```'
                start_idx = content.find(start_marker)
                if start_idx != -1:
                    # Get content after ```json
                    json_start = start_idx + len(start_marker)
                    remaining = content[json_start:]
                    # Find the closing ```
                    end_idx = remaining.find(end_marker)
                    if end_idx != -1:
                        json_content = remaining[:end_idx].strip()
            elif content.startswith('```'):
                # Fallback: handle generic code blocks
                parts = content.split('```')
                if len(parts) >= 2:
                    json_content = parts[1].strip()
                    # Remove language identifier if present (e.g., "json")
                    if json_content.startswith('json'):
                        json_content = json_content[4:].strip()

            result = json.loads(json_content)

            # Calculate cost
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost = self._calculate_cost(input_tokens, output_tokens)

            selected_urls = result.get('selected_urls', [])
            reasoning = result.get('reasoning', '')

            # Filter to ensure URLs are from the original list
            valid_urls = [url for url in selected_urls if url in urls_to_analyze]

            # Limit to max_pages
            valid_urls = valid_urls[:max_pages]

            logger.info(f"Gemini selected {len(valid_urls)}/{len(urls_to_analyze)} URLs (cost: ${cost:.4f})")
            logger.debug(f"Reasoning: {reasoning}")

            return {
                'selected_urls': valid_urls,
                'reasoning': reasoning,
                'cost': cost,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            logger.error(f"Response content: {content}")
            # Fallback: return empty selection
            return {
                'selected_urls': [],
                'reasoning': f'JSON parse error: {e}',
                'cost': 0.0
            }

        except Exception as e:
            logger.error(f"Error in smart URL selection: {e}")
            return {
                'selected_urls': [],
                'reasoning': f'Error: {e}',
                'cost': 0.0
            }

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for Gemini 2.5 Flash.

        Pricing (via OpenRouter):
        - Input: $0.10 per 1M tokens
        - Output: $0.40 per 1M tokens
        """
        input_cost = (input_tokens / 1_000_000) * 0.10
        output_cost = (output_tokens / 1_000_000) * 0.40
        return input_cost + output_cost

    async def select_with_fallback(
        self,
        base_url: str,
        all_urls: List[str],
        max_pages: int = 15,
        keyword_fallback_urls: Optional[List[str]] = None
    ) -> Dict:
        """
        Select URLs with keyword-based fallback if Gemini fails.

        Args:
            base_url: Homepage URL
            all_urls: All URLs found
            max_pages: Max pages to select
            keyword_fallback_urls: Pre-selected URLs from keyword matching (fallback)

        Returns:
            dict with selection results
        """
        # Try Gemini first
        result = await self.select_urls(base_url, all_urls, max_pages)

        # If Gemini succeeded, return its selection
        if result['selected_urls']:
            result['method'] = 'gemini'
            return result

        # If Gemini failed and we have keyword fallback, use it
        if keyword_fallback_urls:
            logger.warning(f"Gemini selection failed, using keyword fallback ({len(keyword_fallback_urls)} URLs)")
            return {
                'selected_urls': keyword_fallback_urls[:max_pages],
                'reasoning': 'Gemini failed, used keyword matching fallback',
                'cost': 0.0,
                'method': 'keyword_fallback'
            }

        # No selection possible
        logger.error("Both Gemini and keyword fallback failed")
        return {
            'selected_urls': [],
            'reasoning': 'Both Gemini and keyword fallback failed',
            'cost': 0.0,
            'method': 'failed'
        }
