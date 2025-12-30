"""
Playwright scraper implementation (Fallback 2)

Uses Playwright for browser automation with guaranteed cleanup and timeouts.
"""

import asyncio
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse
import logging

from .base_scraper import BaseScraper, ScraperMethod, ScraperStatus, ScraperResult, PageContent, ScraperError
from ..markdown.converter import MarkdownConverter

logger = logging.getLogger(__name__)


def normalize_to_root_url(url: str) -> str:
    """
    Normalize URL to root domain.

    Examples:
        https://example.com/signup -> https://example.com/
        https://example.com/path/to/page -> https://example.com/
    """
    parsed = urlparse(url)
    # Reconstruct with just scheme and netloc (domain)
    root_url = f"{parsed.scheme}://{parsed.netloc}/"
    return root_url


class PlaywrightScraper(BaseScraper):
    async def scrape_page(self, url: str, **kwargs) -> PageContent:
        """Scrape page with guaranteed browser cleanup and timeouts."""
        import time
        start_time = time.time()

        # Skip PDF and other download files
        if url.lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.exe', '.dmg')):
            raise ScraperError(f"Skipping download file: {url}")

        browser = None
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                try:
                    # Add timeout to browser launch (30 seconds max)
                    browser = await asyncio.wait_for(
                        p.chromium.launch(headless=True),
                        timeout=30
                    )

                    page = await browser.new_page(user_agent=self.user_agent)

                    # Add timeout to page load
                    await asyncio.wait_for(
                        page.goto(url, wait_until='domcontentloaded'),
                        timeout=self.timeout
                    )

                    html = await page.content()
                    title = await page.title()

                    load_time = time.time() - start_time
                    self.update_stats(True, len(html), load_time)

                    # Convert HTML to markdown
                    markdown = MarkdownConverter.convert(html, method='auto')

                    return PageContent(
                        url=url,
                        html=html,
                        markdown=markdown,
                        title=title,
                        load_time=load_time
                    )

                finally:
                    # CRITICAL: Always close browser to prevent resource leaks
                    if browser:
                        try:
                            await asyncio.wait_for(browser.close(), timeout=5)
                        except:
                            pass  # Ignore errors during cleanup

        except asyncio.TimeoutError:
            self.update_stats(False, 0, time.time() - start_time)
            raise ScraperError(f"Playwright timeout for {url}")
        except Exception as e:
            self.update_stats(False, 0, time.time() - start_time)
            raise ScraperError(f"Playwright failed for {url}: {e}")

    async def scrape_multi_page(self, base_url: str, max_pages: int = 15, important_paths: Optional[List[str]] = None, **kwargs) -> ScraperResult:
        """
        Scrape multiple pages from a website.

        Strategy:
        1. Normalize URL to root domain (avoid deep links)
        2. Scrape homepage
        3. Find important internal links
        4. Scrape those pages (up to max_pages)
        5. Return all scraped content
        """
        import time
        start_time = time.time()

        try:
            # CRITICAL: Normalize to root URL to avoid starting from deep links
            # e.g., https://example.com/signup -> https://example.com/
            base_url = normalize_to_root_url(base_url)
            logger.info(f"Normalized to root URL: {base_url}")

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
                    method=ScraperMethod.PLAYWRIGHT,
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
                method=ScraperMethod.PLAYWRIGHT,
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
                method=ScraperMethod.PLAYWRIGHT,
                pages=pages,
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

    def is_available(self) -> bool:
        try:
            from playwright.async_api import async_playwright
            return True
        except ImportError:
            return False

    def get_method(self) -> ScraperMethod:
        return ScraperMethod.PLAYWRIGHT
