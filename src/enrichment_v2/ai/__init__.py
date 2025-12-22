"""
AI integration modules for data extraction

Uses Gemini 2.5 Flash Preview via OpenRouter for high-quality field extraction.
"""

from .gemini_client import GeminiClient
from .extractor import FieldExtractor, EXTRACTION_PROMPT

__all__ = ['GeminiClient', 'FieldExtractor', 'EXTRACTION_PROMPT']
