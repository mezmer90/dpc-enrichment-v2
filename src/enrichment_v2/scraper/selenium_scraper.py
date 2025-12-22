"""Selenium scraper implementation (Fallback 1)"""

import asyncio
from typing import List, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging

from .base_scraper import BaseScraper, ScraperMethod, ScraperStatus, ScraperResult, PageContent, ScraperError
from ..markdown.converter import MarkdownConverter

logger = logging.getLogger(__name__)


class SeleniumScraper(BaseScraper):
    async def scrape_page(self, url: str, **kwargs) -> PageContent:
        import time
        start_time = time.time()

        # Skip PDF and other download files
        if url.lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.exe', '.dmg')):
            raise ScraperError(f"Skipping download file: {url}")

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'user-agent={self.user_agent}')
        options.add_argument('--disable-blink-features=AutomationControlled')

        driver = None
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(self.timeout)

            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            html = driver.page_source
            title = driver.title

            # Convert HTML to markdown
            markdown = MarkdownConverter.convert(html, method='auto')

            load_time = time.time() - start_time
            self.update_stats(True, len(html), load_time)

            return PageContent(url=url, html=html, markdown=markdown, title=title, load_time=load_time)

        except Exception as e:
            self.update_stats(False, 0, time.time() - start_time)
            raise ScraperError(f"Selenium failed for {url}: {e}")
        finally:
            if driver:
                driver.quit()

    async def scrape_multi_page(self, base_url: str, max_pages: int = 15, important_paths: Optional[List[str]] = None, **kwargs) -> ScraperResult:
        # Simplified multi-page: just scrape homepage
        try:
            page = await self.scrape_page(base_url, **kwargs)
            return ScraperResult(status=ScraperStatus.SUCCESS, method=ScraperMethod.SELENIUM, pages=[page], pages_crawled=1)
        except Exception as e:
            return ScraperResult(status=ScraperStatus.FAILED, method=ScraperMethod.SELENIUM, error_message=str(e))

    def is_available(self) -> bool:
        try:
            from selenium import webdriver
            return True
        except ImportError:
            return False

    def get_method(self) -> ScraperMethod:
        return ScraperMethod.SELENIUM
