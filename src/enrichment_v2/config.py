"""
Configuration for DPC Enrichment System V2

This is a comprehensive, production-grade enrichment system with:
- Multi-threaded scraping
- Multiple fallback methods
- Multi-page crawling
- Markdown storage
- Gemini 2.5 Flash Preview AI model
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==================== PATHS ====================

BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / 'data'
ENRICHED_DIR = DATA_DIR / 'enriched'
MARKDOWN_DIR = DATA_DIR / 'markdown'
PROGRESS_DIR = DATA_DIR / 'progress'
LOGS_DIR = BASE_DIR / 'logs'

# Input data (use final directory which has enrichment_level field)
INPUT_FILE = DATA_DIR / 'final' / 'dpc_directory_complete_v1.json'

# Output files
OUTPUT_FILE = ENRICHED_DIR / 'dpc_enriched_v2_FINAL.json'
PROGRESS_FILE = PROGRESS_DIR / 'enrichment_v2_state.json'

# Create directories
MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

# Note: DEFAULT_* variables removed - use direct references to avoid duplication

# ==================== SCRAPING ====================

# Multi-threading settings
MAX_WORKERS = 2  # Number of concurrent scrapers (reduced from 6 to prevent resource exhaustion)
BATCH_SIZE = 50  # Practices per batch

# Timeout settings (seconds)
SCRAPER_TIMEOUT = 60  # Timeout for individual page loads (increased for JS-heavy sites)
TIMEOUT_PAGE_LOAD = 60
TIMEOUT_TOTAL_SCRAPE = 180  # Max time per practice (increased proportionally)

# Content quality thresholds
MIN_CONTENT_LENGTH = 600  # Minimum chars per page (reduced from implicit 2500)
MIN_SUBSTANTIAL_PAGES = 3  # Pages needed with MIN_CONTENT_LENGTH

# Rate limiting
RATE_LIMIT_DELAY = 1.0  # Seconds between requests to same domain
RATE_LIMIT_PER_DOMAIN = 5  # Max concurrent requests per domain

# Pages to crawl per practice
MAX_PAGES_PER_PRACTICE = 15  # Homepage + up to 14 priority pages for comprehensive enrichment
IMPORTANT_PAGES = [
    'index', 'home',
    'about', 'about-us', 'our-story', 'who-we-are', 'mission',
    'services', 'what-we-offer', 'care', 'treatment', 'offerings',
    'providers', 'team', 'our-team', 'doctors', 'physicians', 'staff',
    'pricing', 'membership', 'fees', 'costs', 'plans', 'packages',
    'contact', 'contact-us', 'get-started', 'join', 'enroll',
    'faq', 'faqs', 'questions',
    'testimonials', 'reviews',
    'blog', 'news',
]

# User agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

# ==================== MARKDOWN CONVERSION ====================

# Conversion methods priority (1 = highest)
MARKDOWN_METHODS = [
    'crawl4ai',      # Method 1: crawl4ai built-in
    'html2text',     # Method 2: html2text library
    'markdownify',   # Method 3: markdownify library
    'custom',        # Method 4: custom HTML stripper (plain text fallback)
]

# Markdown cleaning options
MARKDOWN_CLEAN_OPTIONS = {
    'remove_images': False,  # Keep image references
    'remove_links': False,   # Keep links
    'remove_scripts': True,  # Remove script tags
    'remove_styles': True,   # Remove style tags
    'body_only': True,       # Only body content
}

# ==================== AI MODEL ====================

# Gemini 2.5 Flash Preview via OpenRouter
AI_MODEL = 'google/gemini-2.5-flash-preview-09-2025'
AI_PROVIDER = 'openrouter'
AI_BASE_URL = 'https://openrouter.ai/api/v1'

# Get API keys from environment (REQUIRED - no defaults for security)
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
if not OPENROUTER_API_KEY:
    print("ERROR: OPENROUTER_API_KEY not set in environment variables!")
    print("Please set it in your .env file or environment")
    print("Example: OPENROUTER_API_KEY=sk-or-v1-...")

# ScraperAPI (commercial scraping with 98.9% success rate)
SCRAPERAPI_KEY = os.getenv('SCRAPERAPI_KEY', '')
if not SCRAPERAPI_KEY:
    print("ERROR: SCRAPERAPI_KEY not set in environment variables!")
    print("Please set it in your .env file or environment")

SERPER_API_KEY = os.getenv('SERPER_API_KEY', '')

# Enable ScraperAPI by default
USE_SCRAPING_API = os.getenv('USE_SCRAPING_API', 'true').lower() == 'true'

# AI parameters
AI_TEMPERATURE = 0.1  # Low temperature for consistency
AI_MAX_TOKENS = 8000  # Max output tokens
AI_MAX_RETRIES = 3
AI_TIMEOUT = 60

# Context settings
MAX_CONTEXT_CHARS = 800000  # ~200k tokens for 1M context window
TRUNCATE_IF_NEEDED = True

# ==================== DATA EXTRACTION ====================

# Fields to extract (comprehensive)
EXTRACTION_FIELDS = {
    # Basic info (from DPC Frontier - preserve)
    'practice_id': str,
    'practice_name': str,
    'website_url': str,
    'phone': str,
    'address_street': str,
    'address_city': str,
    'address_state': str,
    'address_zip': str,
    'latitude': float,
    'longitude': float,
    'specialty': str,
    'practice_type': str,
    'verified': bool,

    # Enriched fields
    'philosophy': str,
    'tagline': str,
    'mission_statement': str,
    'year_established': int,

    # Providers
    'providers': list,  # [{name, specialty, bio, medical_school, residency, board_certifications}]
    'provider_count': int,

    # Services
    'services_offered': list,
    'procedures_offered': list,
    'lab_services': list,
    'imaging_services': list,

    # Pricing
    'pricing_individual_monthly': float,
    'pricing_individual_annual': float,
    'pricing_family_monthly': float,
    'pricing_family_annual': float,
    'pricing_child_monthly': float,
    'pricing_senior_monthly': float,
    'enrollment_fee': float,
    'discounts_available': str,

    # Operational details
    'hours': str,
    'office_hours_monday': str,
    'office_hours_tuesday': str,
    'office_hours_wednesday': str,
    'office_hours_thursday': str,
    'office_hours_friday': str,
    'office_hours_saturday': str,
    'office_hours_sunday': str,
    'after_hours_access': bool,
    'same_day_appointments': bool,
    'average_visit_length': str,

    # Patient info
    'ages_accepted': str,
    'ages_accepted_min': int,
    'ages_accepted_max': int,
    'accepting_patients': bool,
    'languages_spoken': list,

    # Technology
    'telehealth_available': bool,
    'home_visits_available': bool,
    'patient_portal_url': str,
    'online_booking_url': str,

    # Social & contact
    'facebook_url': str,
    'instagram_url': str,
    'twitter_url': str,
    'linkedin_url': str,
    'youtube_url': str,
    'phone_alt': str,
    'email': str,

    # Additional
    'insurance_alternatives': str,
    'payment_methods': list,
    'testimonials': list,
    'dba_names': list,
    'additional_locations': list,
    'recent_blog_posts': list,

    # FAQ Fields (Top 5 most common questions)
    'faq_1_question': str,
    'faq_1_answer': str,
    'faq_2_question': str,
    'faq_2_answer': str,
    'faq_3_question': str,
    'faq_3_answer': str,
    'faq_4_question': str,
    'faq_4_answer': str,
    'faq_5_question': str,
    'faq_5_answer': str,
}

# ==================== LOGGING ====================

LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = LOGS_DIR / 'enrichment_v2.log'

# ==================== PROGRESS TRACKING ====================

CHECKPOINT_INTERVAL = 1  # Save progress after EVERY practice (zero data loss!)
RESUME_FROM_CHECKPOINT = True

# ==================== ERROR HANDLING ====================

MAX_RETRIES_PER_PRACTICE = 3
RETRY_DELAY = 5  # Seconds between retries
CONTINUE_ON_ERROR = True  # Don't stop entire process on single failure

# ==================== STATISTICS ====================

TRACK_STATS = True
STATS_INTERVAL = 25  # Print stats every N practices
