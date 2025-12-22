"""
Base scraper interface using Strategy pattern

This module defines the abstract base class for all scrapers,
ensuring a consistent interface and enabling polymorphic behavior.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime


class ScraperMethod(Enum):
    """Enumeration of available scraping methods"""
    SCRAPERAPI = "scraperapi"  # Commercial API with 98.9% success rate
    CRAWL4AI = "crawl4ai"
    SELENIUM = "selenium"
    PLAYWRIGHT = "playwright"
    REQUESTS = "requests"


class ScraperStatus(Enum):
    """Status of scraping operation"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


@dataclass
class PageContent:
    """Container for scraped page content"""
    url: str
    html: str
    markdown: str
    title: str = ""
    status_code: int = 200
    load_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate page content after initialization"""
        if not self.url:
            raise ValueError("URL cannot be empty")
        if not self.html and not self.markdown:
            raise ValueError("Either HTML or markdown must be provided")


@dataclass
class ScraperResult:
    """Result of a scraping operation"""
    status: ScraperStatus
    method: ScraperMethod
    pages: List[PageContent] = field(default_factory=list)
    error_message: Optional[str] = None
    total_time: float = 0.0
    pages_crawled: int = 0
    bytes_downloaded: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if scraping was successful"""
        return self.status == ScraperStatus.SUCCESS and len(self.pages) > 0

    @property
    def total_markdown_chars(self) -> int:
        """Calculate total markdown characters across all pages"""
        return sum(len(page.markdown) for page in self.pages)

    def get_merged_markdown(self) -> str:
        """Get all page markdown merged into single document"""
        if not self.pages:
            return ""

        sections = []
        for i, page in enumerate(self.pages, 1):
            section_header = f"\n\n{'='*80}\n"
            section_header += f"PAGE {i}: {page.title or page.url}\n"
            section_header += f"{'='*80}\n\n"
            sections.append(section_header + page.markdown)

        return "\n".join(sections)


class ScraperError(Exception):
    """Base exception for scraper errors"""
    pass


class ScraperTimeoutError(ScraperError):
    """Raised when scraper times out"""
    pass


class ScraperRateLimitError(ScraperError):
    """Raised when rate limit is hit"""
    pass


class BaseScraper(ABC):
    """
    Abstract base class for all web scrapers.

    Implements Strategy pattern to allow different scraping strategies
    to be swapped at runtime while maintaining a consistent interface.

    All concrete scrapers must implement:
    - scrape_page(): Scrape a single page
    - scrape_multi_page(): Scrape multiple pages from a website
    - is_available(): Check if scraper dependencies are available
    """

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        user_agent: Optional[str] = None
    ):
        """
        Initialize base scraper.

        Args:
            timeout: Maximum time (seconds) to wait for page load
            max_retries: Maximum number of retry attempts
            user_agent: Custom user agent string
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent or self._get_default_user_agent()
        self._stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_bytes': 0,
            'total_time': 0.0,
        }

    @staticmethod
    def _get_default_user_agent() -> str:
        """Get default user agent string"""
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    @abstractmethod
    async def scrape_page(self, url: str, **kwargs) -> PageContent:
        """
        Scrape a single page.

        Args:
            url: URL to scrape
            **kwargs: Additional scraper-specific arguments

        Returns:
            PageContent object with scraped data

        Raises:
            ScraperError: If scraping fails
            ScraperTimeoutError: If request times out
        """
        pass

    @abstractmethod
    async def scrape_multi_page(
        self,
        base_url: str,
        max_pages: int = 10,
        important_paths: Optional[List[str]] = None,
        **kwargs
    ) -> ScraperResult:
        """
        Scrape multiple pages from a website.

        Args:
            base_url: Base URL of the website
            max_pages: Maximum number of pages to scrape
            important_paths: List of important URL paths to prioritize
            **kwargs: Additional scraper-specific arguments

        Returns:
            ScraperResult with all scraped pages

        Raises:
            ScraperError: If scraping fails completely
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this scraper's dependencies are available.

        Returns:
            True if scraper can be used, False otherwise
        """
        pass

    @abstractmethod
    def get_method(self) -> ScraperMethod:
        """
        Get the scraping method identifier.

        Returns:
            ScraperMethod enum value
        """
        pass

    def update_stats(self, success: bool, bytes_downloaded: int, time_taken: float):
        """Update internal statistics"""
        self._stats['total_requests'] += 1
        if success:
            self._stats['successful_requests'] += 1
        else:
            self._stats['failed_requests'] += 1
        self._stats['total_bytes'] += bytes_downloaded
        self._stats['total_time'] += time_taken

    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        return self._stats.copy()

    def reset_stats(self):
        """Reset statistics"""
        for key in self._stats:
            if isinstance(self._stats[key], (int, float)):
                self._stats[key] = 0

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} method={self.get_method().value}>"
