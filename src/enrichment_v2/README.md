# DPC Enrichment System V2

**A comprehensive, production-grade enrichment system for Direct Primary Care practices.**

## 🎯 Overview

The Enrichment System V2 is a complete rewrite designed for maximum reliability, scalability, and data completeness. It enriches DPC practice data by:

1. **Scraping practice websites** with 4-level fallback chain
2. **Crawling multiple pages** (up to 15 pages per practice)
3. **Converting to clean markdown** with 4 fallback methods
4. **Extracting 80+ structured fields** using Gemini 2.5 Flash Preview AI
5. **Saving all data** (markdown files + enriched JSON)

## ✨ Features

### Scraping
- **4 Scraper Methods**: crawl4ai (primary) → Selenium → Playwright → Requests
- **Multi-page Crawling**: Up to 15 pages per practice
- **Smart Page Prioritization**: Prioritizes important pages (about, services, pricing, providers)
- **Circuit Breakers**: Automatically skip failing domains
- **Rate Limiting**: Domain-based rate limiting to prevent IP bans

### Data Extraction
- **80+ Fields**: Comprehensive field extraction covering all practice aspects
- **5 FAQ Fields**: Extracts top 5 FAQs with questions and answers
- **Provider Details**: Full provider bios, credentials, specialties
- **Pricing Information**: All membership tiers and pricing options
- **Services**: Complete service lists, procedures, lab services, imaging

### Reliability
- **Retry Mechanisms**: Exponential backoff with jitter
- **Progress Tracking**: Checkpoint-based resumability
- **Error Handling**: Graceful error handling, never loses progress
- **Circuit Breakers**: Prevents repeated attempts to failing domains

### Performance
- **Async/Await**: Full async architecture
- **Concurrent Workers**: Configurable worker pool (default: 8)
- **ThreadPoolExecutor**: For blocking operations
- **Efficient Storage**: Atomic writes, backups

## 📁 Architecture

```
src/enrichment_v2/
├── config.py                    # Configuration & constants
├── orchestrator.py              # Main orchestration logic
├── run.py                       # CLI entry point
│
├── scraper/                     # Web scraping
│   ├── base_scraper.py         # Abstract base class (Strategy pattern)
│   ├── crawl4ai_scraper.py     # Primary scraper (crawl4ai)
│   ├── selenium_scraper.py     # Fallback #1 (Selenium)
│   ├── playwright_scraper.py   # Fallback #2 (Playwright)
│   ├── requests_scraper.py     # Fallback #3 (aiohttp/requests)
│   ├── scraper_factory.py      # Factory for creating scrapers
│   └── circuit_breaker.py      # Circuit breaker pattern
│
├── markdown/                    # Markdown processing
│   ├── converter.py            # HTML → Markdown (4 fallback methods)
│   └── merger.py               # Multi-page markdown merging
│
├── ai/                          # AI extraction
│   ├── gemini_client.py        # Gemini 2.5 Flash client (OpenRouter)
│   └── extractor.py            # Field extraction with validation
│
├── storage/                     # Data storage
│   ├── markdown_storage.py     # Markdown file organization
│   └── data_storage.py         # JSON data storage
│
└── utils/                       # Utilities
    ├── retry.py                # Retry with exponential backoff
    ├── rate_limiter.py         # Token bucket rate limiter
    └── progress.py             # Progress tracking
```

## 📊 Extracted Fields (80+)

### Basic Information
- practice_id, practice_name, website_url
- phone, address (street, city, state, zip)
- latitude, longitude
- specialty, practice_type

### Practice Details
- philosophy, tagline, mission_statement
- year_established
- dba_names, additional_locations

### Providers
- providers[] (name, specialty, bio, medical_school, residency, board_certifications)
- provider_count

### Services
- services_offered[] (comprehensive list)
- procedures_offered[]
- lab_services[]
- imaging_services[]

### Pricing
- pricing_individual_monthly, pricing_individual_annual
- pricing_family_monthly, pricing_family_annual
- pricing_child_monthly, pricing_senior_monthly
- enrollment_fee, discounts_available

### Hours & Access
- hours (general)
- office_hours_monday through office_hours_sunday
- after_hours_access, same_day_appointments
- average_visit_length

### Patient Information
- ages_accepted (description)
- ages_accepted_min, ages_accepted_max
- accepting_patients
- languages_spoken[]

### Technology
- telehealth_available
- home_visits_available
- patient_portal_url
- online_booking_url

### Contact & Social
- email, phone_alt
- facebook_url, instagram_url, twitter_url, linkedin_url, youtube_url

### Additional
- insurance_alternatives
- payment_methods[]
- testimonials[] (text, author)
- recent_blog_posts[] (title, url, date)

### FAQs (NEW!)
- faq_1_question, faq_1_answer
- faq_2_question, faq_2_answer
- faq_3_question, faq_3_answer
- faq_4_question, faq_4_answer
- faq_5_question, faq_5_answer

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+** (tested with Python 3.11)

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **OpenRouter API Key**:
   - Get your key from: https://openrouter.ai/
   - Set as environment variable or pass via CLI

### Basic Usage

```bash
# Fresh run
python src/enrichment_v2/run.py --api-key YOUR_OPENROUTER_KEY

# Resume previous run
python src/enrichment_v2/run.py --api-key YOUR_KEY --resume

# Process pooled practices first
python src/enrichment_v2/run.py --api-key YOUR_KEY --use-pooled-first

# High concurrency (20 workers)
python src/enrichment_v2/run.py --api-key YOUR_KEY --max-workers 20

# Custom input/output
python src/enrichment_v2/run.py \
  --api-key YOUR_KEY \
  --input data/processed/custom.json \
  --output data/enriched/custom_out.json

# Test API connection
python src/enrichment_v2/run.py --api-key YOUR_KEY --test-connection

# Verbose logging for debugging
python src/enrichment_v2/run.py --api-key YOUR_KEY --verbose
```

## ⚙️ Configuration

Edit `config.py` to customize:

### Scraping Settings
```python
MAX_WORKERS = 8                # Concurrent scrapers
MAX_PAGES_PER_PRACTICE = 15    # Pages to crawl per practice
SCRAPER_TIMEOUT = 30           # Timeout per page (seconds)
RATE_LIMIT_DELAY = 1.0         # Delay between requests to same domain
```

### AI Settings
```python
AI_MODEL = 'google/gemini-2.5-flash-preview-09-2025'
AI_TEMPERATURE = 0.1           # Low temperature for consistency
AI_MAX_TOKENS = 8000           # Max output tokens
MAX_CONTEXT_CHARS = 800000     # ~200k tokens (for 1M context)
```

### Progress & Checkpoints
```python
CHECKPOINT_INTERVAL = 10       # Save progress every N practices
RESUME_FROM_CHECKPOINT = True  # Enable resumability
```

## 📈 Expected Performance

For **2,763 practices**:

| Metric | Expected Value |
|--------|---------------|
| Success Rate | 90-95% |
| Total Cost | $20-40 |
| Total Time | 6-12 hours (8 workers) |
| Pages per Practice | 8-12 average |
| Markdown per Practice | 50-200 KB |
| Fields Extracted | 80+ per practice |

## 📂 Output Files

### Markdown Storage
```
data/markdown/{practice_id}/
├── page_1_homepage.md           # Individual page markdown
├── page_2_about.md
├── page_3_services.md
├── ...
├── merged.md                    # All pages merged
└── metadata.json                # Scraping metadata
```

### Enriched JSON
```json
{
  "metadata": {
    "version": "2.0",
    "source": "DPC Enrichment System V2",
    "generated_at": "2025-12-16T10:30:00",
    "total_practices": 2500,
    "statistics": {...}
  },
  "practices": [
    {
      "practice_id": "abc123",
      "practice_name": "Example DPC",
      "philosophy": "...",
      "providers": [...],
      "services_offered": [...],
      "pricing_individual_monthly": 75.0,
      "faq_1_question": "What is DPC?",
      "faq_1_answer": "...",
      "_enrichment_metadata": {
        "llm_cost": 0.0123,
        "llm_tokens_input": 25000,
        "llm_tokens_output": 1500
      },
      "_scraper_metadata": {
        "scraper_method": "crawl4ai",
        "pages_crawled": 12,
        "total_markdown_chars": 125000
      }
    }
  ]
}
```

### Progress Tracking
```
data/progress/enrichment_v2_state.json

{
  "last_updated": "2025-12-16T10:30:00",
  "total_practices": 2763,
  "completed": 2500,
  "failed": 200,
  "pending": 63,
  "practices": {
    "abc123": {
      "status": "completed",
      "last_updated": "2025-12-16T10:25:00",
      "attempts": 1,
      "enriched_data": {...}
    }
  }
}
```

## 🔄 Resume & Recovery

The system automatically saves progress every 10 practices (configurable). To resume:

```bash
python src/enrichment_v2/run.py --api-key YOUR_KEY --resume
```

This will:
1. Load progress from `data/progress/enrichment_v2_state.json`
2. Process only `pending` and `failed` practices
3. Merge results with existing enriched data

## 🛠️ Troubleshooting

### Low Success Rate

**Problem**: Success rate < 70%

**Solutions**:
1. Check `logs/enrichment_v2.log` for failure reasons
2. Increase timeout: `SCRAPER_TIMEOUT = 60`
3. Reduce workers: `--max-workers 4`
4. Check circuit breaker stats

### API Rate Limits

**Problem**: "Rate limit exceeded" errors

**Solutions**:
1. Reduce workers: `--max-workers 4`
2. Increase delay: `RATE_LIMIT_DELAY = 2.0`
3. Use OpenRouter's pooling feature

### Out of Memory

**Problem**: System crashes with OOM

**Solutions**:
1. Reduce workers: `--max-workers 4`
2. Reduce context: `MAX_CONTEXT_CHARS = 400000`
3. Process in batches (manually split input file)

### Scraper Failures

**Problem**: All scrapers failing for certain sites

**Solutions**:
1. Check circuit breaker logs
2. Manually test URLs in browser
3. Increase timeout: `SCRAPER_TIMEOUT = 60`
4. Check if sites block automated access

## 📝 Design Patterns Used

- **Strategy Pattern**: Scrapers implement common interface
- **Factory Pattern**: ScraperFactory creates scrapers
- **Circuit Breaker Pattern**: Prevents repeated failures
- **Singleton Pattern**: CircuitBreakerManager
- **Producer-Consumer**: Orchestrator with worker pool
- **Retry Pattern**: Exponential backoff with jitter
- **Token Bucket**: Rate limiting algorithm

## 🔍 Logging

Logs are saved to `logs/enrichment_v2.log`:

```
2025-12-16 10:25:00 - INFO - [abc123] Starting enrichment: Example DPC
2025-12-16 10:25:02 - INFO - [abc123] Trying Crawl4AIScraper
2025-12-16 10:25:15 - INFO - [abc123] ✓ Crawl4AIScraper succeeded: 12 pages
2025-12-16 10:25:20 - INFO - [abc123] ✓ Enriched successfully: 12 pages, 125000 chars, $0.0123
```

Set `--verbose` for DEBUG level logs.

## 🧪 Testing

### Test API Connection
```bash
python src/enrichment_v2/run.py --api-key YOUR_KEY --test-connection
```

### Test Single Practice
```python
import asyncio
from enrichment_v2 import EnrichmentOrchestrator

async def test():
    orchestrator = EnrichmentOrchestrator(
        openrouter_api_key="YOUR_KEY",
        input_file="test_data.json",  # Single practice
        output_file="test_output.json",
        markdown_dir="test_markdown",
        progress_file="test_progress.json"
    )

    stats = await orchestrator.run()
    print(stats)

asyncio.run(test())
```

## 📚 Dependencies

Core dependencies:
- **crawl4ai**: Primary web scraper
- **selenium**: Fallback scraper #1
- **playwright**: Fallback scraper #2
- **aiohttp**: Fallback scraper #3
- **openai**: OpenRouter API client (OpenAI-compatible)
- **html2text**: Markdown conversion
- **markdownify**: Markdown conversion (fallback)
- **beautifulsoup4**: HTML parsing

See `requirements.txt` for full list.

## 🎓 Key Concepts

### Multi-page Crawling
The system scrapes up to 15 pages per practice, prioritizing:
1. Homepage
2. Important pages (about, services, pricing, providers, etc.)
3. Additional pages up to limit

### Fallback Chain
If one method fails, the system automatically tries the next:
1. **crawl4ai**: Fastest, best markdown quality
2. **Selenium**: JavaScript rendering, more compatible
3. **Playwright**: Modern browser automation
4. **Requests**: Simple HTTP requests (fallback)

### Circuit Breakers
If a domain fails 5 times, the circuit breaker "opens" and skips that domain for 60 seconds, preventing wasted resources.

### Rate Limiting
Token bucket algorithm ensures we don't overwhelm domains:
- 5 requests per second per domain
- 1 second delay between requests to same domain

## 🚨 Important Notes

1. **API Costs**: Gemini 2.5 Flash Preview costs ~$0.01-0.02 per practice
2. **Time**: ~6-12 hours for full 2,763 practices (8 workers)
3. **Storage**: ~500 MB markdown + ~50 MB JSON
4. **Resumability**: Progress saved every 10 practices
5. **Data Safety**: Creates backups before overwriting files

## 📞 Support

For issues or questions:
1. Check `logs/enrichment_v2.log`
2. Review this README
3. Check `BUILD_STATUS.md` for known issues

## 🏗️ Future Enhancements

- [ ] Distributed workers (multi-machine)
- [ ] Real-time progress dashboard
- [ ] More AI models (Claude, GPT-4)
- [ ] Image extraction and OCR
- [ ] Automated data validation
- [ ] API server mode

## 📄 License

Part of the DPC Directory project.

---

**Built with ❤️ for the Direct Primary Care community.**
