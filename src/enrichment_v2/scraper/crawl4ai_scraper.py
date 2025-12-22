"""
Crawl4AI scraper implementation

Primary scraping method using crawl4ai library.

Features:
- Async web crawling
- Built-in markdown conversion
- JavaScript rendering support
- Multi-page crawling with link discovery
- Session management
"""

import asyncio
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse
import logging

from .base_scraper import (
    BaseScraper,
    ScraperMethod,
    ScraperStatus,
    ScraperResult,
    PageContent,
    ScraperError,
    ScraperTimeoutError
)
from ..utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


def normalize_to_root_url(url: str) -> str:
    """Normalize URL to root domain."""
    parsed = urlparse(url)
    root_url = f"{parsed.scheme}://{parsed.netloc}/"
    return root_url


class Crawl4AIScraper(BaseScraper):
    """
    Crawl4AI-based scraper implementation.

    Uses AsyncWebCrawler for fast, async scraping with built-in markdown.
    """

    def __init__(self, timeout: int = 30, max_retries: int = 3, user_agent: Optional[str] = None):
        """Initialize crawl4ai scraper"""
        super().__init__(timeout, max_retries, user_agent)
        self._crawler = None

    async def _ensure_crawler(self):
        """Ensure crawler is initialized"""
        if self._crawler is None:
            try:
                from crawl4ai import AsyncWebCrawler
                self._crawler = AsyncWebCrawler(
                    verbose=False,
                    headless=True,
                )
                await self._crawler.__aenter__()
                logger.debug("Crawl4AI crawler initialized")
            except ImportError:
                raise ScraperError("crawl4ai not installed. Install with: pip install crawl4ai")
            except Exception as e:
                raise ScraperError(f"Failed to initialize crawl4ai: {e}")

    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    async def scrape_page(self, url: str, **kwargs) -> PageContent:
        """
        Scrape a single page using crawl4ai.

        Args:
            url: URL to scrape
            **kwargs: Additional arguments (wait_for, js_code, etc.)

        Returns:
            PageContent with scraped data
        """
        import time
        start_time = time.time()

        try:
            await self._ensure_crawler()

            # Crawl page
            result = await asyncio.wait_for(
                self._crawler.arun(
                    url=url,
                    bypass_cache=True,
                    user_agent=self.user_agent,
                    **kwargs
                ),
                timeout=self.timeout
            )

            # Check if successful
            if not result.success:
                raise ScraperError(f"Crawl4AI failed for {url}: {result.error_message}")

            # Extract data
            html = result.html or ""
            markdown = result.markdown or ""
            title = self._extract_title(html)

            load_time = time.time() - start_time

            # Update stats
            self.update_stats(
                success=True,
                bytes_downloaded=len(html),
                time_taken=load_time
            )

            return PageContent(
                url=url,
                html=html,
                markdown=markdown,
                title=title,
                status_code=200,
                load_time=load_time,
                metadata={
                    'method': 'crawl4ai',
                    'links_found': len(result.links.get('internal', [])) if result.links else 0,
                }
            )

        except asyncio.TimeoutError:
            self.update_stats(success=False, bytes_downloaded=0, time_taken=time.time() - start_time)
            raise ScraperTimeoutError(f"Timeout scraping {url}")

        except Exception as e:
            self.update_stats(success=False, bytes_downloaded=0, time_taken=time.time() - start_time)
            raise ScraperError(f"Error scraping {url}: {e}")

    async def scrape_multi_page(
        self,
        base_url: str,
        max_pages: int = 15,
        important_paths: Optional[List[str]] = None,
        **kwargs
    ) -> ScraperResult:
        """
        Scrape multiple pages from a website.

        Strategy:
        1. Normalize URL to root domain (avoid deep links)
        2. Scrape homepage
        3. Find important internal links
        4. Scrape those pages (up to max_pages)
        5. Return all scraped content

        Args:
            base_url: Base URL of website
            max_pages: Maximum pages to scrape
            important_paths: List of important URL paths to prioritize
            **kwargs: Additional scraper arguments

        Returns:
            ScraperResult with all pages
        """
        import time
        start_time = time.time()

        try:
            # CRITICAL: Normalize to root URL to avoid starting from deep links
            base_url = normalize_to_root_url(base_url)
            logger.info(f"Normalized to root URL: {base_url}")

            await self._ensure_crawler()

            # Track scraped URLs and pages
            scraped_urls: Set[str] = set()
            pages: List[PageContent] = []

            # 1. Scrape homepage first
            try:
                homepage = await self.scrape_page(base_url, **kwargs)
                pages.append(homepage)
                scraped_urls.add(base_url)
                logger.info(f"Scraped homepage: {base_url}")

                # Extract links from homepage
                homepage_links = self._extract_internal_links(homepage.html, base_url)

            except Exception as e:
                logger.error(f"Failed to scrape homepage {base_url}: {e}")
                return ScraperResult(
                    status=ScraperStatus.FAILED,
                    method=ScraperMethod.CRAWL4AI,
                    pages=[],
                    error_message=str(e),
                    total_time=time.time() - start_time
                )

            # 2. Find important pages to scrape
            urls_to_scrape = self._prioritize_urls(
                homepage_links,
                base_url,
                important_paths or [],
                max_pages - 1  # -1 because we already scraped homepage
            )

            # 3. Scrape additional pages
            for url in urls_to_scrape:
                if url in scraped_urls:
                    continue

                try:
                    page = await self.scrape_page(url, **kwargs)
                    pages.append(page)
                    scraped_urls.add(url)
                    logger.debug(f"Scraped: {url}")

                except Exception as e:
                    logger.warning(f"Failed to scrape {url}: {e}")
                    continue

                # Check if we've reached max pages
                if len(pages) >= max_pages:
                    break

            # 4. Build result
            total_time = time.time() - start_time
            total_bytes = sum(len(page.html) for page in pages)

            return ScraperResult(
                status=ScraperStatus.SUCCESS,
                method=ScraperMethod.CRAWL4AI,
                pages=pages,
                total_time=total_time,
                pages_crawled=len(pages),
                bytes_downloaded=total_bytes,
                metadata={
                    'base_url': base_url,
                    'urls_scraped': list(scraped_urls),
                }
            )

        except Exception as e:
            logger.error(f"Multi-page scraping failed for {base_url}: {e}")
            return ScraperResult(
                status=ScraperStatus.ERROR,
                method=ScraperMethod.CRAWL4AI,
                pages=pages,  # Return whatever we got
                error_message=str(e),
                total_time=time.time() - start_time,
                pages_crawled=len(pages)
            )

    def _extract_internal_links(self, html: str, base_url: str) -> List[str]:
        """Extract internal links from HTML"""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, 'html.parser')
            base_domain = urlparse(base_url).netloc

            links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']

                # Make absolute URL
                absolute_url = urljoin(base_url, href)

                # Check if internal (same domain)
                if urlparse(absolute_url).netloc == base_domain:
                    # Remove fragments and query params for uniqueness
                    clean_url = absolute_url.split('#')[0].split('?')[0]
                    if clean_url and clean_url not in links:
                        links.append(clean_url)

            return links

        except Exception as e:
            logger.warning(f"Failed to extract links: {e}")
            return []

    def _prioritize_urls(
        self,
        urls: List[str],
        base_url: str,
        important_paths: List[str],
        max_urls: int
    ) -> List[str]:
        """
        Prioritize URLs based on importance.

        Strategy:
        1. URLs matching important_paths get highest priority
        2. URLs with key keywords get priority (pricing, membership, services, etc.)
        3. Shorter URLs (closer to root) get higher priority
        4. Avoid blog/news pages
        5. Return up to max_urls
        """
        scored_urls = []

        # Priority keywords for DPC practices
        priority_keywords = [
            'about', 'services', 'pricing', 'membership', 'contact',
            'team', 'providers', 'doctors', 'faq', 'enroll',
            'discounts', 'clinics', 'business', 'corporate', 'plans'
        ]

        for url in urls:
            if url == base_url:
                continue  # Skip homepage (already scraped)

            # Calculate score
            score = 0

            # Check if matches important paths (user-provided)
            path = urlparse(url).path.lower().strip('/')
            for important_path in important_paths:
                if important_path.lower() in path:
                    score += 100  # High priority

            # Check for priority keywords
            for keyword in priority_keywords:
                if keyword in path:
                    score += 50  # Medium-high priority

            # Prefer shorter paths (closer to root)
            path_depth = path.count('/')
            score -= path_depth * 10

            # Avoid certain patterns (blog, wordpress admin, etc.)
            avoid_patterns = ['blog', 'wp-content', 'wp-admin', 'wp-includes', '/post/', '/posts/', '/news/']
            if any(pattern in path for pattern in avoid_patterns):
                score -= 1000  # Very low priority

            scored_urls.append((score, url))

        # Sort by score (descending) and return top N
        scored_urls.sort(reverse=True, key=lambda x: x[0])
        return [url for score, url in scored_urls[:max_urls]]

    @staticmethod
    def _extract_title(html: str) -> str:
        """Extract title from HTML"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            title_tag = soup.find('title')
            return title_tag.get_text().strip() if title_tag else ""
        except:
            return ""

    def is_available(self) -> bool:
        """Check if crawl4ai is available"""
        try:
            import crawl4ai
            return True
        except ImportError:
            return False

    def get_method(self) -> ScraperMethod:
        """Get scraper method identifier"""
        return ScraperMethod.CRAWL4AI

    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_crawler()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup"""
        if self._crawler:
            try:
                await self._crawler.__aexit__(exc_type, exc_val, exc_tb)
            except:
                pass
            self._crawler = None
