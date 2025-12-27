"""
Scraper Factory using Factory Pattern

Creates appropriate scraper instances and manages fallback chains.
"""

from typing import List, Optional
import logging

from .base_scraper import BaseScraper, ScraperMethod
from .scraperapi_scraper import ScraperAPIScraper
from .crawl4ai_scraper import Crawl4AIScraper
from .selenium_scraper import SeleniumScraper
from .playwright_scraper import PlaywrightScraper
from .requests_scraper import RequestsScraper

logger = logging.getLogger(__name__)


class ScraperFactory:
    """
    Factory for creating scraper instances.

    Implements Factory Pattern to encapsulate scraper creation logic.
    """

    # Map of scraper methods to their classes
    _SCRAPER_CLASSES = {
        ScraperMethod.SCRAPERAPI: ScraperAPIScraper,
        ScraperMethod.CRAWL4AI: Crawl4AIScraper,
        ScraperMethod.SELENIUM: SeleniumScraper,
        ScraperMethod.PLAYWRIGHT: PlaywrightScraper,
        ScraperMethod.REQUESTS: RequestsScraper,
    }

    @staticmethod
    def create_scraper(
        method: ScraperMethod,
        timeout: int = 30,
        max_retries: int = 3,
        user_agent: Optional[str] = None
    ) -> BaseScraper:
        """
        Create a scraper instance for the specified method.

        Args:
            method: Scraper method to use
            timeout: Timeout in seconds
            max_retries: Maximum retry attempts
            user_agent: Custom user agent string

        Returns:
            BaseScraper instance

        Raises:
            ValueError: If method is unknown
        """
        scraper_class = ScraperFactory._SCRAPER_CLASSES.get(method)

        if scraper_class is None:
            raise ValueError(f"Unknown scraper method: {method}")

        return scraper_class(
            timeout=timeout,
            max_retries=max_retries,
            user_agent=user_agent
        )

    @staticmethod
    def get_available_scrapers(
        timeout: int = 30,
        max_retries: int = 3,
        user_agent: Optional[str] = None
    ) -> List[BaseScraper]:
        """
        Get list of all available (installed) scrapers.

        Args:
            timeout: Timeout for scrapers
            max_retries: Max retries for scrapers
            user_agent: User agent string

        Returns:
            List of available BaseScraper instances
        """
        available = []

        for method in ScraperFactory._SCRAPER_CLASSES.keys():
            try:
                scraper = ScraperFactory.create_scraper(
                    method=method,
                    timeout=timeout,
                    max_retries=max_retries,
                    user_agent=user_agent
                )

                if scraper.is_available():
                    available.append(scraper)
                    logger.debug(f"Scraper available: {method.value}")
                else:
                    logger.debug(f"Scraper not available (missing dependencies): {method.value}")

            except Exception as e:
                logger.warning(f"Failed to create scraper {method.value}: {e}")

        return available

    @staticmethod
    def create_with_fallback(
        timeout: int = 30,
        max_retries: int = 3,
        user_agent: Optional[str] = None
    ) -> List[BaseScraper]:
        """
        Create scraper chain with fallbacks.

        Returns scrapers in priority order:
        1. Crawl4AI (fastest, best markdown)
        2. Selenium (most compatible, JS rendering)
        3. Playwright (modern, fast)
        4. Requests (lightest, simplest)

        Args:
            timeout: Timeout for scrapers
            max_retries: Max retries for scrapers
            user_agent: User agent string

        Returns:
            List of scrapers in fallback order
        """
        available = ScraperFactory.get_available_scrapers(
            timeout=timeout,
            max_retries=max_retries,
            user_agent=user_agent
        )

        # Sort by priority (ScraperAPI first for 98.9% success rate)
        priority_order = [
            ScraperMethod.SCRAPERAPI,     # 1st - Commercial API with 98.9% success rate
            ScraperMethod.PLAYWRIGHT,     # 2nd - Proven working (8/9 successes)
            ScraperMethod.REQUESTS,       # 3rd - Fast fallback (1/9 successes)
            ScraperMethod.CRAWL4AI,       # 4th - User preference
            # ScraperMethod.SELENIUM,       # 5th - Has driver issues
        ]

        sorted_scrapers = []
        for method in priority_order:
            for scraper in available:
                if scraper.get_method() == method:
                    sorted_scrapers.append(scraper)
                    break

        if not sorted_scrapers:
            logger.error("No scrapers available! Install at least one scraping library.")
            raise RuntimeError("No scrapers available")

        logger.debug(f"Scraper fallback chain: {[s.get_method().value for s in sorted_scrapers]}")
        return sorted_scrapers

    @staticmethod
    def get_scraper_info() -> dict:
        """
        Get information about all scraper types.

        Returns:
            Dict mapping method name to availability and description
        """
        info = {}

        for method, scraper_class in ScraperFactory._SCRAPER_CLASSES.items():
            try:
                scraper = scraper_class()
                info[method.value] = {
                    'available': scraper.is_available(),
                    'class': scraper_class.__name__,
                    'description': scraper_class.__doc__ or "No description"
                }
            except Exception as e:
                info[method.value] = {
                    'available': False,
                    'class': scraper_class.__name__,
                    'error': str(e)
                }

        return info
