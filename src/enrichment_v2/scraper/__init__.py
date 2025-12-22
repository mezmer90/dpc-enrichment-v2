"""
Scraper module for DPC Enrichment V2

Enterprise-level web scraping with:
- Strategy pattern for multiple scraper implementations
- Circuit breaker for failing domains
- Retry with exponential backoff
- Connection pooling
- Async/await for I/O operations
"""

from .base_scraper import BaseScraper, ScraperResult, ScraperError
from .scraper_factory import ScraperFactory
from .circuit_breaker import CircuitBreaker

__all__ = [
    'BaseScraper',
    'ScraperResult',
    'ScraperError',
    'ScraperFactory',
    'CircuitBreaker',
]
