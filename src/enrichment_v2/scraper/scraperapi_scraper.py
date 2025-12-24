"""
ScraperAPI Scraper for V2

Commercial scraping API with 98.9% success rate.
Features:
- JavaScript rendering
- Cloudflare bypass
- Bot detection bypass
- IP rotation
- CAPTCHA handling
- Smart URL selection with Gemini AI
"""

import os
import logging
import aiohttp
import asyncio
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from .base_scraper import (
    BaseScraper,
    ScraperMethod,
    ScraperStatus,
    ScraperResult,
    PageContent,
    ScraperError,
    ScraperTimeoutError
)
from ..markdown.converter import MarkdownConverter
from ..config import MIN_CONTENT_LENGTH, MIN_SUBSTANTIAL_PAGES
from ..utils.api_exceptions import (
    APIBudgetError,
    APIRateLimitError,
    detect_api_error_type
)

logger = logging.getLogger(__name__)

# Try to import smart URL selector (optional)
try:
    from ..ai.smart_url_selector import SmartURLSelector
    SMART_SELECTOR_AVAILABLE = True
except ImportError as e:
    SMART_SELECTOR_AVAILABLE = False
    logger.warning(f"Smart URL selector not available - will use keyword matching (error: {e})")


class ScraperAPIScraper(BaseScraper):
    """
    Commercial scraping API (ScraperAPI.com) with 98.9% success rate.

    Uses paid API service to bypass:
    - Cloudflare protection
    - Bot detection
    - CAPTCHAs
    - IP blocks
    """

    def __init__(
        self,
        timeout: int = 60,
        max_retries: int = 2,
        user_agent: Optional[str] = None,
        use_smart_selector: bool = True
    ):
        """
        Initialize ScraperAPI scraper.

        Args:
            timeout: Request timeout in seconds
            max_retries: Max retry attempts
            user_agent: Custom user agent
            use_smart_selector: Use Gemini for smart URL selection (default: True)
        """
        super().__init__(timeout, max_retries, user_agent)

        self.api_key = os.getenv('SCRAPERAPI_KEY')
        if not self.api_key:
            raise ValueError("SCRAPERAPI_KEY not found in environment variables")

        self.base_url = 'https://api.scraperapi.com/'
        self.session: Optional[aiohttp.ClientSession] = None

        # Initialize smart URL selector
        self.use_smart_selector = use_smart_selector and SMART_SELECTOR_AVAILABLE
        self.smart_selector = None
        if self.use_smart_selector:
            try:
                self.smart_selector = SmartURLSelector()
                logger.info("Initialized ScraperAPI client with smart URL selector")
            except Exception as e:
                logger.warning(f"Failed to initialize smart URL selector: {e}")
                self.use_smart_selector = False
                logger.info("Initialized ScraperAPI client with keyword URL selector")
        else:
            logger.info("Initialized ScraperAPI client with keyword URL selector")

    def is_available(self) -> bool:
        """Check if ScraperAPI is available (has API key)"""
        return bool(self.api_key)

    def get_method(self) -> ScraperMethod:
        """Get scraper method identifier"""
        return ScraperMethod.SCRAPERAPI

    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def _close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def scrape_page(self, url: str, **kwargs) -> PageContent:
        """
        Scrape a single page using ScraperAPI.

        Args:
            url: URL to scrape
            **kwargs: Additional parameters

        Returns:
            PageContent with scraped data
        """
        # Skip PDF and other download files
        if url.lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.exe', '.dmg')):
            raise ScraperError(f"Skipping download file: {url}")

        await self._ensure_session()

        params = {
            'api_key': self.api_key,
            'url': url,
            'render': 'true',      # JavaScript rendering
            'country_code': 'us'   # Use US proxies
        }

        start_time = asyncio.get_event_loop().time()

        try:
            async with self.session.get(
                self.base_url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:

                html = await response.text()
                status_code = response.status

                load_time = asyncio.get_event_loop().time() - start_time

                if status_code != 200:
                    # Check for budget/rate limit errors
                    if status_code == 429:
                        raise APIRateLimitError(
                            api_name='ScraperAPI',
                            message=f"Rate limit exceeded (HTTP 429)",
                            retry_after=int(response.headers.get('Retry-After', 60))
                        )
                    elif status_code == 402:
                        raise APIBudgetError(
                            api_name='ScraperAPI',
                            message=f"Insufficient credits (HTTP 402 Payment Required)"
                        )
                    else:
                        raise ScraperError(f"ScraperAPI returned status {status_code}")

                # Extract title from HTML
                soup = BeautifulSoup(html, 'html.parser')
                title = soup.title.string if soup.title else ""

                # Convert HTML to markdown
                markdown = MarkdownConverter.convert(html, method='auto')

                self.update_stats(True, len(html), load_time)

                return PageContent(
                    url=url,
                    html=html,
                    markdown=markdown,
                    title=title,
                    status_code=status_code,
                    load_time=load_time,
                    metadata={
                        'scraper_method': 'scraperapi',
                        'rendered': True
                    }
                )

        except asyncio.TimeoutError:
            load_time = asyncio.get_event_loop().time() - start_time
            self.update_stats(False, 0, load_time)
            raise ScraperTimeoutError(f"ScraperAPI timeout for {url}")

        except (APIBudgetError, APIRateLimitError):
            # Re-raise API issues without wrapping
            raise

        except Exception as e:
            load_time = asyncio.get_event_loop().time() - start_time
            self.update_stats(False, 0, load_time)

            # Check if this is a budget or rate limit error
            error_type = detect_api_error_type(e, 'ScraperAPI')

            if error_type == 'budget':
                raise APIBudgetError(
                    api_name='ScraperAPI',
                    message=f"API budget/credits exhausted: {str(e)}",
                    original_error=e
                )
            elif error_type == 'rate_limit':
                raise APIRateLimitError(
                    api_name='ScraperAPI',
                    message=f"API rate limit hit: {str(e)}",
                    original_error=e
                )
            else:
                raise ScraperError(f"ScraperAPI error: {e}")

    async def scrape_multi_page(
        self,
        base_url: str,
        max_pages: int = 10,
        important_paths: Optional[List[str]] = None,
        min_content_chars: int = MIN_CONTENT_LENGTH,
        min_substantial_pages: int = MIN_SUBSTANTIAL_PAGES,
        **kwargs
    ) -> ScraperResult:
        """
        Scrape multiple pages from a website using ScraperAPI.

        Strategy:
        1. Scrape homepage
        2. Extract links
        3. Use smart URL selector (if available) or keyword matching
        4. Scrape selected pages
        5. Validate content quality (minimum chars per page, minimum total pages)

        Args:
            base_url: Base URL of website
            max_pages: Maximum pages to scrape
            important_paths: List of important URL paths
            min_content_chars: Minimum characters per page to be considered substantial (default: 2500)
            min_substantial_pages: Minimum number of substantial pages required (default: 3)
            **kwargs: Additional parameters

        Returns:
            ScraperResult with all scraped pages
        """
        await self._ensure_session()

        start_time = asyncio.get_event_loop().time()
        pages = []
        total_bytes = 0

        try:
            # Step 1: Scrape homepage
            logger.info(f"[ScraperAPI] Scraping homepage: {base_url}")
            homepage = await self.scrape_page(base_url)
            pages.append(homepage)
            total_bytes += len(homepage.html)

            # Step 2: Extract links from homepage
            links = self._extract_links(homepage.html, base_url)
            logger.info(f"[ScraperAPI] Found {len(links)} links on homepage")

            # Step 3: Select priority URLs (smart or keyword-based)
            if self.use_smart_selector and self.smart_selector:
                # Use Gemini for smart URL selection
                logger.info(f"[ScraperAPI] Using smart URL selector (Gemini AI)")

                # Get keyword fallback URLs
                keyword_urls = self._select_priority_urls(
                    links, base_url, max_pages - 1, important_paths or []
                )

                # Try smart selection with keyword fallback
                selection_result = await self.smart_selector.select_with_fallback(
                    base_url=base_url,
                    all_urls=links,
                    max_pages=max_pages - 1,
                    keyword_fallback_urls=keyword_urls
                )

                priority_urls = selection_result['selected_urls']
                logger.info(f"[ScraperAPI] Smart selector used: {selection_result.get('method', 'unknown')}")
                logger.info(f"[ScraperAPI] Selection cost: ${selection_result.get('cost', 0):.4f}")
            else:
                # Use keyword matching
                logger.info(f"[ScraperAPI] Using keyword-based URL selection")
                priority_urls = self._select_priority_urls(
                    links,
                    base_url,
                    max_pages - 1,  # Already scraped homepage
                    important_paths or []
                )

            logger.info(f"[ScraperAPI] Selected {len(priority_urls)} priority URLs to scrape")

            # Step 4: Scrape priority pages
            for url in priority_urls[:max_pages - 1]:
                try:
                    await asyncio.sleep(0.5)  # Small delay between requests
                    page = await self.scrape_page(url)
                    pages.append(page)
                    total_bytes += len(page.html)
                except Exception as e:
                    logger.warning(f"[ScraperAPI] Failed to scrape {url}: {e}")
                    continue

            total_time = asyncio.get_event_loop().time() - start_time

            # Validate content quality (check markdown, not HTML)
            substantial_pages = [p for p in pages if len(p.markdown) >= min_content_chars]
            quality_check_passed = len(substantial_pages) >= min_substantial_pages

            if not quality_check_passed:
                logger.warning(
                    f"[ScraperAPI] Content quality check FAILED: "
                    f"{len(substantial_pages)}/{len(pages)} pages have {min_content_chars}+ chars "
                    f"(need {min_substantial_pages}+ substantial pages)"
                )

            return ScraperResult(
                status=ScraperStatus.SUCCESS if quality_check_passed else ScraperStatus.FAILED,
                method=ScraperMethod.SCRAPERAPI,
                pages=pages,
                error_message=None if quality_check_passed else f"Insufficient content: only {len(substantial_pages)} substantial pages (need {min_substantial_pages}+)",
                total_time=total_time,
                pages_crawled=len(pages),
                bytes_downloaded=total_bytes,
                metadata={
                    'api_provider': 'scraperapi',
                    'rendered': True,
                    'cloudflare_bypass': True,
                    'substantial_pages': len(substantial_pages),
                    'total_pages': len(pages),
                    'quality_check_passed': quality_check_passed,
                    'min_content_chars': min_content_chars
                }
            )

        except Exception as e:
            total_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"[ScraperAPI] Multi-page scraping failed: {e}")

            return ScraperResult(
                status=ScraperStatus.FAILED,
                method=ScraperMethod.SCRAPERAPI,
                pages=pages,  # Return whatever we got
                error_message=str(e),
                total_time=total_time,
                pages_crawled=len(pages),
                bytes_downloaded=total_bytes
            )

        finally:
            await self._close_session()

    def _extract_links(self, html: str, base_url: str) -> List[str]:
        """Extract all links from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']

            # Convert relative URLs to absolute
            full_url = urljoin(base_url, href)

            # Only include links from same domain
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                # Remove fragments and query params for deduplication
                clean_url = full_url.split('#')[0].split('?')[0]
                if clean_url and clean_url not in links:
                    links.append(clean_url)

        return links

    def _select_priority_urls(
        self,
        all_urls: List[str],
        base_url: str,
        max_urls: int,
        important_paths: List[str]
    ) -> List[str]:
        """
        Select priority URLs using keyword matching.

        This is a fallback method. For better results, use smart_url_selector.
        """
        priority_keywords = [
            'about', 'services', 'pricing', 'membership', 'fees',
            'team', 'providers', 'doctors', 'physicians',
            'contact', 'join', 'enroll', 'faq', 'testimonials'
        ]

        scored_urls = []

        for url in all_urls:
            url_lower = url.lower()
            score = 0

            # Score based on keyword matches
            for keyword in priority_keywords:
                if keyword in url_lower:
                    score += 10

            # Bonus for shorter URLs (likely more important)
            if len(url.split('/')) <= 4:
                score += 5

            # Bonus for important paths
            for path in important_paths:
                if path in url_lower:
                    score += 20

            scored_urls.append((score, url))

        # Sort by score (descending) and return top N
        scored_urls.sort(reverse=True, key=lambda x: x[0])
        return [url for score, url in scored_urls[:max_urls]]

    def __repr__(self) -> str:
        return f"<ScraperAPIScraper api_key={'*' * 8}>"
