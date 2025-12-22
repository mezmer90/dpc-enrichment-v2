# Batch Enrichment V2 - Setup Guide

## Overview
This package contains everything needed to run the DPC practice enrichment using the V2 system with ScraperAPI and Gemini AI.

## Package Contents

### Core Files
- `batch_enrich_v2.py` - Main enrichment script
- `requirements_enrichment.txt` - Python dependencies
- `dpc_complete_2763_practices_with_corrected_urls.json` - Input data (2,763 practices)

### Source Code
- `src/enrichment_v2/` - Complete V2 enrichment system
  - `ai/` - Gemini AI integration (extraction, URL selection)
  - `scraper/` - Multi-scraper system (ScraperAPI, Playwright, etc.)
  - `markdown/` - HTML to markdown conversion
  - `storage/` - Data and markdown storage
  - `utils/` - Progress tracking, rate limiting, retry logic
  - `config.py` - System configuration
  - `orchestrator.py` - Main enrichment orchestrator

### Configuration (Optional)
- `config/` - Additional configuration files

### Documentation
- `README.md` - Data file documentation
- `SETUP_GUIDE.md` - This file

## Prerequisites

### 1. Python Environment
- Python 3.10 or higher
- Virtual environment recommended

### 2. API Keys Required
You need two API keys:

**OpenRouter API Key** (for Gemini AI)
- Sign up at: https://openrouter.ai/
- Get API key from dashboard
- Used for: Smart URL selection and data extraction
- Cost: ~$0.005 per practice

**ScraperAPI Key** (for web scraping)
- Sign up at: https://www.scraperapi.com/
- Get API key from dashboard
- Used for: High-success rate web scraping (98.9%)
- Cost: ~$0.024 per practice

## Installation Steps

### 1. Extract Package
```bash
# Extract to your desired location
cd /path/to/extraction/location
```

### 2. Install Dependencies
```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install required packages
pip install -r requirements_enrichment.txt

# Install Playwright browsers
playwright install chromium
```

### 3. Configure API Keys

Edit `src/enrichment_v2/config.py` and add your API keys:

```python
# Line 109-114
OPENROUTER_API_KEY = 'your-openrouter-api-key-here'
SCRAPERAPI_KEY = 'your-scraperapi-key-here'
```

Or set as environment variables:
```bash
# Windows:
set OPENROUTER_API_KEY=your-key
set SCRAPERAPI_KEY=your-key

# Linux/Mac:
export OPENROUTER_API_KEY=your-key
export SCRAPERAPI_KEY=your-key
```

### 4. Configure Input/Output Paths

Edit `src/enrichment_v2/config.py` (lines 25-29):

```python
INPUT_FILE = DATA_DIR / 'final' / 'dpc_directory_complete_v1.json'
OUTPUT_FILE = ENRICHED_DIR / 'dpc_enriched_v2_FINAL.json'
```

Update to point to your data file:
```python
INPUT_FILE = Path('dpc_complete_2763_practices_with_corrected_urls.json')
OUTPUT_FILE = Path('output') / 'dpc_enriched_v2_FINAL.json'
```

Or keep defaults and create the directory structure:
```bash
mkdir -p data/final
cp dpc_complete_2763_practices_with_corrected_urls.json data/final/dpc_directory_complete_v1.json
```

## Running the Enrichment

### Test Run (5 practices)
```bash
python batch_enrich_v2.py --limit 5
```

### Small Test (20 practices)
```bash
python batch_enrich_v2.py --limit 20
```

### Full Run (All 2,763 practices)
```bash
python batch_enrich_v2.py
```

## Expected Results

### Test Run (5 practices)
- Runtime: ~30 seconds
- Cost: ~$0.15
- Success rate: 90-95%

### Full Run (2,763 practices)
- Runtime: 3-5 hours
- Cost: ~$80-100
- Success rate: 90-95%
- Output: 2,400-2,600 successfully enriched practices

## Features

### Robust Scraping
- **ScraperAPI**: 98.9% success rate, bypasses bot detection
- **Multi-page crawling**: Up to 15 pages per practice
- **Smart URL selection**: Gemini AI picks best pages to scrape
- **Circuit breaker**: Automatic fallback if failures occur

### Data Safety
- **Progressive saving**: Saves after EVERY practice
- **Auto-resume**: Continues from last checkpoint if interrupted
- **Zero data loss**: Complete crash protection
- **Backups**: Automatic backups of progress

### Quality Control
- **Content validation**: Minimum 2500 characters per page
- **Multi-page requirement**: At least 3 substantial pages
- **AI extraction**: Gemini 2.5 Flash extracts structured data
- **Field validation**: Comprehensive data field extraction

## Output

### Files Created
- `data/enriched/dpc_enriched_v2_FINAL.json` - Enriched practices
- `data/progress/enrichment_v2_state.json` - Progress tracking
- `data/markdown/` - Markdown files for each practice
- `batch_enrichment_v2.log` - Detailed logs

### Data Fields Extracted
- Philosophy, tagline, mission statement
- Provider details (names, specialties, bios, credentials)
- Services offered, procedures, lab/imaging services
- Pricing (individual, family, child, senior rates)
- Office hours (by day), after-hours access
- Ages accepted, languages spoken
- Telehealth, home visits availability
- Patient portal, online booking URLs
- Social media, contact info
- FAQs (top 5 questions/answers)
- Testimonials, blog posts

## Monitoring Progress

### Check Progress
```bash
python check_progress.py
```

### View Logs
```bash
tail -f batch_enrichment_v2.log
```

### Check Output
```bash
python check_enriched_sample.py
```

## Troubleshooting

### API Key Errors
```
WARNING: OPENROUTER_API_KEY not set
```
- Solution: Set API keys in config.py or environment variables

### Import Errors
```
ModuleNotFoundError: No module named 'enrichment_v2'
```
- Solution: Run from the directory containing batch_enrich_v2.py
- The script adds `src/` to Python path automatically

### Playwright Errors
```
Playwright browser not found
```
- Solution: Run `playwright install chromium`

### Rate Limiting
- ScraperAPI: 5 requests/second (built-in rate limiting)
- OpenRouter: 10 requests/second (built-in rate limiting)

## Cost Management

### Per Practice Costs
- ScraperAPI: ~$0.024 (7 pages × $0.003/page)
- URL Selection: ~$0.001 (Gemini AI)
- Data Extraction: ~$0.005 (Gemini AI)
- **Total**: ~$0.030 per practice

### Full Run Cost Estimate
- 2,763 practices × $0.030 = ~$83
- With 90% success: ~$75 actual cost
- Monthly ScraperAPI plan: Check their pricing tiers

## Support Files Included

All files needed for enrichment:
✅ Main script (batch_enrich_v2.py)
✅ Complete V2 system (src/enrichment_v2/)
✅ Dependencies list (requirements_enrichment.txt)
✅ Input data (2,763 practices with corrected URLs)
✅ Configuration files
✅ Documentation

## Next Steps

1. Install dependencies
2. Configure API keys
3. Run test with --limit 5
4. Review output quality
5. Run full enrichment
6. Check results in output directory

## Questions?

Refer to:
- `src/enrichment_v2/README.md` - Technical documentation
- `src/enrichment_v2/IMPLEMENTATION_GUIDE.md` - Implementation details
- Source code comments for detailed explanations

---

Generated: December 22, 2025
Package Version: 2.0
