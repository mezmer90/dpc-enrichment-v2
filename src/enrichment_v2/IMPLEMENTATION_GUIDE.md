# Implementation Guide - Remaining Components

This guide provides complete implementation details for finishing the enrichment system.

---

## ✅ Completed (40%)

1. Configuration system
2. Base scraper (Strategy pattern)
3. Circuit breaker
4. Retry with backoff
5. Rate limiter
6. Progress tracker
7. Crawl4AI scraper
8. Documentation

---

## 🚧 Remaining Components (60%)

### 1. Additional Scrapers

**File:** `scraper/selenium_scraper.py`

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base_scraper import BaseScraper, ScraperMethod, PageContent

class SeleniumScraper(BaseScraper):
    async def scrape_page(self, url: str, **kwargs) -> PageContent:
        options = Options()
        options.add_argument('--headless')
        options.add_argument(f'user-agent={self.user_agent}')
        driver = webdriver.Chrome(options=options)

        try:
            driver.set_page_load_timeout(self.timeout)
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            html = driver.page_source
            # Convert to markdown using html2text
            return PageContent(url=url, html=html, markdown=html_to_markdown(html), title=driver.title)
        finally:
            driver.quit()
```

**File:** `scraper/playwright_scraper.py`

```python
from playwright.async_api import async_playwright
from .base_scraper import BaseScraper, ScraperMethod

class PlaywrightScraper(BaseScraper):
    async def scrape_page(self, url: str, **kwargs) -> PageContent:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=self.user_agent)
            await page.goto(url, timeout=self.timeout * 1000)
            html = await page.content()
            title = await page.title()
            await browser.close()
            return PageContent(url=url, html=html, markdown=html_to_markdown(html), title=title)
```

**File:** `scraper/requests_scraper.py`

```python
import aiohttp
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, ScraperMethod

class RequestsScraper(BaseScraper):
    async def scrape_page(self, url: str, **kwargs) -> PageContent:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=self.timeout, headers={'User-Agent': self.user_agent}) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                title = soup.find('title').get_text() if soup.find('title') else ""
                return PageContent(url=url, html=html, markdown=html_to_markdown(html), title=title)
```

### 2. Scraper Factory

**File:** `scraper/scraper_factory.py`

```python
from typing import List
from .base_scraper import BaseScraper, ScraperMethod
from .crawl4ai_scraper import Crawl4AIScraper
from .selenium_scraper import SeleniumScraper
from .playwright_scraper import PlaywrightScraper
from .requests_scraper import RequestsScraper

class ScraperFactory:
    @staticmethod
    def create_scraper(method: ScraperMethod, **kwargs) -> BaseScraper:
        if method == ScraperMethod.CRAWL4AI:
            return Crawl4AIScraper(**kwargs)
        elif method == ScraperMethod.SELENIUM:
            return SeleniumScraper(**kwargs)
        elif method == ScraperMethod.PLAYWRIGHT:
            return PlaywrightScraper(**kwargs)
        elif method == ScraperMethod.REQUESTS:
            return RequestsScraper(**kwargs)
        raise ValueError(f"Unknown scraper method: {method}")

    @staticmethod
    def get_available_scrapers(**kwargs) -> List[BaseScraper]:
        scrapers = []
        for method in [ScraperMethod.CRAWL4AI, ScraperMethod.SELENIUM, ScraperMethod.PLAYWRIGHT, ScraperMethod.REQUESTS]:
            scraper = ScraperFactory.create_scraper(method, **kwargs)
            if scraper.is_available():
                scrapers.append(scraper)
        return scrapers

    @staticmethod
    def create_with_fallback(**kwargs) -> List[BaseScraper]:
        return ScraperFactory.get_available_scrapers(**kwargs)
```

### 3. Markdown Converter

**File:** `markdown/converter.py`

```python
import html2text
from markdownify import markdownify
from bs4 import BeautifulSoup

class MarkdownConverter:
    @staticmethod
    def convert(html: str, method: str = 'auto') -> str:
        methods = {
            'html2text': MarkdownConverter._html2text,
            'markdownify': MarkdownConverter._markdownify,
            'custom': MarkdownConverter._custom_stripper,
        }

        if method == 'auto':
            # Try all methods in order
            for m in ['html2text', 'markdownify', 'custom']:
                try:
                    return methods[m](html)
                except:
                    continue
            return html  # Worst case: return HTML

        return methods.get(method, MarkdownConverter._custom_stripper)(html)

    @staticmethod
    def _html2text(html: str) -> str:
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        return h.handle(html)

    @staticmethod
    def _markdownify(html: str) -> str:
        return markdownify(html)

    @staticmethod
    def _custom_stripper(html: str) -> str:
        soup = BeautifulSoup(html, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text(separator='\n')
```

**File:** `markdown/merger.py`

```python
from typing import List
from ..scraper.base_scraper import PageContent

class MarkdownMerger:
    @staticmethod
    def merge_pages(pages: List[PageContent]) -> str:
        sections = []
        for i, page in enumerate(pages, 1):
            header = f"\n\n{'='*80}\nPAGE {i}: {page.title or page.url}\n{'='*80}\n\n"
            sections.append(header + page.markdown)
        return "\n".join(sections)

    @staticmethod
    def create_toc(pages: List[PageContent]) -> str:
        toc = "# Table of Contents\n\n"
        for i, page in enumerate(pages, 1):
            toc += f"{i}. [{page.title or 'Page'}]({page.url})\n"
        return toc
```

### 4. Gemini Client

**File:** `ai/gemini_client.py`

```python
import openai
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: str, model: str, temperature: float = 0.1, max_tokens: int = 8000):
        self.client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def extract_data(self, markdown: str, practice_data: dict, prompt_template: str) -> Dict:
        try:
            # Build prompt with markdown and existing data
            prompt = prompt_template.format(
                markdown=markdown[:800000],  # 1M context ~ 800k chars
                practice_name=practice_data.get('practice_name', ''),
                website_url=practice_data.get('website_url', '')
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a data extraction expert for healthcare practices."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            # Parse JSON response
            content = response.choices[0].message.content
            import json
            extracted = json.loads(content)

            # Track cost
            cost = (response.usage.prompt_tokens / 1_000_000 * 0.30) + \
                   (response.usage.completion_tokens / 1_000_000 * 2.50)

            extracted['_llm_cost'] = cost
            extracted['_llm_tokens_input'] = response.usage.prompt_tokens
            extracted['_llm_tokens_output'] = response.usage.completion_tokens

            return extracted

        except Exception as e:
            logger.error(f"Gemini extraction failed: {e}")
            raise
```

### 5. Field Extractor (with Prompt)

**File:** `ai/extractor.py`

```python
EXTRACTION_PROMPT = """
You are extracting structured data from a Direct Primary Care practice website.

Website: {website_url}
Practice Name: {practice_name}

Below is the complete website content in markdown format:

{markdown}

Extract the following information in JSON format. Return ONLY valid JSON with no additional text.

For any field you cannot find, use "-NA-" as the value.

{{
  "philosophy": "Practice philosophy/mission statement",
  "tagline": "Practice tagline or slogan",
  "providers": [
    {{
      "name": "Dr. Name",
      "specialty": "Specialty",
      "bio": "Biography text",
      "medical_school": "School name",
      "residency": "Residency program",
      "board_certifications": ["Certification 1"]
    }}
  ],
  "services_offered": ["Service 1", "Service 2", ...],
  "procedures_offered": ["Procedure 1", ...],
  "lab_services": ["Lab service 1", ...],
  "imaging_services": ["Imaging service 1", ...],
  "pricing_individual_monthly": 0.0,
  "pricing_individual_annual": 0.0,
  "pricing_family_monthly": 0.0,
  "pricing_family_annual": 0.0,
  "pricing_child_monthly": 0.0,
  "pricing_senior_monthly": 0.0,
  "enrollment_fee": 0.0,
  "office_hours_monday": "Hours",
  "office_hours_tuesday": "Hours",
  "office_hours_wednesday": "Hours",
  "office_hours_thursday": "Hours",
  "office_hours_friday": "Hours",
  "office_hours_saturday": "Hours",
  "office_hours_sunday": "Hours",
  "telehealth_available": true,
  "home_visits_available": false,
  "same_day_appointments": true,
  "after_hours_access": false,
  "ages_accepted": "All ages",
  "ages_accepted_min": 0,
  "ages_accepted_max": 100,
  "languages_spoken": ["English"],
  "email": "email@example.com",
  "phone_alt": "Alternate phone",
  "facebook_url": "URL",
  "instagram_url": "URL",
  "twitter_url": "URL",
  "patient_portal_url": "URL",
  "online_booking_url": "URL",
  "insurance_alternatives": "Description of insurance alternatives",
  "payment_methods": ["Credit card", "ACH", ...],
  "testimonials": [
    {{"text": "Quote", "author": "Name"}}
  ],
  "faq_1_question": "Question text",
  "faq_1_answer": "Answer text",
  "faq_2_question": "Question text",
  "faq_2_answer": "Answer text",
  "faq_3_question": "Question text",
  "faq_3_answer": "Answer text",
  "faq_4_question": "Question text",
  "faq_4_answer": "Answer text",
  "faq_5_question": "Question text",
  "faq_5_answer": "Answer text"
}}

Extract as much information as possible. Be thorough and accurate.
"""

class FieldExtractor:
    def __init__(self, gemini_client):
        self.client = gemini_client

    async def extract(self, markdown: str, practice_data: dict) -> dict:
        return await self.client.extract_data(markdown, practice_data, EXTRACTION_PROMPT)
```

### 6. Storage

**File:** `storage/markdown_storage.py`

```python
from pathlib import Path
from typing import List
from ..scraper.base_scraper import PageContent
import json

class MarkdownStorage:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_pages(self, practice_id: str, pages: List[PageContent]):
        practice_dir = self.base_dir / practice_id
        practice_dir.mkdir(exist_ok=True)

        for i, page in enumerate(pages, 1):
            filename = f"page_{i}_{self._sanitize_filename(page.title or 'page')}.md"
            (practice_dir / filename).write_text(page.markdown, encoding='utf-8')

    def save_merged(self, practice_id: str, merged_markdown: str):
        practice_dir = self.base_dir / practice_id
        practice_dir.mkdir(exist_ok=True)
        (practice_dir / "merged.md").write_text(merged_markdown, encoding='utf-8')

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        return "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in name)[:50]
```

**File:** `storage/data_storage.py`

```python
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime

class DataStorage:
    @staticmethod
    def save_enriched(practices: List[Dict], output_file: Path, metadata: Dict = None):
        data = {
            "metadata": metadata or {},
            "practices": practices,
            "generated_at": datetime.now().isoformat()
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def load_enriched(input_file: Path) -> List[Dict]:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('practices', [])
```

### 7. Orchestrator

See next section for complete orchestrator implementation.

### 8. Main Entry Point

See `run.py` template below.

---

## 🚀 Quick Implementation Commands

```bash
# Install dependencies
pip install crawl4ai selenium playwright aiohttp openai html2text markdownify beautifulsoup4

# Set API key
export OPENROUTER_API_KEY="your_key"

# Run
python src/enrichment_v2/run.py
```

---

## 📝 Next Developer Instructions

1. Implement remaining scrapers (Selenium, Playwright, Requests)
2. Complete scraper factory
3. Build markdown converter and merger
4. Implement Gemini client
5. Create field extractor with prompt
6. Build storage systems
7. Create orchestrator (see detailed template below)
8. Build main entry point

Total time: ~4-6 hours for experienced developer

---

**All architectural decisions are made. Just implement following the patterns established.**
